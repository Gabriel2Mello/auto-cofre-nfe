import sys
from contextlib import closing
from metricas_nunes import registrar_evento
from sincronizar_estatisticas import Sincronizador
from time import sleep, perf_counter
from requests import (
  RequestException,
  HTTPError,
  Timeout,
)

from src.auth import login
from src.http_client import TimeoutScraper
from src.config import Config
from src.diagnostico_portal import diagnostico_execucao
from src.interface import input_dados
from src.parsers import extrair_empresas_href
from src.emitente_handler import EmitenteHandler
from src.enums import Empresa
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


def main() -> int:
  with Sincronizador(aplicacao='cofre-nfe'):
    return executar()


def executar() -> int:
  if sys.platform == 'win32':
    set_app_id()

  config = Config()

  notas, empresa, mes_nota, mes_pasta, ano_nota, ano_pasta, tipo = input_dados()
  emitente_handler = EmitenteHandler()
  start_time = perf_counter()
  falhas = 0

  with closing(emitente_handler), TimeoutScraper() as session:
    with diagnostico_execucao(empresa):
      html_login = login(
        session,
        config.senha_cofre,
        config.cnpj[Empresa.MATRIZ]
      )
      empresas_href = extrair_empresas_href(html_login)
      trocar_empresa(session, empresa, empresas_href, config.cnpj[empresa])

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
          nota=nota,
          cnpj_empresa=config.cnpj[empresa],
          mes_nota=mes_nota,
          ano_nota=ano_nota,
        )
        emitente = emitente_handler.get_nome(dados['emitente'])
        nome_arquivo = salvar_arquivos(
          xml,
          pdf,
          emitente,
          nota,
          empresa,
          mes_pasta,
          str(ano_pasta),
          tipo,
          config.caminho_documento_entrada,
          cnpj_empresa=config.cnpj[empresa],
          mes_nota=mes_nota,
          ano_nota=ano_nota,
        )
        print(f'Arquivos salvos: {nome_arquivo}')
        registrar_evento('documento_baixado', f"{empresa}:{tipo}:{dados['chave']}",
                         nota, empresa=str(empresa), tipo=str(tipo))
        marcar_flag(session, dados['codigo_arquivo'], nota=nota, tipo=tipo)
        sleep(0.2)

      except (KeyboardInterrupt, EOFError):
        raise
      except Timeout as e:
        falhas += 1
        handle_error(e, 'Site demorou a responder')
      except HTTPError as e:
        falhas += 1
        handle_error(e, 'Erro HTTP')
      except RequestException as e:
        falhas += 1
        handle_error(e, 'Erro no site')
      except (KeyError, ValueError) as e:
        falhas += 1
        handle_error(e, 'Valor faltando/inadequado')
      except Exception as e:
        falhas += 1
        handle_error(e, f'Erro na nota {nota}')

  elapsed_time = perf_counter() - start_time
  print(f'\nNotas sem falha: {len(notas) - falhas} · Notas com falha: {falhas}')
  print(f'\nTerminado em {elapsed_time:0.2f} segundos')
  pause()
  return 1 if falhas else 0


if __name__ == "__main__":
  try:
    from integracao_hub import executar_console
    raise SystemExit(executar_console('cofre-nfe', 'Cofre NF-e', main, sisplan=False))
  except (KeyboardInterrupt, EOFError):
    print('\n\nInterrompido pelo usuário.')
    sys.exit(130)
  except Exception as e:
    handle_error(e, '\nErro fatal')
    pause()
    sys.exit(1)

