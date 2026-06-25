import sys
from time import sleep, perf_counter
from requests import RequestException

from src.auth import login
from src.http_client import TimeoutScraper
from src.config import init_config
from src.interface import (
  input_dados,
)
from src.utils import (
  set_app_id,
)
from src.parsers import (
  extrair_empresas_href,
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
          mes_pasta
        )

  except (RequestException, KeyError) as e:
    print(f'Erro no site: {e}')
  except Exception as e:
    print(f'Erro inesperado: {type(e).__name__}: {e}')

  elapsed_time = perf_counter() - start_time
  print(f'\nTerminado em: {elapsed_time:0.2f} segundos')

  input('Pressione Enter para fechar...')


if __name__ == "__main__":
  try:
    main()
  except Exception as fatal_error:
    print(f'\nErro fatal: {fatal_error}')
    input('Pressione Enter para fechar...')
    sys.exit(1)

