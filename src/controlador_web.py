"""Execução local com decisões explícitas do operador, sem entrada de console."""

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from threading import Condition, Event, Thread
from uuid import uuid4

from bs4 import BeautifulSoup

from src.auth import login
from src.config import Config
from src.core import baixar_arquivos, marcar_flag, processar_nota, trocar_empresa, ver_arquivos
from src.emitente_handler import EmitenteHandler
from src.enums import Empresa, TipoDocumento
from src.http_client import TimeoutScraper
from src.parsers import DocumentoFiscal, extrair_empresas_href, resolve_emitente
from src.utils import clean_name, salvar_arquivos
from metricas_nunes import registrar_evento


class ExecucaoInterrompida(Exception):
  pass


def competencia(valor: object) -> tuple[int, int]:
  if not isinstance(valor, str):
    raise ValueError('Informe a competência no formato AAAA-MM.')
  partes = valor.split('-')
  if (len(partes) != 2 or len(partes[0]) != 4 or len(partes[1]) != 2
      or not all(p.isascii() and p.isdigit() for p in partes)):
    raise ValueError('Informe a competência no formato AAAA-MM.')
  ano, mes = map(int, partes)
  date(ano, mes, 1)
  return mes, ano


@dataclass(frozen=True)
class Pedido:
  notas: list[str]
  empresa: Empresa
  tipo: TipoDocumento
  mes_nota: int
  ano_nota: int
  mes_pasta: int
  ano_pasta: int

  @classmethod
  def de_json(cls, dados: dict) -> 'Pedido':
    texto = dados.get('notas', '')
    if not isinstance(texto, str) or len(texto) > 12000:
      raise ValueError('Informe até 12.000 caracteres de números de documentos.')
    notas = []
    vistos = set()
    for item in texto.replace('\r', '\n').replace(';', ',').replace('\n', ',').split(','):
      nota = item.strip()
      if not nota:
        continue
      if not nota.isascii() or not nota.isdigit() or len(nota) > 9 or int(nota) == 0:
        raise ValueError('Use números de documentos com 1 a 9 dígitos, separados por vírgula ou linha.')
      if int(nota) not in vistos:
        notas.append(nota)
        vistos.add(int(nota))
    if not notas or len(notas) > 500:
      raise ValueError('Informe de 1 a 500 documentos por execução.')
    try:
      empresa = Empresa(dados.get('empresa'))
      tipo = TipoDocumento(dados.get('tipo'))
    except (ValueError, TypeError) as erro:
      raise ValueError('Selecione uma empresa e um tipo de documento válidos.') from erro
    mes_nota, ano_nota = competencia(dados.get('competencia'))
    mes_pasta, ano_pasta = competencia(dados.get('pasta'))
    return cls(notas, empresa, tipo, mes_nota, ano_nota, mes_pasta, ano_pasta)


def executar_lote(pedido: Pedido, estado: 'EstadoInterface') -> None:
  config = Config()
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
          estado.atualizar_nota(indice, 'Concluído', f'XML e PDF salvos · {nome_arquivo} · sinalizado no portal.')
        except ExecucaoInterrompida:
          estado.atualizar_nota(indice, 'Não processado', 'Execução interrompida antes de salvar.')
          raise
        except Exception as erro:
          situacao = 'Conferir sinalização' if salvo else 'Erro'
          detalhe = ('XML e PDF salvos; não foi possível confirmar a sinalização no portal. '
                     if salvo else 'O documento não foi concluído. Confira os arquivos antes de repetir. ')
          estado.atualizar_nota(indice, situacao, detalhe + mensagem_erro(erro))
  finally:
    emitentes.close()


def mensagem_erro(erro: Exception) -> str:
  # Exceções HTTP podem carregar URL com identificadores; não expor resposta ou credenciais.
  from requests import RequestException, Timeout
  if isinstance(erro, Timeout):
    return 'O portal demorou a responder. Confira a conexão antes de tentar novamente.'
  if isinstance(erro, RequestException):
    return 'Falha de comunicação com o Cofre NF-e. Confira o portal e a conexão.'
  if isinstance(erro, OSError):
    return 'Falha ao acessar ou gravar arquivos. Confira as permissões e o acesso à pasta.'
  if isinstance(erro, (ValueError, RuntimeError, KeyError)):
    return str(erro)[:500]
  return f'Falha inesperada ({type(erro).__name__}). Solicite apoio ao responsável.'


class EstadoInterface:
  def __init__(self, executor: Callable = executar_lote) -> None:
    self.condicao = Condition()
    self.parada = Event()
    self.executor = executor
    self.worker: Thread | None = None
    self.resposta: str | None = None
    self.encerrando = False
    self.dados = {
      'ativo': False, 'parando': False, 'status': 'Pronto para baixar os documentos.',
      'resultados': [], 'pergunta': None, 'lote': None,
    }

  def snapshot(self) -> dict:
    with self.condicao:
      return deepcopy(self.dados)

  def iniciar(self, dados: dict) -> None:
    pedido = Pedido.de_json(dados)
    with self.condicao:
      if self.encerrando:
        raise ValueError('O programa está encerrando. Abra o atalho novamente.')
      if self.dados['ativo']:
        raise ValueError('Já existe uma execução em andamento.')
      self.parada.clear()
      self.dados = {
        'ativo': True, 'parando': False, 'status': 'Preparando a execução…', 'pergunta': None,
        'lote': {'empresa': pedido.empresa.value, 'tipo': pedido.tipo.value,
                 'competencia': f'{pedido.ano_nota:04d}-{pedido.mes_nota:02d}',
                 'pasta': f'{pedido.ano_pasta:04d}-{pedido.mes_pasta:02d}'},
        'resultados': [{'nota': n, 'situacao': 'Aguardando', 'detalhe': ''} for n in pedido.notas],
      }
      self.worker = Thread(target=self._executar, args=(pedido,), daemon=False)
      self.worker.start()

  def _executar(self, pedido: Pedido) -> None:
    try:
      self.executor(pedido, self)
      self.informar('Execução interrompida. Confira os documentos pendentes.' if self.parada.is_set()
                    else 'Execução finalizada. Confira o resultado de cada documento.')
    except ExecucaoInterrompida:
      self.informar('Execução interrompida. Os documentos já concluídos foram preservados.')
    except Exception as erro:
      self.informar('Execução encerrada: ' + mensagem_erro(erro))
    finally:
      with self.condicao:
        for resultado in self.dados['resultados']:
          if resultado['situacao'] in ('Aguardando', 'Processando'):
            resultado.update(situacao='Não processado', detalhe='A execução terminou antes de concluir este documento.')
        self.dados.update(ativo=False, parando=False, pergunta=None)
        self.condicao.notify_all()

  def informar(self, texto: str) -> None:
    with self.condicao:
      self.dados['status'] = texto

  def atualizar_nota(self, indice: int, situacao: str, detalhe: str) -> None:
    with self.condicao:
      self.dados['resultados'][indice].update(situacao=situacao, detalhe=detalhe)
      self.dados['status'] = f"Documento {self.dados['resultados'][indice]['nota']} · {situacao.lower()}"

  def verificar_parada(self) -> None:
    if self.parada.is_set():
      raise ExecucaoInterrompida()

  def parar(self) -> None:
    with self.condicao:
      if self.dados['ativo']:
        self.parada.set()
        self.dados.update(parando=True, status='Parando após concluir a operação atual…', pergunta=None)
        self.condicao.notify_all()

  def encerrar(self) -> None:
    with self.condicao:
      self.encerrando = True
      self.parar()

  def perguntar(self, tipo: str, **campos) -> str:
    with self.condicao:
      self.verificar_parada()
      self.resposta = None
      self.dados['pergunta'] = {'id': uuid4().hex, 'tipo': tipo, **campos}
      self.dados['status'] = 'Aguardando sua resposta para continuar.'
      self.condicao.notify_all()
      self.condicao.wait_for(lambda: self.resposta is not None or self.parada.is_set())
      self.verificar_parada()
      resposta = self.resposta
      self.dados['pergunta'] = None
      return str(resposta)

  def responder(self, dados: dict) -> None:
    with self.condicao:
      pergunta = self.dados['pergunta']
      if not pergunta or dados.get('id') != pergunta['id'] or self.resposta is not None:
        raise ValueError('Esta decisão já foi atendida ou não está mais disponível.')
      valor = dados.get('valor')
      if not isinstance(valor, str):
        raise ValueError('Informe uma resposta válida.')
      if pergunta['tipo'] == 'emitente':
        if not valor.isascii() or not valor.isdigit() or int(valor) >= len(pergunta['opcoes']):
          raise ValueError('Selecione um dos emitentes apresentados.')
      elif not valor.strip() or len(valor) > 120 or not clean_name(valor):
        raise ValueError('Informe um nome de arquivo válido com até 120 caracteres.')
      self.resposta = valor
      self.condicao.notify_all()

  def selecionar_emitente(self, linhas: list[DocumentoFiscal]) -> DocumentoFiscal:
    opcoes = [{'nome': resolve_emitente(l.emitente_html),
               'data': BeautifulSoup(l.data_emissao_html, 'lxml').get_text(' ', strip=True),
               'valor': BeautifulSoup(l.valor_total, 'lxml').get_text(' ', strip=True)} for l in linhas]
    escolha = self.perguntar('emitente', opcoes=opcoes)
    return linhas[int(escolha)]

  def solicitar_nome(self, emitente: str) -> str:
    return self.perguntar('nome', emitente=emitente, sugestao=clean_name(emitente))
