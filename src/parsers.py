from dataclasses import dataclass, field
from html import unescape
from datetime import datetime

from bs4 import BeautifulSoup
from validate_docbr import CNPJ

from src.utils import (
  upper_strip,
  ano_referencia,
  validate_nfe_row,
  validate_cte_row,
)

TROCAR_LOGIN_URL = 'trocarLogin?vid='
TAMANHO_CHAVE = 22
TAMANHO_CNPJ = 14

@dataclass
class DocumentoFiscal:
  recebimento_quando: str
  emitente_html: str
  data_emissao_html: str
  nota_html: str
  valor_total: str
  dados_brutos: list = field(default_factory=list)
  _html_completo: str = field(init=False, repr=False)
  _texto_limpo: str = field(init=False, repr=False)

  def __post_init__(self):
    self._html_completo = " ".join(str(item) for item in (self.dados_brutos or [
      self.recebimento_quando,
      self.emitente_html,
      self.data_emissao_html,
      self.nota_html,
      self.valor_total
    ]))
    self._texto_limpo = BeautifulSoup(self._html_completo, 'lxml').get_text().lower()

  def html_completo(self) -> str:
    return self._html_completo


@dataclass
class LinhaNFe(DocumentoFiscal):
  @classmethod
  def de_lista(cls, lista: list) -> 'LinhaNFe':
    validate_nfe_row(lista)
    return cls(
      lista[0],
      lista[1],
      lista[2],
      lista[3],
      lista[4],
      dados_brutos=lista
    )


@dataclass
class LinhaCTe(DocumentoFiscal):
  destinatario_html: str = ''

  @classmethod
  def de_lista(cls, lista: list) -> 'LinhaCTe':
    validate_cte_row(lista)
    return cls(
      lista[0],
      lista[1],
      lista[3],
      lista[4],
      lista[5],
      destinatario_html=lista[2],
      dados_brutos=lista
    )


def encontrar_linha(
  linhas: list,
  nota: str,
  mes_atual: int,
  tipo: str
) -> list[DocumentoFiscal]:
  if not linhas:
    raise ValueError('Nenhum dado encontrado')

  fabrica = LinhaCTe if tipo == 'cte' else LinhaNFe
  mes_target = int(mes_atual)
  ano_target = ano_referencia(mes_target)
  matches = []
  target_nota_digits = _extract_digits(nota)

  for item in linhas:
    linha = fabrica.de_lista(item)

    if not _validar_data_linha(
      linha.data_emissao_html,
      mes_target,
      ano_target
    ):
      continue

    if 'c. correção' in linha._texto_limpo or 'carta de correção' in linha._texto_limpo:
      print('Carta de Correção encontrada')
      continue

    if 'cancelada' in linha._texto_limpo or 'cancelamento' in linha._texto_limpo:
      print('Nota Cancelada encontrada')
      continue

    if _matches_nota(linha.nota_html, target_nota_digits):
      matches.append(linha)

  if not matches:
    raise ValueError('Nenhuma foi encontrada')

  return matches


def extrair_dados(linha: DocumentoFiscal) -> dict[str, str]:
  soup = BeautifulSoup(linha._html_completo, 'lxml')

  link_element = soup.select_one('a.linkManifestar[onclick]')
  onclick_attr = link_element.get('onclick') if link_element else None

  chave = _extract_chave(str(onclick_attr) if onclick_attr is not None else None)
  if not chave:
    raise ValueError('Chave da nota não encontrada')

  link_xml = soup.select_one('a.iconeXML[href]')
  url_parts = [p for p in str(link_xml.get('href', '')).split('/') if p] if link_xml else []
  if len(url_parts) < 2:
    raise ValueError('ID da empresa não encontrado')

  div_flag = soup.select_one('div[id^="flagArq"]')
  if not div_flag or not (id_str := div_flag.get('id', '')):
    raise ValueError('Código setaFlag não encontrado')

  emitente = resolve_emitente(linha.emitente_html)
  if not emitente:
    raise ValueError('Emitente não encontrado')

  print('Emitente:', emitente)
  return {
    'chave': chave,
    'empresa_id': url_parts[-2],
    'codigo_arquivo': str(id_str).replace('flagArq', ''),
    'emitente': emitente
  }


def extrair_empresas_href(html_content: str) -> dict[str, str]:
  soup = BeautifulSoup(html_content, 'lxml')
  empresas = {}
  cnpj_validator = CNPJ()

  for link in soup.find_all('a', href=True):
    href = link.get('href', '')
    if not href or TROCAR_LOGIN_URL not in href:
      continue

    vizinho = link.next_sibling
    if vizinho and hasattr(vizinho, 'get_text'):
      texto = vizinho.get_text()
    else:
      texto = str(vizinho) if vizinho else ''

    numeros = _extract_digits(texto)

    if len(numeros) == TAMANHO_CNPJ:
      cnpj = cnpj_validator.mask(numeros)
      empresas[cnpj] = href

  return empresas


def resolve_emitente(emitente_html: str) -> str:
  if not emitente_html:
    return ''

  soup = BeautifulSoup(emitente_html, 'lxml')
  for span in soup.find_all('span'):
    span.decompose()

  emitente_limpo = upper_strip(unescape(soup.get_text(separator=' ')))
  return " ".join(emitente_limpo.split())


def _validar_data_linha(
  data_html: str,
  mes_alvo: int,
  ano_alvo: int
) -> bool:
  texto_data = BeautifulSoup(data_html, 'lxml').get_text().strip().split()
  if not texto_data:
    return False

  for fmt in ('%d/%m/%y', '%d/%m/%Y'):
    try:
      data = datetime.strptime(texto_data[0], fmt)
      return data.month == mes_alvo and data.year == ano_alvo
    except ValueError:
      continue

  return False


def _extract_chave(onclick_text: str | None) -> str | None:
  if not onclick_text:
    return None

  partes = [p.strip('\'"() ') for p in onclick_text.split(',')]
  if len(partes) < 2:
    return None

  id_limpo = partes[1].translate(str.maketrans('', '', ')(;"\'')).strip()

  if len(id_limpo) == TAMANHO_CHAVE:
    return id_limpo

  return None


def _extract_digits(text: str) -> str:
  return ''.join(c for c in text if c.isdigit())


def _matches_nota(html: str, target_nota: str) -> bool:
  texto = BeautifulSoup(html, 'lxml').get_text().strip()
  partes = [p.strip() for p in texto.split('/') if p.strip()]
  id_nota = partes[1] if len(partes) > 1 else texto
  id_nota_limpa = _extract_digits(id_nota)

  target_nota_limpa = _extract_digits(target_nota)

  if id_nota_limpa and target_nota_limpa:
    return int(id_nota_limpa) == int(target_nota_limpa)

  return False

