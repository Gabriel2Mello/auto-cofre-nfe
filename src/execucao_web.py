"""Executor do lote web, carregado somente quando uma operação é iniciada."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from src.auth import login
from src.config import Config
from src.caminhos import documentos_entrada
from src.core import baixar_arquivos, marcar_flag, processar_nota, trocar_empresa, ver_arquivos
from src.emitente_handler import EmitenteHandler
from src.enums import Empresa
from src.http_client import TimeoutScraper
from src.parsers import NotaNaoEncontrada, extrair_empresas_href
from src.utils import salvar_arquivos
from metricas_nunes import registrar_evento
from src.controlador_web import ExecucaoInterrompida, mensagem_erro

if TYPE_CHECKING:
  from src.controlador_web import EstadoInterface, Pedido


def executar_lote(pedido: Pedido, estado: 'EstadoInterface') -> None:
  config = Config(caminho_documento_entrada=documentos_entrada() or None)
  if not Path(config.caminho_documento_entrada).is_dir():
    raise ValueError('A pasta CAMINHO_DOCUMENTO_ENTRADA está indisponível. Confira o acesso à rede.')
  emitentes = EmitenteHandler()
  try:
    with TimeoutScraper() as sessao:
      estado.verificar_parada()
      estado.informar('Conectando ao Cofre NF-e…')
      html = login(sessao, config.senha_cofre, config.cnpj[Empresa.MATRIZ])
      trocar_empresa(sessao, pedido.empresa, extrair_empresas_href(html), config.cnpj[pedido.empresa])
      ver_arquivos(sessao, pedido.tipo)
      for indice, nota in enumerate(pedido.notas):
        estado.verificar_parada()
        estado.atualizar_nota(indice, 'Processando', 'Consultando o documento no portal.')
        salvo = False
        try:
          dados = processar_nota(sessao, nota, pedido.tipo, pedido.mes_nota,
                                pedido.ano_nota, estado.selecionar_emitente)
          nome = emitentes.get_nome(dados['emitente'], estado.solicitar_nome)
          estado.verificar_parada()
          xml, pdf = baixar_arquivos(sessao, dados['empresa_id'], dados['chave'], pedido.tipo,
                                    nota=nota, cnpj_empresa=config.cnpj[pedido.empresa],
                                    mes_nota=pedido.mes_nota, ano_nota=pedido.ano_nota)
          estado.verificar_parada()
          nome_arquivo = salvar_arquivos(xml, pdf, nome, nota, pedido.empresa, pedido.mes_pasta,
                          str(pedido.ano_pasta), pedido.tipo, config.caminho_documento_entrada,
                          cnpj_empresa=config.cnpj[pedido.empresa],
                          mes_nota=pedido.mes_nota, ano_nota=pedido.ano_nota)
          salvo = True
          registrar_evento('documento_baixado', f"{pedido.empresa}:{pedido.tipo}:{dados['chave']}",
                           nota, empresa=str(pedido.empresa), tipo=str(pedido.tipo))
          # Concluir a sinalização da nota salva antes de atender uma parada.
          marcar_flag(sessao, dados['codigo_arquivo'])
          estado.atualizar_nota(indice, 'Concluído', f'XML e PDF salvos · {nome_arquivo}')
        except ExecucaoInterrompida:
          estado.atualizar_nota(indice, 'Não processado', 'Execução interrompida antes de salvar.')
          raise
        except NotaNaoEncontrada:
          estado.atualizar_nota(indice, 'Erro', 'Nenhuma nota encontrada')
        except Exception as erro:
          situacao = 'Conferir sinalização' if salvo else 'Erro'
          detalhe = ('XML e PDF salvos; não foi possível confirmar a sinalização no portal. '
                     if salvo else 'O documento não foi concluído. Confira os arquivos antes de repetir. ')
          estado.atualizar_nota(indice, situacao, detalhe + mensagem_erro(erro))
  finally:
    emitentes.close()
