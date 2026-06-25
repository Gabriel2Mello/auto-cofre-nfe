from dataclasses import dataclass, field
from datetime import datetime
from html import unescape
import re
from typing import Pattern

from bs4 import BeautifulSoup

RE_CNPJ: Pattern[str] = re.compile(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}')
RE_DATA: Pattern[str] = re.compile(r'(\d{2})/(\d{2})/(\d{2,4})')
RE_NOTA: Pattern[str] = re.compile(r'/(\d+)/')
RE_EMPRESA_ID: Pattern[str] = re.compile(r"(?:nfe|cte)/(\d+)/")
RE_CODIGO_ARQUIVO: Pattern[str] = re.compile(r"setaFlag\(\d+,'(\d+)'\)")
RE_CHAVE_NFE: Pattern[str] = re.compile(r"(?:chave='([^']+)'|consultarSituacaoNota\(\"empresa\",\"([^\"]+)\"\))")
RE_CHAVE_CTE: Pattern[str] = re.compile(r'consultarSituacaoNota\("empresa","(.*?)"\)')


@dataclass
class DocumentoFiscal:
  recebimento_quando: str
  emitente_html: str
  data_emissao_html: str
  nota_html: str
  valor_total: str
  dados_brutos: list = field(default_factory=list)

  def html_completo(self) -> str:
    if self.dados_brutos:
      return " ".join(str(item) for item in self.dados_brutos)
    return " ".join(str(v) for v in self.__dict__.values())

@dataclass
class LinhaNFe(DocumentoFiscal):
  @classmethod
  def de_lista(cls, lista: list) -> 'LinhaNFe':
    if len(lista) < 5:
      raise ValueError('Malformed raw NFe row')
    return cls(
      recebimento_quando=lista[0],
      emitente_html=lista[1],
      data_emissao_html=lista[2],
      nota_html=lista[3],
      valor_total=lista[4],
      dados_brutos=lista
    )

@dataclass
class LinhaCTe(DocumentoFiscal):
  destinatario_html: str = ""

  @classmethod
  def de_lista(cls, lista: list) -> 'LinhaCTe':
    if len(lista) < 6:
      raise ValueError('Malformed raw CTe row')
    return cls(
      recebimento_quando=lista[0],
      emitente_html=lista[1],
      data_emissao_html=lista[3],
      nota_html=lista[4],
      valor_total=lista[5],
      destinatario_html=lista[2],
      dados_brutos=lista
    )


def extrair_empresas_href(html_content: str) -> dict[str, str]:
  soup = BeautifulSoup(html_content, 'lxml')
  empresas = {}

  for link in soup.find_all('a', href=True):

    href = link.get('href')
    if not href or 'trocarLogin?vid=' not in href:
      continue

    texto_apos_link = link.next_sibling
    if not texto_apos_link:
      continue

    cnpj_match = RE_CNPJ.search(str(texto_apos_link))
    if cnpj_match:
      empresas[cnpj_match.group()] = href

  return empresas


def _validar_data_linha(data: str, mes_alvo: int, ano_alvo: int) -> bool:
  data_match = RE_DATA.search(data)
  if not data_match:
    return False

  _, mes_str, ano_str = data_match.groups()
  mes = int(mes_str)
  ano = int(ano_str)

  if ano < 100:
    ano += 2000

  return mes == mes_alvo and ano == ano_alvo


def _extrair_campo_regex(regex: Pattern[str], texto: str, erro_msg: str) -> str:
  match = regex.search(texto)
  if not match:
    raise RuntimeError(erro_msg)

  for group in match.groups():
    if group is not None:
      return group

  raise RuntimeError(erro_msg)


def encontrar_linha(linhas: list, nota: str, mes_atual: int, tipo: str) -> list:
  if not linhas:
    raise RuntimeError(f'Nenhum dado para nota: {nota}')

  fabrica_documento = LinhaCTe if tipo == 'cte' else LinhaNFe

  mes_target = int(mes_atual)
  hoje = datetime.today()
  ano_target = hoje.year - 1 if (hoje.month == 1 and mes_target == 12) else hoje.year

  linhas_encontradas = []

  for linha in linhas:
    objeto_linha = fabrica_documento.de_lista(linha)

    if not _validar_data_linha(objeto_linha.data_emissao_html, mes_target, ano_target):
      continue

    nota_match = RE_NOTA.search(objeto_linha.nota_html)
    if nota_match:
      id_nota = next((g for g in nota_match.groups() if g is not None), None)
      if id_nota == str(nota):
        linhas_encontradas.append(objeto_linha)

  if not linhas_encontradas:
    raise RuntimeError('Nenhuma nota encontrada')

  return linhas_encontradas


def resolve_emitente(emitente_html: str) -> str:
  emitente_antes_do_br = (
    re.split(r'<br', emitente_html, flags=re.IGNORECASE)[0]
  )
  emitente_limpo = re.sub(r'<[^>]+>', ' ', emitente_antes_do_br)

  emitente = unescape(emitente_limpo).strip().upper()
  return " ".join(emitente.split())


def extrair_dados(linha: DocumentoFiscal, tipo: str) -> dict[str, str]:
  html_content = linha.html_completo()

  try:
    chave = _extrair_campo_regex(
      RE_CHAVE_CTE if tipo == 'cte' else RE_CHAVE_NFE,
      html_content,
      'Chave da nota não encontrada'
    )
    empresa_id = _extrair_campo_regex(
      RE_EMPRESA_ID,
      html_content,
      'ID da empresa não encontrado'
    )
    codigo_arquivo = _extrair_campo_regex(
      RE_CODIGO_ARQUIVO,
      html_content,
      'Código setaFlag não encontrado'
    )

    emitente = resolve_emitente(linha.emitente_html)
    if not emitente:
      raise RuntimeError('Emitente não encontrado')

    print('Emitente:', emitente)
    return {
      'chave': chave,
      'empresa_id': empresa_id,
      'codigo_arquivo': codigo_arquivo,
      'emitente': emitente
    }

  except Exception as e:
    raise RuntimeError(f'Erro ao processar {tipo}: {str(e)}')

