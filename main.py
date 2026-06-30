import sys
from time import sleep, perf_counter
from requests import (
  RequestException,
  HTTPError,
  Timeout,
)

from src.auth import login
from src.http_client import TimeoutScraper
from src.config import init_config
from src.interface import input_dados
from src.parsers import extrair_empresas_href
from src.emitente_handler import EmitenteHandler
from src.utils import (
  set_app_id,
  pause,
  handle_error,
)
from src.core import (
  ver_arquivos,
  trocar_empresa,
  processar_nota,
)


def main() -> None:
  if sys.platform == 'win32':
    set_app_id()

  init_config()
  notas, empresa, mes_nota, mes_pasta, tipo = input_dados()
  start_time = perf_counter()
  emitente_handler = EmitenteHandler()

  try:
    with TimeoutScraper(default_timeout=10) as session:
      html_login = login(session)
      empresas_href = extrair_empresas_href(html_login)
      trocar_empresa(session, empresa, empresas_href)

      print('Aguardando sincronização...')
      sleep(0.5)
      ver_arquivos(session, tipo)

      for nota in notas:
        print(f'\nProcessando: {nota}')
        processar_nota(
          session,
          nota,
          mes_nota,
          tipo,
          empresa,
          mes_pasta,
          emitente_handler
        )

  except Timeout as e:
    handle_error(e, msg='Site demorou a responder')
  except HTTPError as e:
    handle_error(e, msg='Erro HTTP')
  except RequestException as e:
    handle_error(e, msg='Erro desconhecido no site')
  except KeyError as e:
    handle_error(e, msg='Valor faltando')
  except ValueError as e:
    handle_error(e, msg='Valor inadequado')
  except Exception as e:
    handle_error(e)
  finally:
    emitente_handler.close()

  elapsed_time = perf_counter() - start_time
  print(f'\nTerminado em: {elapsed_time:0.2f} segundos')
  pause()


if __name__ == "__main__":
  try:
    main()
  except Exception as e:
    handle_error(e, msg='\nErro fatal')
    pause()
    sys.exit(1)

