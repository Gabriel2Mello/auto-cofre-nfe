import json
import sys
import re
from datetime import datetime
from time import sleep
from pathlib import Path

from src.config import CAMINHO_DOCUMENTO_ENTRADA, MONTHS

def encerrar_programa(value):
    if value is None:
        print('\nOperação cancelada...encerrando programa.')
        sleep(1)
        sys.exit()


def obter_caminho_json():
    if hasattr(sys, 'frozen'):
        diretorio_execucao = Path(sys.executable).parent
    else:
        diretorio_execucao = Path(__file__).parent.parent

    return diretorio_execucao / 'emitentes_conhecidos.json'


def resolver_emitente(emitente):
    caminho_json = obter_caminho_json()

    emitentes_conhecidos = {}

    if caminho_json.exists():
        with open(caminho_json, 'r', encoding='utf-8') as f:
            try:
                emitentes_conhecidos = json.load(f)
            except json.JSONDecodeError:
                emitentes_conhecidos = {}

    if emitente in emitentes_conhecidos:
        return emitentes_conhecidos[emitente]

    print(f'\nEmitente não reconhecido: {emitente}')
    emitente_identificado = input('Digite o nome: ').upper().strip()

    emitentes_conhecidos[emitente] = emitente_identificado

    # Salva nome no arquivo emitentes_conhecidos.json
    with open(caminho_json, 'w', encoding='utf-8') as f:
        json.dump(emitentes_conhecidos, f, indent=4, ensure_ascii=False)

    return emitente_identificado


def salvar_arquivos(xml, pdf, nome_emitente, numero_nota, empresa, mes, tipo):
    ano = str(datetime.today().year)

    nome_arquivo = f'{nome_emitente} {numero_nota}'
    nome_limpo = re.sub(r'[\\/*?:"<>|]', '', nome_arquivo)

    base_path = Path(CAMINHO_DOCUMENTO_ENTRADA)
    if not base_path.exists():
        raise RuntimeError('CAMINHO_DOCUMENTO_ENTRADA não configurado.')


    tipo_caminho = 'NF-e' if tipo == 'NFE' else 'CT-e'
    path_pdf = base_path / f'PDF {tipo_caminho}' / ano / empresa / MONTHS[mes]
    path_xml = base_path / f'XML - {tipo_caminho}' / ano / empresa / MONTHS[mes]

    if not path_pdf.exists():
        raise RuntimeError('Caminho da pasta PDF não existe')

    if not path_xml.exists():
        raise RuntimeError('Caminho da pasta XML não existe')

    (path_pdf / f'{nome_limpo}.pdf').write_bytes(pdf)
    (path_xml / f'{nome_limpo}.xml').write_bytes(xml)

