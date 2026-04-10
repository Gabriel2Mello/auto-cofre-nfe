from time import perf_counter
import requests
from os import environ
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
import os
import json
import argparse
from datetime import datetime
from pathlib import Path

MONTHS = [
    None,
    'JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL',
    'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO',
    'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO'
]

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36'

URL_BASE = 'https://painel.cofrenfe.com.br'

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('nota', help='Número da nota')
    parser.add_argument('empresa', help='1(Matriz) 2(Filial)')
    return parser.parse_args()

def login(session):
    headers_login = {
        'User-Agent': USER_AGENT,
        'Referer': URL_BASE + '/login',
        'Origin': URL_BASE,
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    data_login = {
        's': 'nfe',
        'cpf': environ['CNPJ_MATRIZ'],
        'senha': environ['SENHA_COFRE']
    }

    response = session.post(
        url=URL_BASE + '/login/enviar',
        data=data_login,
        headers=headers_login,
        allow_redirects=True
    )

    return response.text

def extrair_empresas_href(html):
    soup = BeautifulSoup(html, 'html.parser')
    empresas = {}

    for link in soup.find_all('a', href=True):
        href = link.get('href')

        if not href:
            continue

        if 'trocarLogin?vid=' in href:
            texto_apos_link = link.next_sibling

            if not texto_apos_link:
                continue

            cnpj_match = re.search(
                r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}",
                str(texto_apos_link)
            )

            if cnpj_match:
                empresas[cnpj_match.group()] = href

    return empresas


def trocar_empresa(session, empresa, empresas_href):
    empresa_link = empresas_href.get('09.034.052/0002-34')

    if empresa == 'MATRIZ':
        empresa_link = empresas_href.get('09.034.052/0001-53')

    if not empresa_link:
        raise RuntimeError('Empresa não encontrada')

    headers = {
        'User-Agent': USER_AGENT,
        'Referer': URL_BASE + '/login/enviar',
    }

    response = session.get(
        url=urljoin(URL_BASE, empresa_link),
        headers=headers,
        allow_redirects=True
    )

    response.raise_for_status()


def carregar_notas(session, numero_nota):
    data_load = {
        'sEcho': '1',
        'iColumns': '7',
        'sColumns': 'recebimento_quando,emitente_nome,nfe_data,nro_nota,vlr_total,tipo,',
        'nro_nota_de': f"{numero_nota}",
        'flag_cliente': '98',
        'flag_conta': '98',
        'iDisplayStart': '0',
        'iDisplayLength': '25',
    }

    headers_load = {
        'User-Agent': USER_AGENT,
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': URL_BASE + '/nfe/empresa/ver-arquivos-nfe',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Origin': URL_BASE,
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    response = session.post(
        URL_BASE + '/nfe/empresa/ver-arquivos-nfe/load',
        headers=headers_load,
        data=data_load
    )

    response.raise_for_status()

    return response.json().get('aaData')

def encontrar_linha_nota(linhas, numero_nota):
    mes_atual = datetime.today().month
    ano_atual = datetime.today().year % 100

    for l in linhas:
        data_emissao = l[2]

        data_match = re.search(r"(\d{2})/(\d{2})/(\d{2})", data_emissao)
        if not data_match:
            continue

        _, mes, ano = data_match.groups()

        if int(mes) != mes_atual or int(ano) != ano_atual:
            continue

        nota_str = l[3]

        nota_match = re.search(r"/(\d+)/", nota_str)
        if not nota_match:
            continue

        if nota_match.group(1) == str(numero_nota):
            return l

    raise RuntimeError('Nota não encontrada')


def extrair_dados_nota(linha):
    html = linha[6]

    chave_match = re.search(r"chave='([^']+)'", html)
    if not chave_match:
        raise RuntimeError('Chave da NFe não encontrada')

    chave = chave_match.group(1)

    empresa_match = re.search(r"nfe/(\d+)/", html)
    if not empresa_match:
        raise RuntimeError('ID da empresa não encontrado')

    empresa_id = empresa_match.group(1)

    codigo_arquivo_match = re.search(r"setaFlag\(\d+,'(\d+)'\)", html)
    if not codigo_arquivo_match:
        raise RuntimeError('Código setaFlag não encontrado')

    codigo_arquivo = codigo_arquivo_match.group(1)

    emitente_html = linha[1]
    emitente = emitente_html.split('<br')[0].upper().strip()

    if not emitente:
        raise RuntimeError('Emitente não encontrado')

    print('Emitente:', emitente)
    return chave, empresa_id, codigo_arquivo, emitente


def baixar_arquivos(session, empresa_id, chave):
    xml_url = f"{URL_BASE}/nfe/download-arquivo/nfe/{empresa_id}/{chave}.xml"
    pdf_url = f"{URL_BASE}/nfe/ver-danfe/nfe/{empresa_id}/{chave}.pdf"

    xml = session.get(xml_url)
    pdf = session.get(pdf_url)

    xml.raise_for_status()
    pdf.raise_for_status()

    return xml.content, pdf.content


def resolver_emitente(emitente):
    base_dir = Path(os.getcwd())
    arquivo_emitentes = base_dir / 'emitentes_conhecidos.json'

    emitentes_conhecidos = {}

    if os.path.exists(arquivo_emitentes):
        with open(arquivo_emitentes, 'r', encoding='utf-8') as f:
            emitentes_conhecidos = json.load(f)

    if emitente in emitentes_conhecidos:
        nome_emitente = emitentes_conhecidos[emitente]
    else:
        print(f"\nEmitente não reconhecido: {emitente}")
        nome_emitente = input("Digite o nome: ").upper().strip()

    emitentes_conhecidos[emitente] = nome_emitente

    # Salva nome no arquivo emitentes_conhecidos.json
    with open(arquivo_emitentes, 'w', encoding='utf-8') as f:
        json.dump(emitentes_conhecidos, f, indent=4, ensure_ascii=False)

    return nome_emitente

def salvar_arquivos(xml, pdf, nome_emitente, numero_nota, empresa):
    mes = datetime.today().month
    ano = datetime.today().year

    nome_arquivo = f"{nome_emitente} {numero_nota}"
    nome_arquivo = re.sub(r'[\\/*?:"<>|]', '', nome_arquivo)

    base_path = Path(environ['CAMINHO_DOCUMENTO_ENTRADA'])
    if not base_path.exists():
        raise RuntimeError('Caminho base não existe')

    path_pdf = base_path / 'PDF NF-e' / str(ano) / empresa / MONTHS[mes]
    path_xml = base_path / 'XML - NF-e' / str(ano) / empresa / MONTHS[mes]

    if not Path(path_pdf).exists() or not Path(path_xml).exists():
        raise RuntimeError('Caminho da pasta não existe')

    with open(path_pdf / f"{nome_arquivo}.pdf", 'wb') as f:
        f.write(pdf)

    with open(path_xml / f"{nome_arquivo}.xml", 'wb') as f:
        f.write(xml)

def marcar_flag(session, codigo_arquivo, codigo_flag = 10):
    response = session.post(
        f"{URL_BASE}/nfe/seta-flag/{codigo_arquivo}/{codigo_flag}"
    )
    response.raise_for_status()



def main():
    start_time = perf_counter()

    args = parse_args()
    numero_nota = args.nota
    empresa = args.empresa
    empresa = 'MATRIZ' if empresa == '1' else 'FILIAL'

    session = requests.Session()

    html_login = login(session)
    empresas_href = extrair_empresas_href(html_login)

    trocar_empresa(session, empresa, empresas_href)

    session.get(
        URL_BASE + '/nfe/empresa/ver-arquivos-nfe'
    ).raise_for_status()

    linhas = carregar_notas(session, numero_nota)

    linha = encontrar_linha_nota(linhas, numero_nota)

    chave, empresa_id, codigo_arquivo, emitente = extrair_dados_nota(linha)

    xml, pdf = baixar_arquivos(session, empresa_id, chave)

    nome_emitente = resolver_emitente(emitente)

    salvar_arquivos(xml, pdf, nome_emitente, numero_nota, empresa)

    #marcar_flag(session, codigo_arquivo)


    elapsed_time = perf_counter() - start_time
    print(f"Terminado em: {elapsed_time:0.2f} segundos")


if __name__ == "__main__":
    main()

