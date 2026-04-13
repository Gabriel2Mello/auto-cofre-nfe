import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.config import (
    CONTENT_TYPE,
    REQUESTED_WITH,
    USER_AGENT,
    ACCEPT,
    URL_BASE,
    COLUNAS,
    CNPJ_MATRIZ,
    SENHA_COFRE,
    CNPJ
)

RE_CNPJ = re.compile(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}')
RE_DATA = re.compile(r'(\d{2})/(\d{2})/(\d{2})')
RE_NOTA = re.compile(r'/(\d+)/')
RE_EMPRESA_ID = re.compile(r"(?:nfe|cte)/(\d+)/")
RE_CODIGO_ARQUIVO = re.compile(r"setaFlag\(\d+,'(\d+)'\)")


def login(session):
    session.headers.update({
        'User-Agent': USER_AGENT,
        'Origin': URL_BASE,
        'Content-Type': CONTENT_TYPE
    })

    payload = {
        's': 'nfe',
        'cpf': CNPJ_MATRIZ,
        'senha': SENHA_COFRE
    }

    response = session.post(
        url=f'{URL_BASE}/login/enviar',
        data=payload,
        headers={'Referer': f'{URL_BASE}/login'},
        allow_redirects=True
    )
    response.raise_for_status()

    return response.text


def ver_arquivos(session, tipo):
    session.get(
        f'{URL_BASE}/nfe/empresa/ver-arquivos-{tipo}'
    ).raise_for_status()


def extrair_empresas_href(html):
    soup = BeautifulSoup(html, 'lxml')
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


def trocar_empresa(session, empresa, empresas_href):
    empresa_link = empresas_href.get(CNPJ[empresa])

    if not empresa_link:
        raise RuntimeError('Link da empresa não encontrado')

    session.get(
        url=urljoin(URL_BASE, empresa_link),
        headers={'Referer': f'{URL_BASE}/login/enviar'},
        allow_redirects=True
    ).raise_for_status()


def carregar_dados(session, nota, tipo):
    endpoint = f'ver-arquivos-{tipo}'

    payload = {
        'sEcho': '1',
        'iColumns': '7' if tipo == 'nfe' else '8',
        'sColumns': COLUNAS[tipo],
        'nro_nota_de': str(nota),
        'flag_cliente': '98',
        'flag_conta': '98',
        'iDisplayStart': '0',
        'iDisplayLength': '25',
    }

    headers = {
        'X-Requested-With': REQUESTED_WITH,
        'Referer': f'{URL_BASE}/nfe/empresa/{endpoint}',
        'Accept': ACCEPT,
    }

    response = session.post(
        url=f'{URL_BASE}/nfe/empresa/{endpoint}/load',
        headers=headers,
        data=payload
    )
    response.raise_for_status()

    return response.json().get('aaData')


def encontrar_linha(linhas, nota, mes_atual, tipo):
    if not linhas:
        raise RuntimeError(f'Nenhum dado para nota: {nota}')

    ano_atual = int(datetime.today().strftime('%y'))

    for linha in linhas:
        index_emissao, index_nota = (3, 4) if tipo == 'cte' else (2, 3)

        data_match = RE_DATA.search(linha[index_emissao])
        if not data_match: continue

        _, mes, ano = map(int, data_match.groups())
        if mes != mes_atual or ano != ano_atual: continue

        nota_match = RE_NOTA.search(linha[index_nota])
        if nota_match and nota_match.group(1) == str(nota):
            return linha

    raise RuntimeError('Nenhuma nota encontrada')


def extrair_dados(linha, tipo):
    html = " ".join(map(str, linha))

    padroes = {
        'nfe': r"chave='([^']+)'|consultarSituacaoNota\(\"empresa\",\"([^\"]+)\"\)",
        'cte': r'consultarSituacaoNota\("empresa","(.*?)"\)'
    }

    try:
        re_chave = re.compile(padroes.get(tipo, padroes['cte']))
        chave_match = re_chave.search(html)
        if not chave_match:
            raise RuntimeError('Chave da nota não encontrada')

        chave = next(g for g in chave_match.groups() if g is not None)

        empresa_match = RE_EMPRESA_ID.search(html)
        if not empresa_match:
            raise RuntimeError('ID da empresa não encontrado')

        empresa_id = empresa_match.group(1)

        codigo_arquivo_match = RE_CODIGO_ARQUIVO.search(html)
        if not codigo_arquivo_match:
            raise RuntimeError('Código setaFlag não encontrado')

        codigo_arquivo = codigo_arquivo_match.group(1)

        emitente_html = str(linha[1])
        emitente = (
            re.split(r'<br', emitente_html, flags=re.IGNORECASE)[0]
            .strip()
            .upper()
        )

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


def baixar_arquivos(session, empresa_id, chave, tipo):
    ver_path = 'danfe' if tipo == 'nfe' else 'dacte'

    xml_url = f"{URL_BASE}/nfe/download-arquivo/{tipo}/{empresa_id}/{chave}.xml"
    pdf_url = f"{URL_BASE}/nfe/ver-{ver_path}/{tipo}/{empresa_id}/{chave}.pdf"

    #print(f'XML URL: {xml_url}')
    #print(f'PDF URL: {pdf_url}')
    response_xml = session.get(xml_url)
    response_pdf = session.get(pdf_url)

    response_xml.raise_for_status()
    response_pdf.raise_for_status()

    return response_xml.content, response_pdf.content


def marcar_flag(session, codigo_arquivo, codigo_flag = 10):
    session.post(
        f'{URL_BASE}/nfe/seta-flag/{codigo_arquivo}/{codigo_flag}'
    ).raise_for_status()

