import time
import random
import sys
from requests import Session
from time import perf_counter

from src.interface import input_dados
from src.auth import login
from src.emitente_handler import EmitenteHandler
from src.http_client import TimeoutSession
from src.utils import (
  salvar_arquivos,
  set_app_id,
)
from src.parsers import (
  extrair_empresas_href,
  encontrar_linha,
  extrair_dados,
)
from src.core import (
  ver_arquivos,
  trocar_empresa,
  carregar_dados,
  baixar_arquivos,
  marcar_flag,
)


def main() -> None:
  if sys.platform == 'win32':
    set_app_id()

  notas, empresa, mes_nota, mes_pasta, tipo = input_dados()
  start_time = perf_counter()

  with TimeoutSession(default_timeout=10) as session:
    try:
      html_login = login(session)
      empresas_href = extrair_empresas_href(html_login)
      trocar_empresa(session, empresa, empresas_href)

      print('Aguardando sincronização do sistema...')
      time.sleep(0.5)

      ver_arquivos(session, tipo)
      emitente_handler = EmitenteHandler()

      for nota in notas:
        print(f'\nProcessando: {nota}')

        try:
          linhas = carregar_dados(session, nota, tipo)
          linha = encontrar_linha(
            linhas,
            nota,
            mes_nota,
            tipo
          )
          dados = extrair_dados(linha, tipo)

          xml, pdf = baixar_arquivos(
            session,
            dados['empresa_id'],
            dados['chave'],
            tipo
          )

          nome_emitente = emitente_handler.get_or_create(dados['emitente'])
          salvar_arquivos(
            xml,
            pdf,
            nome_emitente,
            nota,
            empresa,
            mes_pasta,
            tipo
          )

          marcar_flag(session, dados['codigo_arquivo'])

          delay = random.uniform(0.5, 1.5)
          time.sleep(delay)

        except Exception as e:
          print(f'Erro na nota {nota}: {e}')
          time.sleep(5)

    except Exception as e:
      print(f'Erro fatal no processo: {e}')
      sys.exit(1)

  elapsed_time = perf_counter() - start_time
  print(f'\nTerminado em: {elapsed_time:0.2f} segundos')
  input('Pressione Enter para fechar...')


if __name__ == "__main__":
  main()

