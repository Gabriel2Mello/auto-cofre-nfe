"""Identificação e autoteste do build; sem leitura de configuração operacional."""
import importlib
import json
from pathlib import Path
import socket
import sys

from cofre_instalacao import COMPATIBILIDADE, InstalacaoErro, atomico, identificador, ler_json


def metadados():
    if not getattr(sys, 'frozen', False):
        return {'versao': 'desenvolvimento', 'commit': None}
    dados = ler_json(Path(sys._MEIPASS) / 'cofre-versao.json', 8192)
    identificador(dados.get('versao'))
    return dados


def autoteste(destino):
    def proibido(*args, **kwargs):
        raise InstalacaoErro('O autoteste não permite conexões de rede.')
    socket.socket.connect = proibido
    socket.create_connection = proibido
    from dpi_windows import preparar
    preparar('CofreDesktop')
    # Dependências adiadas pela abertura normal precisam existir no pacote completo.
    for modulo in ('requests', 'cloudscraper', 'bs4', 'lxml.etree', 'pypdf', 'dateutil',
                   'src.execucao_web', 'src.validacao_documentos', 'webview.platforms.winforms',
                   'webview.platforms.edgechromium'):
        importlib.import_module(modulo)
    from src.caminhos import recursos
    for nome in ('src/cofre.html', 'src/cofre.js', 'src/cofre.css', 'desktop-winforms.config', 'icons/icone.ico'):
        if not (recursos() / nome).is_file():
            raise InstalacaoErro('Recurso ausente no pacote.')
    versao = metadados()['versao']
    atomico(Path(destino), {'formato': 1, 'versao': versao,
                           'compatibilidade': COMPATIBILIDADE, 'pronto': True})
    return 0
