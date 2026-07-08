import sys
from time import sleep, perf_counter
from requests import (
  RequestException,
  HTTPError,
  Timeout,
)

from src.auth import login
from src.http_client import TimeoutScraper
from src.config import Config
from src.interface import input_dados
from src.parsers import extrair_empresas_href
from src.emitente_handler import EmitenteHandler
from src.utils import (
  set_app_id,
  pause,
  handle_error,
  salvar_arquivos,
)
from src.core import (
  ver_arquivos,
  trocar_empresa,
  processar_nota,
  marcar_flag,
  baixar_arquivos,
)


def main() -> None:
  if sys.platform == 'win32':
    set_app_id()

  config = Config()

  notas, empresa, mes_nota, mes_pasta, ano_nota, ano_pasta, tipo = input_dados()
  emitente_handler = EmitenteHandler()
  start_time = perf_counter()

  with TimeoutScraper() as session:
    html_login = login(session, config.senha_cofre)
    empresas_href = extrair_empresas_href(html_login)
    trocar_empresa(session, empresa, empresas_href)

    print('Sincronizado...')
    sleep(0.2)
    ver_arquivos(session, tipo)

    for nota in notas:
      print(f'\nProcessando: {nota}')
      try:
        dados = processar_nota(
          session,
          nota,
          tipo,
          mes_nota,
          ano_nota,
        )
        xml, pdf = baixar_arquivos(
          session,
          dados['empresa_id'],
          dados['chave'],
          tipo,
        )
        emitente = emitente_handler.get_nome(dados['emitente'])
        salvar_arquivos(
          xml,
          pdf,
          emitente,
          nota,
          empresa,
          mes_pasta,
          str(ano_pasta),
          tipo,
          config.caminho_documento_entrada,
        )
        marcar_flag(session, dados['codigo_arquivo'])
        sleep(0.2)

      except Timeout as e:
        handle_error(e, 'Site demorou a responder')
      except HTTPError as e:
        handle_error(e, 'Erro HTTP')
      except RequestException as e:
        handle_error(e, 'Erro no site')
      except (KeyError, ValueError) as e:
        handle_error(e, 'Valor faltando/inadequado')
      except Exception as e:
        handle_error(e, f'Erro na nota {nota}')

    emitente_handler.close()
  elapsed_time = perf_counter() - start_time
  print(f'\nTerminado em {elapsed_time:0.2f} segundos')
  pause()


if __name__ == "__main__":
  try:
    main()
  except (KeyboardInterrupt, EOFError):
    print('\n\nInterrompido pelo usuário.')
    sys.exit(0)
  except Exception as e:
    handle_error(e, '\nErro fatal')
    pause()
    sys.exit(1)

