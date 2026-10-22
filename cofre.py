"""Abre o painel local. main.py continua disponível para uso pelo console."""

import sys
import logging
from integracao_hub import IntegracaoLocal, executar_interface
from sincronizar_estatisticas import Sincronizador


def informar_falha(mensagem: str) -> None:
  if sys.platform == 'win32':
    import ctypes
    ctypes.windll.user32.MessageBoxW(None, mensagem, 'Cofre NF-e', 0x10)
  else:
    print(mensagem, file=sys.stderr)


def main(publicacao: IntegracaoLocal) -> int:
  with Sincronizador(aplicacao='cofre-nfe', relatar=logging.getLogger(__name__).info):
    return executar_painel(publicacao)


def executar_painel(publicacao: IntegracaoLocal) -> int:
  servidor = None
  estado = None
  try:
    from src.controlador_web import EstadoInterface
    from src.interface_web import criar_servidor
    from src.utils import set_app_id
    set_app_id()
    estado = EstadoInterface()
    servidor = criar_servidor(estado)
    servidor_ativo, estado_ativo = servidor, estado
    publicacao.publicar(servidor, estado.encerrar,
      lambda: {'encerrando': estado_ativo.encerrando, 'paginas': len(servidor_ativo.paginas)})
    servidor.serve_forever()
  except KeyboardInterrupt:
    pass
  except Exception as erro:
    publicacao.registrar_falha(erro)
    informar_falha(f'Não foi possível manter a interface local ({type(erro).__name__}). '
                   'Confira o ambiente Python e os recursos da instalação.')
    return 1
  finally:
    if estado is not None:
      estado.encerrar()
    if servidor is not None:
      servidor.server_close()
    if estado is not None and estado.worker is not None:
      estado.worker.join()
  return 0


if __name__ == '__main__':
  raise SystemExit(executar_interface('cofre-nfe', 'Cofre NF-e', False, main))
