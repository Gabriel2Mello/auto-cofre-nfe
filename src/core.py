from urllib.parse import urljoin
from time import sleep
from typing import cast
import random
from requests import (
  Timeout,
  RequestException,
  HTTPError,
)

from cloudscraper import CloudScraper

from src.emitente_handler import EmitenteHandler
from src.interface import escolher_emitente
from src.utils import salvar_arquivos, handle_error
from src.config import Config
from src.parsers import (
  encontrar_linha,
  extrair_dados,
  DocumentoFiscal,
)


CHECK_FLAG = 10

def processar_nota(
  session: CloudScraper,
  nota: str,
  mes_nota: int,
  tipo: str,
  empresa: str,
  mes_pasta: int,
  emitente_handler: EmitenteHandler
) -> None:
  try:
    linhas = carregar_dados(session, nota, tipo)
    linhas_validas = encontrar_linha(linhas, nota, mes_nota, tipo)

    if len(linhas_validas) == 1:
      linha = linhas_validas[0]
    else:
      linha = escolher_emitente(linhas_validas)

    linha_objeto = cast(DocumentoFiscal, linha)
    dados = extrair_dados(linha_objeto)

    xml, pdf = baixar_arquivos(
      session,
      dados['empresa_id'],
      dados['chave'],
      tipo
    )

    nome_emitente = emitente_handler.get_nome(dados['emitente'])

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
    sleep(random.uniform(0.5, 1.5))

  except Timeout as e:
    handle_error(e, msg='Site demorou a responder')
  except HTTPError as e:
    handle_error(e, msg='Erro HTTP')
  except RequestException as e:
    handle_error(e, msg='Erro desconhecido no site')
  except (KeyError, ValueError) as e:
    handle_error(e, msg='Valor faltando/inadequado')
  except Exception as e:
    handle_error(e, msg=f'Erro na nota {nota}')


def ver_arquivos(
  session: CloudScraper,
  tipo: str,
  tentativas: int = 3
) -> None:
  for i in range(tentativas):

    try:
      response = session.get(
        f'{Config.URL_BASE}/nfe/empresa/ver-arquivos-{tipo}',
      )
      response.raise_for_status()
      return

    except Timeout as e:
      if i < tentativas - 1:
        print(f"O site demorou a responder. Tentando acessar novamente ({i+1}/{tentativas})...")
        sleep(5)
      else:
        raise Timeout(f"\nNetwork Error: {e}")


def trocar_empresa(
  session: CloudScraper,
  empresa: str,
  empresas_href: dict
) -> None:
  cnpj_target = Config.CNPJ.get(empresa)
  if not cnpj_target:
    raise KeyError(f"CNPJ '{empresa}' não encontrado")

  empresa_link = empresas_href.get(cnpj_target)
  if not empresa_link:
    raise KeyError(f"Link da empresa '{empresa}' não encontrado")

  session.get(
    url=urljoin(Config.URL_BASE, empresa_link),
    headers={'Referer': f'{Config.URL_BASE}/login/enviar'},
    allow_redirects=True,
  ).raise_for_status()


def carregar_dados(
  session: CloudScraper,
  nota: str,
  tipo: str
) -> list:
  endpoint = f'ver-arquivos-{tipo}'

  payload = {
    'sEcho': '1',
    'iColumns': '7' if tipo == 'nfe' else '8',
    'sColumns': Config.COLUNAS[tipo],
    'nro_nota_de': str(nota),
    'flag_cliente': '98',
    'flag_conta': '98',
    'iDisplayStart': '0',
    'iDisplayLength': '25',
  }

  headers = {
    'X-Requested-With': Config.REQUESTED_WITH,
    'Referer': f'{Config.URL_BASE}/nfe/empresa/{endpoint}',
    'Accept': Config.ACCEPT,
  }

  response = session.post(
    url=f'{Config.URL_BASE}/nfe/empresa/{endpoint}/load',
    headers=headers,
    data=payload,
  )
  response.raise_for_status()

  return response.json().get('aaData', [])


def baixar_arquivos(
  session: CloudScraper,
  empresa_id: str,
  chave: str,
  tipo: str
) -> tuple[bytes, bytes]:
  ver_path = 'danfe' if tipo == 'nfe' else 'dacte'

  xml_url = f"{Config.URL_BASE}/nfe/download-arquivo/{tipo}/{empresa_id}/{chave}.xml"
  pdf_url = f"{Config.URL_BASE}/nfe/ver-{ver_path}/{tipo}/{empresa_id}/{chave}.pdf"

  response_xml = session.get(xml_url)
  response_xml.raise_for_status()

  response_pdf = session.get(pdf_url)
  response_pdf.raise_for_status()

  return response_xml.content, response_pdf.content


def marcar_flag(
  session: CloudScraper,
  codigo_arquivo: str,
  codigo_flag: int = CHECK_FLAG
) -> None:
  session.post(
    f'{Config.URL_BASE}/nfe/seta-flag/{codigo_arquivo}/{codigo_flag}',
    data={},
  ).raise_for_status()

