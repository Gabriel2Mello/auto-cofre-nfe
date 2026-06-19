from datetime import datetime
from html import unescape
import re

from bs4 import BeautifulSoup

RE_CNPJ = re.compile(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}')
RE_DATA = re.compile(r'(\d{2})/(\d{2})/(\d{2})')
RE_NOTA = re.compile(r'/(\d+)/')
RE_EMPRESA_ID = re.compile(r"(?:nfe|cte)/(\d+)/")
RE_CODIGO_ARQUIVO = re.compile(r"setaFlag\(\d+,'(\d+)'\)")
RE_CHAVE_NFE = re.compile(r"chave='([^']+)'|consultarSituacaoNota\(\"empresa\",\"([^\"]+)\"\)")
RE_CHAVE_CTE = re.compile(r'consultarSituacaoNota\("empresa","(.*?)"\)')


def extrair_empresas_href(html_content):
  soup = BeautifulSoup(html_content, 'lxml')
  empresas = {}

  for link in soup.find_all('a', href=True):
    href = link.get('href')

    if not href:
      continue

    if 'trocarLogin?vid=' in href:
      texto_apos_link = link.next_sibling

      if not texto_apos_link:
        continue

      cnpj_match = RE_CNPJ.search(str(texto_apos_link))

      if cnpj_match:
        empresas[cnpj_match.group()] = href

  return empresas


def encontrar_linha(linhas, nota, mes_atual, tipo):
  if not linhas:
    raise RuntimeError(f'Nenhum dado para nota: {nota}')

  hoje = datetime.today()
  ano_atual = hoje.year

  if hoje.month == 1 and mes_atual == 12:
    ano_alvo = (ano_atual - 1) % 100
  else:
    ano_alvo = ano_atual % 100

  for linha in linhas:
    index_emissao, index_nota = (3, 4) if tipo == 'cte' else (2, 3)

    data_match = RE_DATA.search(linha[index_emissao])
    if not data_match:
      continue

    _, mes, ano = map(int, data_match.groups())
    if mes != mes_atual or ano != ano_alvo:
      continue

    nota_match = RE_NOTA.search(linha[index_nota])
    if nota_match and nota_match.group(1) == str(nota):
      return linha

  raise RuntimeError('Nenhuma nota encontrada')


def resolve_emitente(emitente_html: str) -> str:
  emitente_antes_do_br = (
    re.split(r'<br', emitente_html, flags=re.IGNORECASE)[0]
  )
  emitente_limpo = re.sub(r'<[^>]+>', ' ', emitente_antes_do_br)

  emitente = unescape(emitente_limpo).strip().upper()
  emitente = " ".join(emitente.split())

  return emitente


def extrair_dados(linha, tipo):
  html_content = " ".join(map(str, linha))

  try:
    re_chave = RE_CHAVE_CTE if tipo == 'cte' else RE_CHAVE_NFE
    chave_match = re_chave.search(html_content)
    if not chave_match:
      raise RuntimeError('Chave da nota não encontrada')

    chave = next((g for g in chave_match.groups() if g is not None), None)
    if not chave:
      raise RuntimeError('Chave da nota não capturada')

    empresa_match = RE_EMPRESA_ID.search(html_content)
    if not empresa_match:
      raise RuntimeError('ID da empresa não encontrado')

    empresa_id = empresa_match.group(1)

    codigo_arquivo_match = RE_CODIGO_ARQUIVO.search(html_content)
    if not codigo_arquivo_match:
      raise RuntimeError('Código setaFlag não encontrado')

    codigo_arquivo = codigo_arquivo_match.group(1)

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

