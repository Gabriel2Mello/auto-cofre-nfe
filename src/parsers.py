from datetime import datetime
from html import unescape
import re

from bs4 import BeautifulSoup

RE_CNPJ = re.compile(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}')
RE_DATA = re.compile(r'(\d{2})/(\d{2})/(\d{2,4})')
RE_NOTA = re.compile(r'/(\d+)/')
RE_EMPRESA_ID = re.compile(r"(?:nfe|cte)/(\d+)/")
RE_CODIGO_ARQUIVO = re.compile(r"setaFlag\(\d+,'(\d+)'\)")
RE_CHAVE_NFE = re.compile(r"(?:chave='([^']+)'|consultarSituacaoNota\(\"empresa\",\"([^\"]+)\"\))")
RE_CHAVE_CTE = re.compile(r'consultarSituacaoNota\("empresa","(.*?)"\)')


def extrair_empresas_href(html_content):
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


def _validar_data_linha(data, mes_alvo, ano_alvo) -> bool:
  data_match = RE_DATA.search(data)
  if not data_match:
    return False

  _, mes, ano_str = data_match.groups()
  mes = int(mes)
  ano = int(ano_str)

  if ano < 100:
    ano += 2000

  return mes == mes_alvo and ano == ano_alvo


def _extrair_campo_regex(regex, texto, erro_msg):
  match = regex.search(texto)
  if not match:
    raise RuntimeError(erro_msg)

  val = next((g for g in match.groups() if g is not None), None)
  if not val:
    raise RuntimeError(erro_msg)

  return val


def encontrar_linha(linhas, nota, mes_atual, tipo):
  if not linhas:
    raise RuntimeError(f'Nenhum dado para nota: {nota}')

  mes_alvo = int(mes_atual)
  hoje = datetime.today()
  ano_alvo = hoje.year - 1 if (hoje.month == 1 and mes_alvo == 12) else hoje.year

  linhas_encontradas = []

  for linha in linhas:
    index_emissao, index_nota = (3, 4) if tipo == 'cte' else (2, 3)

    if not _validar_data_linha(linha[index_emissao], mes_alvo, ano_alvo):
      continue

    nota_match = RE_NOTA.search(linha[index_nota])
    if nota_match:
      id_nota = next((g for g in nota_match.groups() if g is not None), None)
      if id_nota == str(nota):
        linhas_encontradas.append(linha)

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


def extrair_dados(linha, tipo):
  html_content = " ".join(map(str, linha))

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

    emitente = resolve_emitente(str(linha[1]))
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

