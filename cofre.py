"""Abre o painel local. main.py continua disponível para uso pelo console."""

import sys
import logging
import time
from pathlib import Path
from contextlib import ExitStack
from integracao_hub import IntegracaoLocal, MedidorAbertura, ConflitoAplicacao
from sincronizar_estatisticas import Sincronizador


def informar_falha(mensagem: str) -> None:
  if sys.platform == 'win32':
    import ctypes
    ctypes.windll.user32.MessageBoxW(None, mensagem, 'Cofre NF-e', 0x10)
  else:
    print(mensagem, file=sys.stderr)


def informar_falha_abertura(erro, etapa):
  from src.diagnostico_abertura import registrar
  try:
    caminho = registrar(erro, etapa)
  except Exception:
    caminho = None
  mensagem = f'Não foi possível abrir o Cofre NF-e.\nEtapa: {etapa}. Erro: {type(erro).__name__}.'
  if caminho:
    mensagem += f'\n\nEnvie o conteúdo deste diagnóstico ao suporte:\n{caminho}'
  informar_falha(mensagem)


def main(publicacao: IntegracaoLocal) -> int:
  with MedidorAbertura('cofre-nfe') as medidor, ExitStack() as recursos:
    with medidor.etapa('sincronizacao'):
      from src.caminhos import vinculo_central
      recursos.enter_context(Sincronizador(aplicacao='cofre-nfe', arquivo=vinculo_central(),
                                          relatar=logging.getLogger(__name__).info))
    return executar_painel(publicacao, medidor)


def executar_painel(publicacao: IntegracaoLocal, medidor: MedidorAbertura | None = None) -> int:
  medidor = medidor or MedidorAbertura('cofre-nfe')
  servidor = None
  estado = None
  etapa = 'importacoes'
  try:
    with medidor.etapa('importacoes'):
      from src.controlador_web import EstadoInterface
      from src.interface_web import criar_servidor
    etapa = 'identidade_windows'
    with medidor.etapa('identidade_windows'):
      import desktop_windows
      from desktop_cofre import APP_ID
      desktop_windows.identidade_processo(APP_ID)
    etapa = 'estado'
    with medidor.etapa('estado'):
      estado = EstadoInterface()
    etapa = 'servidor_local'
    with medidor.etapa('servidor_local'):
      servidor = criar_servidor(estado)
      servidor.modo_desktop = True
    servidor_ativo, estado_ativo = servidor, estado
    etapa = 'publicacao'
    with medidor.etapa('publicacao'):
      publicacao.registro['desktop'] = 1
      publicacao.publicar(servidor, estado.encerrar,
        lambda: {'encerrando': estado_ativo.encerrando, 'ocupado': estado_ativo.snapshot()['ativo'],
                 'paginas': len(servidor_ativo.paginas)})
    etapa = 'janela_webview2'
    from desktop_cofre import executar
    executar(servidor)
  except KeyboardInterrupt:
    pass
  except Exception as erro:
    try:
      publicacao.registrar_falha(erro)
    except OSError:
      pass
    informar_falha_abertura(erro, etapa)
    return 1
  finally:
    if estado is not None:
      estado.encerrar()
    if servidor is not None:
      servidor.server_close()
    if estado is not None and estado.worker is not None:
      estado.worker.join()
  return 0


def iniciar() -> int:
  import argparse
  from desktop_cofre import ativar_existente, APP_ID
  from src.caminhos import recursos
  parser = argparse.ArgumentParser(description='Cofre NF-e desktop')
  parser.add_argument('--nunes-sem-navegador', action='store_true', help=argparse.SUPPRESS)
  parser.add_argument('--criar-atalho', type=Path)
  parser.add_argument('--autoteste-pacote', type=Path, help=argparse.SUPPRESS)
  args = parser.parse_args()
  try:
    if args.autoteste_pacote:
      from versao_pacote import autoteste
      return autoteste(args.autoteste_pacote)
    if args.criar_atalho:
      import desktop_windows
      from cofre_instalacao import relancamento, icone_relancamento
      desktop_windows.criar_atalho(args.criar_atalho.resolve(),
        relancamento() or desktop_windows.comando_reabrir([], Path(__file__).resolve()), icone_relancamento() or recursos() / 'icons/icone.ico',
        app_id=APP_ID, descricao='Baixar e organizar XML e PDF do Cofre NF-e')
      return 0
    from cofre_instalacao import reservar_execucao
    reservar_execucao()
    limite = time.monotonic() + 15
    while True:
      publicacao = IntegracaoLocal('cofre-nfe', 'Cofre NF-e', False, sem_navegador=True)
      try:
        with publicacao:
          return main(publicacao)
      except ConflitoAplicacao:
        if ativar_existente(publicacao.caminho, espera=max(0, limite - time.monotonic())):
          return 0
  except Exception as erro:
    if args.autoteste_pacote:
      from cofre_instalacao import atomico
      atomico(args.autoteste_pacote, {'formato': 1, 'pronto': False, 'erro': type(erro).__name__})
      return 1
    informar_falha(str(erro) if isinstance(erro, RuntimeError) else
      f'Não foi possível abrir a Cofre NF-e ({type(erro).__name__}). Confira a instalação e o diagnóstico local.')
    return 1


if __name__ == '__main__':
  raise SystemExit(iniciar())
