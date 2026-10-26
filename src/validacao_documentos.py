"""Confere a integridade básica dos arquivos antes de organizá-los."""

from io import BytesIO

import lxml.etree as etree
from pypdf import PdfReader

from src.enums import TipoDocumento


class DocumentoInvalido(ValueError):
  """Resposta que não permite concluir a baixa com segurança."""


def validar_xml(xml: bytes, tipo: TipoDocumento) -> str:
  """Lê a chave usada na organização; a conferência fiscal cabe ao operador."""
  if not xml or not xml.strip():
    raise DocumentoInvalido('O portal retornou XML vazio.')
  analisador = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True, recover=False)
  try:
    raiz = etree.fromstring(xml, parser=analisador)
  except (etree.XMLSyntaxError, ValueError) as erro:
    raise DocumentoInvalido('O portal não retornou um XML fiscal legível.') from erro
  if raiz.getroottree().docinfo.doctype:
    raise DocumentoInvalido('XML com DTD não é aceito.')

  nfe = tipo == TipoDocumento.NFE
  documento, informacoes = ('NFe', 'infNFe') if nfe else ('CTe', 'infCte')
  namespace = '{http://www.portalfiscal.inf.br/' + str(tipo) + '}'
  processado = 'nfeProc' if nfe else 'cteProc'
  if raiz.tag == namespace + processado:
    documentos = raiz.findall(namespace + documento)
  elif raiz.tag == namespace + documento:
    documentos = [raiz]
  else:
    raise DocumentoInvalido('XML não corresponde ao tipo fiscal solicitado (NF-e/CT-e).')
  if len(documentos) != 1:
    raise DocumentoInvalido('XML deve conter exatamente um documento fiscal.')
  grupos = documentos[0].findall(namespace + informacoes)
  if len(grupos) != 1:
    raise DocumentoInvalido('XML fiscal incompleto ou com identificação ambígua.')
  fiscal = grupos[0]
  identificador = fiscal.get('Id', '')
  chave = identificador[len(documento):]
  if (not identificador.startswith(documento) or len(chave) != 44
      or not chave.isascii() or not chave.isdigit()):
    raise DocumentoInvalido('XML sem chave fiscal válida na identificação.')
  return chave


def validar_pdf(pdf: bytes) -> None:
  """Exige um PDF completo e acessível, sem analisar seu conteúdo fiscal."""
  if not pdf or not pdf.startswith(b'%PDF-') or not pdf.rstrip().endswith(b'%%EOF'):
    raise DocumentoInvalido('O portal retornou PDF vazio, inválido ou incompleto.')
  try:
    with PdfReader(BytesIO(pdf), strict=True) as leitor:
      if leitor.is_encrypted:
        raise DocumentoInvalido('O PDF está protegido e não permite conferir o documento.')
      if not leitor.pages:
        raise DocumentoInvalido('O PDF não contém páginas.')
  except DocumentoInvalido:
    raise
  except Exception as erro:
    raise DocumentoInvalido('O PDF não pôde ser lido para conferir o documento.') from erro
