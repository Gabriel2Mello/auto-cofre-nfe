"""Confere formato e identidade antes de persistir documentos do portal."""

from datetime import date, datetime
from io import BytesIO
import re

import lxml.etree as etree
from pypdf import PdfReader

from src.enums import TipoDocumento


class DocumentoInvalido(ValueError):
  """Resposta que não permite concluir a baixa com segurança."""


def _texto(elemento: etree._Element, caminho: str) -> str:
  campos = elemento.findall(caminho)
  if len(campos) != 1 or not campos[0].text or not campos[0].text.strip():
    raise DocumentoInvalido('XML fiscal incompleto ou com identificação ambígua.')
  return campos[0].text.strip()


def _cnpj(valor: str) -> str:
  return valor.translate(str.maketrans('', '', './- ')).strip()


def validar_xml(xml: bytes, tipo: TipoDocumento, *, nota: str, cnpj_empresa: str,
                mes_nota: int, ano_nota: int) -> str:
  """Retorna a chave fiscal do XML; o ID de 22 caracteres do portal é distinto."""
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
  documento, informacoes, campo_numero, modelo = ('NFe', 'infNFe', 'nNF', '55') if nfe else ('CTe', 'infCte', 'nCT', '57')
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
  ide = namespace + 'ide/' + namespace
  numero = _texto(fiscal, ide + campo_numero)
  if (not numero.isascii() or not numero.isdigit() or len(numero) > 9
      or not nota.isascii() or not nota.isdigit() or int(numero) != int(nota)):
    raise DocumentoInvalido('O número do XML diverge do documento solicitado.')
  if _texto(fiscal, ide + 'mod') != modelo:
    raise DocumentoInvalido('O modelo do XML diverge do tipo solicitado.')
  try:
    if fiscal.find(ide + 'dhEmi') is not None:
      emissao = datetime.fromisoformat(_texto(fiscal, ide + 'dhEmi')).date()
    else:
      emissao = date.fromisoformat(_texto(fiscal, ide + 'dEmi'))
  except ValueError as erro:
    raise DocumentoInvalido('XML sem data de emissão válida.') from erro
  if (emissao.month, emissao.year) != (mes_nota, ano_nota):
    raise DocumentoInvalido('A competência do XML diverge da competência solicitada.')

  identificador = fiscal.get('Id', '')
  chave = identificador[len(documento):]
  if (not identificador.startswith(documento) or len(chave) != 44
      or not chave.isascii() or not chave.isdigit()):
    raise DocumentoInvalido('XML sem chave fiscal válida na identificação.')
  emitente = _texto(fiscal, namespace + 'emit/' + namespace + 'CNPJ')
  serie = _texto(fiscal, ide + 'serie')
  if (chave[20:22] != modelo or int(chave[25:34]) != int(numero)
      or chave[6:20] != emitente or chave[2:6] != emissao.strftime('%y%m')
      or chave[:2] != _texto(fiscal, ide + 'cUF') or chave[22:25] != serie.zfill(3)):
    raise DocumentoInvalido('A chave fiscal diverge dos dados do XML.')
  if raiz.tag == namespace + processado:
    protocolo, campo_chave = ('protNFe', 'chNFe') if nfe else ('protCTe', 'chCTe')
    if _texto(raiz, namespace + protocolo + '/' + namespace + 'infProt/' + namespace + campo_chave) != chave:
      raise DocumentoInvalido('O protocolo do XML corresponde a outro documento.')

  empresa = _cnpj(cnpj_empresa)
  if len(empresa) != 14 or not empresa.isascii() or not empresa.isdigit():
    raise DocumentoInvalido('CNPJ da empresa selecionada não está configurado corretamente.')
  # A empresa deve participar do documento; autXML não estabelece esse vínculo.
  participantes = ['emit', 'dest'] if nfe else ['emit', 'rem', 'exped', 'receb', 'dest', 'toma4', 'ide/' + namespace + 'toma4']
  cnpjs = {campo.text.strip() for participante in participantes
           for campo in fiscal.findall(namespace + participante + '/' + namespace + 'CNPJ') if campo.text}
  if empresa not in cnpjs:
    raise DocumentoInvalido('O XML não pertence à empresa selecionada como participante fiscal.')
  return chave


def validar_pdf(pdf: bytes, chave: str) -> None:
  if not pdf or not pdf.startswith(b'%PDF-') or not pdf.rstrip().endswith(b'%%EOF'):
    raise DocumentoInvalido('O portal retornou PDF vazio, inválido ou incompleto.')
  try:
    with PdfReader(BytesIO(pdf), strict=True) as leitor:
      if leitor.is_encrypted:
        raise DocumentoInvalido('O PDF está protegido e não permite conferir o documento.')
      if not leitor.pages:
        raise DocumentoInvalido('O PDF não contém páginas.')
      textos = [pagina.extract_text() or '' for pagina in leitor.pages]
  except DocumentoInvalido:
    raise
  except Exception as erro:
    raise DocumentoInvalido('O PDF não pôde ser lido para conferir o documento.') from erro
  # DANFE/DACTE pode apresentar a chave contínua ou agrupada em blocos de quatro.
  chaves = {''.join(c for c in trecho if c.isdigit())
            for texto in textos
            for trecho in re.findall(r'(?<![0-9])(?:[0-9]{4}\s*){10}[0-9]{4}(?![0-9])', texto)}
  rotulo = 'DANFE' if chave[20:22] == '55' else 'DACTE'
  if rotulo not in ''.join(' '.join(textos).upper().split()):
    raise DocumentoInvalido('O PDF não identifica o tipo de documento auxiliar esperado (DANFE/DACTE).')
  chaves_do_modelo = {identidade for identidade in chaves if identidade[20:22] == chave[20:22]}
  if chaves_do_modelo != {chave}:
    raise DocumentoInvalido('O PDF não permite identificar uma única chave fiscal correspondente ao XML em texto legível. Confira o download no portal.')
