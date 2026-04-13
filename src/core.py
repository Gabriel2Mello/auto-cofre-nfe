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
    CNPJ_MATRIZ,
    SENHA_COFRE,
    CNPJ
)


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
    if tipo == 'NFE':
        session.get(
            f'{URL_BASE}/nfe/empresa/ver-arquivos-nfe'
        ).raise_for_status()
    else:
        session.get(
            f'{URL_BASE}/nfe/empresa/ver-arquivos-cfe'
        ).raise_for_status()


def extrair_empresas_href(html):
    soup = BeautifulSoup(html, 'lxml')
    empresas = {}

    re_cnpj = re.compile(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}')

    for link in soup.find_all('a', href=True):
        href = link.get('href')

        if not href:
            continue

        if 'trocarLogin?vid=' in href:
            texto_apos_link = link.next_sibling

            if not texto_apos_link:
                continue

            cnpj_match = re_cnpj.search(str(texto_apos_link))

            if cnpj_match:
                empresas[cnpj_match.group()] = href

    return empresas


def trocar_empresa(session, empresa, empresas_href):
    empresa_link = empresas_href.get(CNPJ[empresa])

    if not empresa_link:
        raise RuntimeError('Link da empresa não encontrado')

    response = session.get(
        url=urljoin(URL_BASE, empresa_link),
        headers={'Referer': f'{URL_BASE}/login/enviar'},
        allow_redirects=True
    )
    response.raise_for_status()


def carregar_nota(session, nota):
    payload = {
        'sEcho': '1',
        'iColumns': '7',
        'sColumns': 'recebimento_quando,emitente_nome,nfe_data,nro_nota,vlr_total,tipo,',
        'nro_nota_de': str(nota),
        'flag_cliente': '98',
        'flag_conta': '98',
        'iDisplayStart': '0',
        'iDisplayLength': '25',
    }

    headers = {
        'X-Requested-With': REQUESTED_WITH,
        'Referer': f'{URL_BASE}/nfe/empresa/ver-arquivos-nfe',
        'Accept': ACCEPT,
    }

    response = session.post(
        url=f'{URL_BASE}/nfe/empresa/ver-arquivos-nfe/load',
        headers=headers,
        data=payload
    )
    response.raise_for_status()

    return response.json().get('aaData')


def carregar_cte(session, nota):
    payload = {
        'sEcho': '1',
        'iColumns': '8',
        'sColumns': 'recebimento_quando,emitente_nome,destinatario_nome,nfe_data,nro_nota,vlr_total,tipo,tipo',
        'nro_nota_de': str(nota),
        'flag_cliente': '98',
        'flag_conta': '98',
        'iDisplayStart': '0',
        'iDisplayLength': '25',
    }

    headers = {
        'X-Requested-With': REQUESTED_WITH,
        'Referer': f'{URL_BASE}/nfe/empresa/ver-arquivos-cte',
        'Accept': ACCEPT,
    }

    response = session.post(
        url=f'{URL_BASE}/nfe/empresa/ver-arquivos-cte/load',
        headers=headers,
        data=payload
    )
    response.raise_for_status()

    return response.json().get('aaData')


def encontrar_linha_nota(linhas, numero_nota, mes_atual):
    if not linhas:
        raise RuntimeError(f'Nenhum dado para nota: {numero_nota}')

    ano_atual = int(datetime.today().strftime('%y'))

    re_data = re.compile(r'(\d{2})/(\d{2})/(\d{2})')
    re_nota = re.compile(r'/(\d+)/')

    for linha in linhas:
        if len(linha) >= 8:
            data_emissao = linha[3]
            nota_str = linha[4]
        else:
            data_emissao = linha[2]
            nota_str = linha[3]

        data_match = re_data.search(data_emissao)
        if not data_match:
            continue

        _, mes, ano = map(int, data_match.groups())
        if mes != mes_atual or ano != ano_atual:
            continue

        nota_match = re_nota.search(nota_str)
        if not nota_match:
            continue

        if nota_match.group(1) == str(numero_nota):
            return linha

    raise RuntimeError('Nenhuma nota encontrada')


def extrair_dados_nota(linha, tipo):
    html = " ".join([str(item) for item in linha])

    padroes = {
        'NFE': r"chave='([^']+)'|consultarSituacaoNota\(\"empresa\",\"([^\"]+)\"\)",
        'CTE': r'consultarSituacaoNota\("empresa","(.*?)"\)'
    }

    re_chave = re.compile(padroes.get(tipo, padroes['CTE']))
    re_empresa = re.compile(r"(?:nfe|cte)/(\d+)/")
    re_codigo_arquivo = re.compile(r"setaFlag\(\d+,'(\d+)'\)")

    try:
        chave_match = re_chave.search(html)
        if not chave_match:
            raise RuntimeError('Chave da nota não encontrada')

        chave = next(g for g in chave_match.groups() if g is not None)

        empresa_match = re_empresa.search(html)
        if not empresa_match:
            raise RuntimeError('ID da empresa não encontrado')

        empresa_id = empresa_match.group(1)

        codigo_arquivo_match = re_codigo_arquivo.search(html)
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
    if tipo == 'NFE':
        xml_url = f"{URL_BASE}/nfe/download-arquivo/nfe/{empresa_id}/{chave}.xml"
        pdf_url = f"{URL_BASE}/nfe/ver-danfe/nfe/{empresa_id}/{chave}.pdf"
    else:
        xml_url = f"{URL_BASE}/nfe/download-arquivo/cte/{empresa_id}/{chave}.xml"
        pdf_url = f"{URL_BASE}/nfe/ver-dacte/cte/{empresa_id}/{chave}.pdf"

    print(f'XML URL: {xml_url}')
    print(f'PDF URL: {pdf_url}')
    response_xml = session.get(xml_url)
    response_pdf = session.get(pdf_url)

    response_xml.raise_for_status()
    response_pdf.raise_for_status()

    return response_xml.content, response_pdf.content


def marcar_flag(session, codigo_arquivo, codigo_flag = 10):
    response = session.post(
        f'{URL_BASE}/nfe/seta-flag/{codigo_arquivo}/{codigo_flag}'
    )
    response.raise_for_status()

