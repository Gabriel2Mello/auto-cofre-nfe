from dataclasses import dataclass, field
from functools import cached_property
from html import unescape
import json
import re

from dateutil import parser
from bs4 import BeautifulSoup, Tag
from validate_docbr import CNPJ

from src.enums import TipoDocumento
from src.config import Config
from src.diagnostico_portal import registrar_confirmacao
from src.utils import upper_strip, extract_digits


class NotaNaoEncontrada(RuntimeError):
  """A consulta não retornou documento elegível para a nota solicitada."""


@dataclass
class DocumentoFiscal:
  recebimento_quando: str
  emitente_html: str
  data_emissao_html: str
  nota_html: str
  valor_total: str
  dados_brutos: list = field(default_factory=list, kw_only=True)

  @cached_property
  def html_completo(self) -> str:
    html_data = self.dados_brutos or [
      self.recebimento_quando,
      self.emitente_html,
      self.data_emissao_html,
      self.nota_html,
      self.valor_total
    ]
    return " ".join(map(str, html_data))

  @cached_property
  def soup(self) -> BeautifulSoup:
    return BeautifulSoup(self.html_completo, 'lxml')

  @cached_property
  def texto_limpo(self) -> str:
    return self.soup.get_text().lower()


@dataclass
class LinhaNFe(DocumentoFiscal):
  @classmethod
  def de_lista(cls, lista: list) -> 'LinhaNFe':
    if len(lista) < 5:
      raise ValueError('Linha NFe requer 5+ campos')
    return cls(*lista[:5], dados_brutos=lista)


@dataclass
class LinhaCTe(DocumentoFiscal):
  destinatario_html: str = ''

  @classmethod
  def de_lista(cls, lista: list) -> 'LinhaCTe':
    if len(lista) < 6:
      raise ValueError('Linha CTe requer 6+ campos')
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
  linhas: list[list[str]],
  nota: str,
  mes_nota: int,
  ano_nota: int,
  tipo: TipoDocumento
) -> list[DocumentoFiscal]:
  if not linhas:
    raise NotaNaoEncontrada('Nenhuma nota encontrada')

  fabrica = LinhaCTe if tipo == TipoDocumento.CTE else LinhaNFe
  matches = []
  target_nota_digits = extract_digits(nota)

  for item in linhas:
    linha = fabrica.de_lista(item)

    if not _validar_data_linha(linha.data_emissao_html, mes_nota, ano_nota):
      continue

    if any(x in linha.texto_limpo for x in ['c. correção', 'carta de correção']):
      print('Carta de Correção encontrada')
      continue

    if any(x in linha.texto_limpo for x in ['cancelada', 'cancelamento']):
      print('Nota Cancelada encontrada')
      continue

    if _matches_nota(linha.nota_html, target_nota_digits):
      matches.append(linha)

  if not matches:
    raise NotaNaoEncontrada('Nenhuma nota encontrada')

  return matches


def extrair_dados(linha: DocumentoFiscal) -> dict[str, str]:
  chave = _extrair_chave_portal(linha.soup)

  link_xml = linha.soup.select_one('a.iconeXML[href]')
  url_parts = [p for p in str(link_xml.get('href', '')).split('/') if p] if link_xml else []
  if len(url_parts) < 2:
    raise ValueError('ID da empresa não encontrado')

  div_flag = linha.soup.select_one('div[id^="flagArq"]')
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


def _extrair_chave_portal(soup: BeautifulSoup) -> str:
  # HTML observado em NF-e e CT-e: eventos declarativos com argumentos JSON.
  links = soup.select('a.linkManifestar[data-on-click="consultarSituacaoNota"], '
                      'a.linkManifestar[data-on-click="manifestarNFE"]')
  if links:
    chaves = set()
    for link in links:
      try:
        argumentos = json.loads(str(link.get('data-on-click-args', '')))
      except (ValueError, TypeError):
        raise ValueError('Não foi possível identificar a chave da nota no Cofre.') from None
      if (not isinstance(argumentos, list) or len(argumentos) != 2
          or argumentos[0] != 'empresa' or not isinstance(argumentos[1], str)):
        raise ValueError('Não foi possível identificar a chave da nota no Cofre.')
      chave = argumentos[1]
      if link.get('data-on-click') == 'manifestarNFE':
        partes = chave.split('/')
        if len(partes) != 2 or not re.fullmatch(r'[0-9]+', partes[0]):
          raise ValueError('Não foi possível identificar a chave da nota no Cofre.')
        chave = partes[1]
      if not re.fullmatch(r'[A-Za-z0-9]{' + str(Config.TAMANHO_CHAVE) + r'}', chave):
        raise ValueError('Chave da nota não encontrada')
      chaves.add(chave)
    if len(chaves) != 1:
      raise ValueError('Identificadores da nota divergentes no Cofre.')
    return chaves.pop()

  # Compatibilidade com as respostas anteriores do portal.
  link_element = soup.select_one('a.linkManifestar[onclick]')

  onclick_attr = link_element.get('onclick') if link_element else None
  if not onclick_attr:
    raise ValueError('Não foi possível identificar a chave da nota no Cofre.')

  chave = _extract_chave(str(onclick_attr), Config.TAMANHO_CHAVE)
  if not chave:
    raise ValueError('Chave da nota não encontrada')

  return chave


def extrair_empresas_href(html_content: str) -> dict[str, str]:
  soup = BeautifulSoup(html_content, 'lxml')
  empresas = {}
  cnpj_validator = CNPJ()

  for link in soup.find_all('a', href=True):
    href = link.get('href', '')
    if not href or Config.TROCAR_LOGIN_URL not in href:
      continue

    vizinho = link.next_sibling

    if isinstance(vizinho, Tag):
      texto = vizinho.get_text()
    else:
      texto = str(vizinho) if vizinho else ''

    numeros = extract_digits(texto)

    if len(numeros) == Config.TAMANHO_CNPJ:
      cnpj = cnpj_validator.mask(numeros)
      empresas[cnpj] = href

  return empresas


def confirmar_empresa_ativa(html: str, cnpj: str) -> None:
  # Contrato observado no portal: o cabeçalho identifica o contexto ativo;
  # a lista de vínculos do login não comprova que a troca aconteceu.
  soup = BeautifulSoup(html, 'lxml')
  cabecalhos = soup.select('#mws-header-container > span')
  esperado = extract_digits(cnpj)
  configuracao_valida = len(esperado) == 14 and esperado.isascii()
  encontrados = re.findall(r'\(\s*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\s*\)',
                            cabecalhos[0].get_text(' ', strip=True)) if len(cabecalhos) == 1 else []
  if not configuracao_valida:
    motivo = 'configuracao_invalida'
  elif not cabecalhos:
    motivo = 'cabecalho_ausente'
  elif len(cabecalhos) != 1:
    motivo = 'cabecalho_ambiguo'
  elif len(encontrados) != 1:
    motivo = 'cnpj_ausente' if not encontrados else 'cnpj_ambiguo'
  elif extract_digits(encontrados[0]) != esperado:
    motivo = 'cnpj_divergente'
  else:
    motivo = 'confirmado'
  registrar_confirmacao(motivo, len(soup.select('#mws-header-container')),
                       len(cabecalhos), len(encontrados), configuracao_valida)
  if len(cabecalhos) != 1 or not configuracao_valida:
    raise ValueError('Não foi possível confirmar a empresa ativa no portal. O lote não foi iniciado.')
  if len(encontrados) != 1 or extract_digits(encontrados[0]) != esperado:
    raise ValueError('A empresa ativa no portal não corresponde à solicitada ou não pôde ser confirmada. O lote não foi iniciado.')


def confirmar_flag(linhas: list[list[str]], codigo_arquivo: str, flag: int) -> None:
  marcacoes = []
  for linha in linhas:
    soup = BeautifulSoup(' '.join(linha), 'lxml')
    marcacoes.extend(soup.find_all('div', id='flagArq' + codigo_arquivo))
  if len(marcacoes) != 1 or f'flag{flag}' not in marcacoes[0].get('class', []):
    raise RuntimeError('Não foi possível confirmar a marcação do documento na consulta ao portal.')


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
  mes_nota: int,
  ano_nota: int,
) -> bool:
  soup = BeautifulSoup(data_html, 'lxml')
  texto_data = soup.get_text().strip().split()

  if not texto_data:
    return False

  try:
    data = parser.parse(texto_data[0], dayfirst=True)
    return data.month == mes_nota and data.year == ano_nota
  except (parser.ParserError, ValueError):
    return False


def _extract_chave(onclick_text: str, tamanho_chave: int) -> str | None:
  partes = onclick_text.split(',')
  if len(partes) < 2:
    return None

  id_limpo = "".join(c for c in partes[1] if c.isalnum())
  if len(id_limpo) == tamanho_chave:
    return id_limpo

  return None


def _matches_nota(html: str, target_nota: str) -> bool:
  texto = BeautifulSoup(html, 'lxml').get_text().strip()
  partes = [p.strip() for p in texto.split('/') if p.strip()]
  id_nota = partes[1] if len(partes) > 1 else texto

  id_nota_limpa = extract_digits(id_nota)
  target_nota_limpa = extract_digits(target_nota)

  if id_nota_limpa and target_nota_limpa:
    return int(id_nota_limpa) == int(target_nota_limpa)

  return False

