from urllib.parse import urljoin
import time
import requests

from src.config import (
  ACCEPT,
  COLUNAS,
  CNPJ,
  REQUESTED_WITH,
  URL_BASE,
)


def ver_arquivos(session, tipo, tentativas=3):
  for i in range(tentativas):
    try:
      response = session.get(
        f'{URL_BASE}/nfe/empresa/ver-arquivos-{tipo}',
      )
      response.raise_for_status()
      return
    except requests.RequestException as e:
      if i < tentativas - 1:
        print(f"O site demorou a responder. Tentando acessar novamente ({i+1}/{tentativas})...")
        time.sleep(5)
      else:
        raise RuntimeError(f"\nNetwork error: {e}")


def trocar_empresa(session, empresa, empresas_href):
  cnpj_target = CNPJ.get(empresa)
  if not cnpj_target:
    raise KeyError(f"CNPJ '{empresa}' não encontrado")

  empresa_link = empresas_href.get(cnpj_target)
  if not empresa_link:
    raise RuntimeError('Link da empresa não encontrado')

  session.get(
    url=urljoin(URL_BASE, empresa_link),
    headers={'Referer': f'{URL_BASE}/login/enviar'},
    allow_redirects=True,
  ).raise_for_status()


def carregar_dados(session, nota, tipo):
  endpoint = f'ver-arquivos-{tipo}'

  payload = {
    'sEcho': '1',
    'iColumns': '7' if tipo == 'nfe' else '8',
    'sColumns': COLUNAS[tipo],
    'nro_nota_de': str(nota),
    'flag_cliente': '98',
    'flag_conta': '98',
    'iDisplayStart': '0',
    'iDisplayLength': '25',
  }

  headers = {
    'X-Requested-With': REQUESTED_WITH,
    'Referer': f'{URL_BASE}/nfe/empresa/{endpoint}',
    'Accept': ACCEPT,
  }

  response = session.post(
    url=f'{URL_BASE}/nfe/empresa/{endpoint}/load',
    headers=headers,
    data=payload,
  )
  response.raise_for_status()

  return response.json().get('aaData')


def baixar_arquivos(session, empresa_id, chave, tipo):
  ver_path = 'danfe' if tipo == 'nfe' else 'dacte'

  xml_url = f"{URL_BASE}/nfe/download-arquivo/{tipo}/{empresa_id}/{chave}.xml"
  pdf_url = f"{URL_BASE}/nfe/ver-{ver_path}/{tipo}/{empresa_id}/{chave}.pdf"

  response_xml = session.get(xml_url)
  response_xml.raise_for_status()

  response_pdf = session.get(pdf_url)
  response_pdf.raise_for_status()

  return response_xml.content, response_pdf.content


def marcar_flag(session, codigo_arquivo, codigo_flag=10):
  session.post(
    f'{URL_BASE}/nfe/seta-flag/{codigo_arquivo}/{codigo_flag}',
    data={},
  ).raise_for_status()

