from urllib.parse import urljoin, urlsplit
import json
from time import sleep
from collections.abc import Callable
from requests import Session

from validate_docbr import CNPJ

from src.interface import escolher_emitente
from src.config import Config
from src.diagnostico_portal import etapa_portal, registrar_resposta, registrar_confirmacao
from src.enums import TipoDocumento, Empresa
from src.parsers import (DocumentoFiscal, encontrar_linha, extrair_dados,
                         confirmar_empresa_ativa, confirmar_flag)
from src.validacao_documentos import DocumentoInvalido, validar_xml, validar_pdf


def processar_nota(
  session: Session,
  nota: str,
  tipo: TipoDocumento,
  mes_nota: int,
  ano_nota: int,
  selecionar_emitente: Callable[[list[DocumentoFiscal]], DocumentoFiscal] = escolher_emitente,
) -> dict[str, str]:
  linhas = carregar_dados(session, nota, tipo)
  linhas_validas = encontrar_linha(
    linhas,
    nota,
    mes_nota,
    ano_nota,
    tipo,
  )

  if len(linhas_validas) == 1:
    linha = linhas_validas[0]
  else:
    linha = selecionar_emitente(linhas_validas)

  return extrair_dados(linha)


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


@etapa_portal('troca_empresa')
def trocar_empresa(
  session: Session,
  empresa: Empresa,
  empresas_href: dict[str, str],
  cnpj: str,
) -> None:
  cnpj_validator = CNPJ()

  cnpj_formatado = cnpj_validator.mask(cnpj)
  if not (empresa_link := empresas_href.get(cnpj_formatado)):
    registrar_confirmacao('vinculo_ausente')
    raise ValueError(f"Link da empresa '{empresa}' não encontrado")

  destino = urljoin(Config.URL_BASE, empresa_link)
  origem = urlsplit(Config.URL_BASE)
  if (urlsplit(destino).scheme, urlsplit(destino).netloc) != (origem.scheme, origem.netloc):
    registrar_confirmacao('origem_invalida')
    raise ValueError('Link de troca de empresa fora do portal. O lote não foi iniciado.')
  response = session.get(
    url=destino,
    headers={'Referer': f'{Config.URL_BASE}/login/enviar'},
    allow_redirects=True,
  )
  registrar_resposta('troca_empresa', response)
  response.raise_for_status()
  if (response.status_code != 200
      or (urlsplit(response.url).scheme, urlsplit(response.url).netloc) != (origem.scheme, origem.netloc)):
    registrar_confirmacao('resposta_invalida')
    raise ValueError('Não foi possível confirmar a troca de empresa. O lote não foi iniciado.')
  confirmar_empresa_ativa(response.text, cnpj)


def carregar_dados(
  session: Session,
  nota: str,
  tipo: TipoDocumento,
) -> list[list[str]]:
  endpoint = f'ver-arquivos-{tipo}'

  payload = {
    'sEcho': '1',
    'iColumns': '7' if tipo == TipoDocumento.NFE else '8',
    'sColumns': Config.COLUNAS[tipo],
    'nro_nota_de': str(nota),
    'nro_nota_ate': str(nota),
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

  linhas: list[list[str]] = []
  paginas = set()
  total_esperado = None
  while True:
    payload['iDisplayStart'] = str(len(linhas))
    response = session.post(
      url=f'{Config.URL_BASE}/nfe/empresa/{endpoint}/load',
      headers=headers,
      data=dict(payload),
      allow_redirects=False,
    )
    response.raise_for_status()
    if response.status_code != 200:
      raise ValueError('Consulta não concluída. Confira a sessão no portal.')
    try:
      dados = response.json()
    except ValueError:
      raise ValueError('O portal não retornou uma consulta de documentos válida.') from None
    if not isinstance(dados, dict) or not isinstance(dados.get('aaData'), list):
      raise ValueError('O portal não retornou uma consulta de documentos válida.')
    pagina = dados['aaData']
    if (len(pagina) > 25 or any(not isinstance(linha, list)
        or any(not isinstance(campo, str) for campo in linha) for linha in pagina)):
      raise ValueError('Página de documentos inválida. A seleção não foi concluída.')
    total = dados.get('iTotalDisplayRecords')
    if isinstance(total, str) and total.isascii() and total.isdigit():
      total = int(total)
    if total is not None and (type(total) is not int or total < 0):
      raise ValueError('Total de documentos inválido. A seleção não foi concluída.')
    if not linhas:
      total_esperado = total
    if total != total_esperado or (total is not None and len(linhas) + len(pagina) > total):
      raise ValueError('A consulta mudou durante a paginação. Confira e consulte novamente.')
    if not pagina:
      if total is not None and len(linhas) != total:
        raise ValueError('A consulta ficou incompleta. Nenhum documento foi selecionado.')
      return linhas
    assinatura = json.dumps(pagina, ensure_ascii=False)
    if assinatura in paginas:
      raise ValueError('O portal repetiu uma página. A seleção não foi concluída.')
    paginas.add(assinatura)
    linhas.extend(pagina)
    if total is not None and len(linhas) == total:
      return linhas
    if total is None and len(pagina) < 25:
      return linhas


def baixar_arquivos(
  session: Session,
  empresa_id: str,
  chave: str,
  tipo: TipoDocumento,
  *,
  nota: str,
  cnpj_empresa: str,
  mes_nota: int,
  ano_nota: int,
) -> tuple[bytes, bytes]:
  ver_path = 'danfe' if tipo == TipoDocumento.NFE else 'dacte'

  xml_url = f"{Config.URL_BASE}/nfe/download-arquivo/{tipo}/{empresa_id}/{chave}.xml"
  pdf_url = f"{Config.URL_BASE}/nfe/ver-{ver_path}/{tipo}/{empresa_id}/{chave}.pdf"

  response_xml = session.get(xml_url, allow_redirects=False)
  response_xml.raise_for_status()
  if response_xml.status_code != 200:
    raise DocumentoInvalido('Download do XML não foi concluído (redirecionamento ou resposta parcial). Confira a sessão no portal.')
  validar_xml(response_xml.content, tipo)

  response_pdf = session.get(pdf_url, allow_redirects=False)
  response_pdf.raise_for_status()
  if response_pdf.status_code != 200:
    raise DocumentoInvalido('Download do PDF não foi concluído (redirecionamento ou resposta parcial). Confira a sessão no portal.')
  validar_pdf(response_pdf.content)

  return response_xml.content, response_pdf.content


def marcar_flag(
  session: Session,
  codigo_arquivo: str,
  *,
  nota: str,
  tipo: TipoDocumento,
) -> None:
  response = session.post(
    f'{Config.URL_BASE}/nfe/seta-flag/{codigo_arquivo}/{Config.CHECK_FLAG}',
    data={},
    allow_redirects=False,
  )
  response.raise_for_status()
  if response.status_code != 200:
    raise RuntimeError('O portal não confirmou a solicitação de marcação. Confira a sessão e a sinalização.')
  # O indicador relido no servidor é a confirmação, inclusive quando a ação
  # retorna corpo vazio. Nunca repetir a escrita para conferir a resposta.
  confirmar_flag(carregar_dados(session, nota, tipo), codigo_arquivo, Config.CHECK_FLAG)

