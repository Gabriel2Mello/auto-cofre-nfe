"""Documentos mínimos para testar formato e identidade, sem valor fiscal."""

from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from src.enums import TipoDocumento

CNPJ_EMPRESA = '00000000000100'
CNPJ_EMITENTE = '00000000000200'
CNPJ_FISCO = '00000000000400'
CPF_EMITENTE = '00000000001'
ID_PORTAL = 'P' * 22


def chave_fiscal(tipo=TipoDocumento.NFE, numero='123', cnpj=CNPJ_EMITENTE, competencia='2610', serie='1'):
  modelo = '55' if tipo == TipoDocumento.NFE else '57'
  base = f'35{competencia}{cnpj}{modelo}{int(serie):03d}{int(numero):09d}112345678'
  soma = sum(int(digito) * (2 + indice % 8) for indice, digito in enumerate(reversed(base)))
  resto = soma % 11
  return base + str(0 if resto < 2 else 11 - resto)


def xml_fiscal(tipo=TipoDocumento.NFE, numero='123', empresa=CNPJ_EMPRESA,
               chave=None, emissao='2026-10-01T12:00:00-03:00', processado=True):
  nfe = tipo == TipoDocumento.NFE
  documento, informacoes, campo_numero = ('NFe', 'infNFe', 'nNF') if nfe else ('CTe', 'infCte', 'nCT')
  namespace = 'http://www.portalfiscal.inf.br/' + str(tipo)
  chave = chave or chave_fiscal(tipo, numero)
  conteudo = f'''<{documento} xmlns="{namespace}"><{informacoes} Id="{documento}{chave}" versao="4.00">
    <ide><cUF>35</cUF><mod>{'55' if nfe else '57'}</mod><serie>1</serie>
      <{campo_numero}>{numero}</{campo_numero}><dhEmi>{emissao}</dhEmi></ide>
    <emit><CNPJ>{CNPJ_EMITENTE}</CNPJ><xNome>EMITENTE FICTICIO</xNome></emit>
    <dest><CNPJ>{empresa}</CNPJ><xNome>EMPRESA FICTICIA</xNome></dest>
  </{informacoes}></{documento}>'''
  if processado:
    raiz = 'nfeProc' if nfe else 'cteProc'
    protocolo, campo_chave = ('protNFe', 'chNFe') if nfe else ('protCTe', 'chCTe')
    conteudo = f'<{raiz} xmlns="{namespace}">{conteudo}<{protocolo}><infProt><{campo_chave}>{chave}</{campo_chave}></infProt></{protocolo}></{raiz}>'
  return conteudo.encode()


def xml_avulsa(serie='890', processado=True):
  chave = chave_fiscal(cnpj=CNPJ_FISCO, serie=serie)
  return (xml_fiscal(chave=chave, processado=processado)
          .replace(b'<serie>1</serie>', f'<serie>{serie}</serie>'.encode())
          .replace(b'</ide>', b'<procEmi>1</procEmi></ide>')
          .replace(b'<dest>', f'<avulsa><CNPJ>{CNPJ_FISCO}</CNPJ><xOrgao>FISCO FICTICIO</xOrgao></avulsa><dest>'.encode()))


def xml_emitente_cpf(serie='910', processado=True):
  if 890 <= int(serie) <= 899:
    xml = xml_avulsa(serie, processado)
  else:
    chave = chave_fiscal(cnpj=CPF_EMITENTE.zfill(14), serie=serie)
    xml = (xml_fiscal(chave=chave, processado=processado)
           .replace(b'<serie>1</serie>', f'<serie>{serie}</serie>'.encode())
           .replace(b'</ide>', b'<procEmi>1</procEmi></ide>' if int(serie) < 920 else b'<procEmi>0</procEmi></ide>'))
  return xml.replace(f'<CNPJ>{CNPJ_EMITENTE}</CNPJ>'.encode(),
                     f'<CPF>{CPF_EMITENTE}</CPF>'.encode())


def pdf_fiscal(chave=None, texto=None, sem_paginas=False, senha=None, rotulo=None):
  escritor = PdfWriter()
  if not sem_paginas:
    pagina = escritor.add_blank_page(width=600, height=200)
    fonte = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                             NameObject('/Subtype'): NameObject('/Type1'),
                             NameObject('/BaseFont'): NameObject('/Helvetica')})
    pagina[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): fonte})})
    conteudo = DecodedStreamObject()
    chave = chave or chave_fiscal()
    texto = texto if texto is not None else chave
    if texto:
      texto = (rotulo or ('DANFE' if chave[20:22] == '55' else 'DACTE')) + ' ' + texto
    conteudo.set_data(f'BT /F1 10 Tf 10 100 Td ({texto}) Tj ET'.encode('ascii'))
    pagina.replace_contents(conteudo.flate_encode())
  if senha:
    escritor.encrypt(senha)
  destino = BytesIO()
  escritor.write(destino)
  return destino.getvalue()
