from urllib.parse import urljoin
from time import sleep
from requests import Session

from src.emitente_handler import EmitenteHandler
from src.interface import escolher_emitente
from src.utils import salvar_arquivos
from src.config import Config
from src.enums import TipoDocumento, Empresa
from src.parsers import (
  encontrar_linha,
  extrair_dados,
)


def processar_nota(
  session: Session,
  nota: str,
  mes_nota: int,
  tipo: TipoDocumento,
  empresa: Empresa,
  mes_pasta: int,
  emitente_handler: EmitenteHandler,
  caminho_documento: str,
) -> None:
  linhas = carregar_dados(session, nota, tipo)
  linhas_validas = encontrar_linha(linhas, nota, mes_nota, tipo)

  if len(linhas_validas) == 1:
    linha = linhas_validas[0]
  else:
    linha = escolher_emitente(linhas_validas)

  dados = extrair_dados(linha)

  xml, pdf = baixar_arquivos(
    session,
    dados['empresa_id'],
    dados['chave'],
    tipo,
  )
  nome_emitente = emitente_handler.get_nome(dados['emitente'])

  salvar_arquivos(
    xml,
    pdf,
    nome_emitente,
    nota,
    empresa,
    mes_pasta,
    tipo,
    caminho_documento,
  )
  marcar_flag(session, dados['codigo_arquivo'])
  sleep(0.2)


def ver_arquivos(
  session: Session,
  tipo: TipoDocumento,
  tentativas: int = 3
) -> None:
  for i in range(tentativas):
    try:
      response = session.get(
        f'{Config.URL_BASE}/nfe/empresa/ver-arquivos-{tipo}',
      )
      response.raise_for_status()
      return

    except Exception as e:
      if i < tentativas - 1:
        print(f"O site demorou a responder. Tentando acessar novamente ({i+1}/{tentativas})...")
        sleep(5)
      else:
        raise e


def trocar_empresa(
  session: Session,
  empresa: Empresa,
  empresas_href: dict[str, str],
) -> None:
  if not (cnpj_target := Config.CNPJ.get(empresa)):
    raise ValueError(f"CNPJ '{empresa}' não encontrado")

  if not (empresa_link := empresas_href.get(cnpj_target)):
    raise ValueError(f"Link da empresa '{empresa}' não encontrado")

  session.get(
    url=urljoin(Config.URL_BASE, empresa_link),
    headers={'Referer': f'{Config.URL_BASE}/login/enviar'},
    allow_redirects=True,
  ).raise_for_status()


def carregar_dados(
  session: Session,
  nota: str,
  tipo: TipoDocumento,
) -> list:
  endpoint = f'ver-arquivos-{tipo}'

  payload = {
    'sEcho': '1',
    'iColumns': '7' if tipo == TipoDocumento.NFE else '8',
    'sColumns': Config.COLUNAS[tipo],
    'nro_nota_de': str(nota),
    'flag_cliente': Config.FLAG_CLIENTE,
    'flag_conta': Config.FLAG_CONTA,
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
  session: Session,
  empresa_id: str,
  chave: str,
  tipo: TipoDocumento,
) -> tuple[bytes, bytes]:
  ver_path = 'danfe' if tipo == TipoDocumento.NFE else 'dacte'

  xml_url = f"{Config.URL_BASE}/nfe/download-arquivo/{tipo}/{empresa_id}/{chave}.xml"
  pdf_url = f"{Config.URL_BASE}/nfe/ver-{ver_path}/{tipo}/{empresa_id}/{chave}.pdf"

  response_xml = session.get(xml_url)
  response_xml.raise_for_status()

  response_pdf = session.get(pdf_url)
  response_pdf.raise_for_status()

  return response_xml.content, response_pdf.content


def marcar_flag(
  session: Session,
  codigo_arquivo: str,
) -> None:
  session.post(
    f'{Config.URL_BASE}/nfe/seta-flag/{codigo_arquivo}/{Config.CHECK_FLAG}',
    data={},
  ).raise_for_status()

