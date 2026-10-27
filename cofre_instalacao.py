"""Coordenação local do piloto Cofre. Fonte no Hub; cópia explícita no Cofre.

Não acessa distribuição, portal, credenciais ou dados de negócio.
"""
from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import re
import sys
import time
import uuid

APLICACAO = 'cofre-nfe'
COMPATIBILIDADE = {'cofre': 'gravacao-e5', 'metricas': 'schema-1-e7',
                  'integracao': 1, 'central': 1, 'confirmacoes': 1}
AMBIENTE = ('NUNES_COFRE_DADOS', 'NUNES_HUB_DADOS', 'NUNES_METRICAS_DADOS')
_reservas = []  # Mantidas até a saída do interpretador; não liberar antes do worker.
_piloto = False


class InstalacaoErro(ValueError):
    pass


def fisico(caminho):
    caminho = Path(caminho).absolute()
    if '..' in caminho.parts:
        raise InstalacaoErro('Caminhos com .. não são permitidos.')
    for parte in (caminho, *caminho.parents):
        if parte.is_symlink() or parte.is_junction():
            raise InstalacaoErro('A instalação não aceita links ou junctions.')
    return caminho


def identificador(valor):
    if not isinstance(valor, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}', valor) or valor.endswith('.'):
        raise InstalacaoErro('Identificador de versão inválido.')
    if valor.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL',
                                      *(f'COM{i}' for i in range(1, 10)),
                                      *(f'LPT{i}' for i in range(1, 10))}:
        raise InstalacaoErro('Identificador reservado pelo Windows.')
    return valor


def ler_json(caminho, limite=4 * 1024 * 1024):
    caminho = fisico(caminho)
    with caminho.open('rb') as entrada:
        bruto = entrada.read(limite + 1)
    if len(bruto) > limite:
        raise InstalacaoErro('Arquivo de controle excede o limite.')
    return decodificar_json(bruto)


def decodificar_json(bruto):
    def objeto(pares):
        resultado = {}
        for chave, valor in pares:
            if chave in resultado:
                raise InstalacaoErro('Chaves repetidas no arquivo de controle.')
            resultado[chave] = valor
        return resultado
    dados = json.loads(bruto, object_pairs_hook=objeto)
    if not isinstance(dados, dict):
        raise InstalacaoErro('Arquivo de controle inválido.')
    return dados


def atomico(caminho, dados):
    caminho = fisico(caminho)
    temporario = caminho.with_name(caminho.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporario.open('xb') as saida:
            saida.write((json.dumps(dados, ensure_ascii=False, sort_keys=True) + '\n').encode('utf-8'))
            saida.flush()
            os.fsync(saida.fileno())
        os.replace(temporario, caminho)
    finally:
        temporario.unlink(missing_ok=True)


class Reserva:
    """Trava de arquivo compartilhada para uso, exclusiva para ativação.

    O arquivo físico é comum a todas as sessões que usam a mesma instalação.
    Ausência de permissão é falha, nunca interpretada como reserva livre.
    """
    def __init__(self, caminho, *, exclusiva=True):
        self.arquivo = fisico(caminho).open('a+b')
        self.exclusiva = exclusiva
        self.sobreposta = None
        try:
            if os.name == 'nt':
                import msvcrt
                from ctypes import wintypes
                class Overlapped(ctypes.Structure):
                    _fields_ = [('Internal', ctypes.c_size_t), ('InternalHigh', ctypes.c_size_t),
                                ('Offset', wintypes.DWORD), ('OffsetHigh', wintypes.DWORD),
                                ('hEvent', wintypes.HANDLE)]
                self.sobreposta = Overlapped()
                self.handle = msvcrt.get_osfhandle(self.arquivo.fileno())
                kernel = ctypes.WinDLL('kernel32', use_last_error=True)
                kernel.LockFileEx.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                                              wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
                if not kernel.LockFileEx(self.handle, 1 | (2 if exclusiva else 0), 0, 1, 0,
                                         ctypes.byref(self.sobreposta)):
                    raise OSError(ctypes.get_last_error(), 'Instalação em uso ou atualização em curso.')
            else:
                import fcntl
                fcntl.flock(self.arquivo, (fcntl.LOCK_EX if exclusiva else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        except BaseException:
            self.arquivo.close()
            raise

    def close(self):
        self.arquivo.close()  # O SO libera a região também em término inesperado.

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def raiz_instalada(executavel=None):
    if executavel is None and not getattr(sys, 'frozen', False):
        return None
    exe = Path(executavel or sys.executable).absolute()
    if exe.parent.name != 'conteudo' or exe.parent.parent.parent.name != 'versoes':
        return None
    raiz = fisico(exe.parent.parent.parent.parent)
    if not (raiz / 'instalacao.json').is_file():
        return None
    return raiz


def estado(raiz):
    dados = ler_json(Path(raiz) / 'instalacao.json')
    if dados.get('formato') != 1 or dados.get('aplicacao') != APLICACAO:
        raise InstalacaoErro('Instalação incompatível.')
    identificador(dados.get('ativa'))
    if dados.get('anterior') is not None:
        identificador(dados['anterior'])
    if type(dados.get('maior_sequencia')) is not int or dados['maior_sequencia'] < 1:
        raise InstalacaoErro('Sequência da instalação inválida.')
    return dados


def ambiente_instalado(raiz):
    config = ler_json(Path(raiz) / 'configuracao.json')
    if config.get('formato') != 1 or not isinstance(config.get('ambiente', {}), dict):
        raise InstalacaoErro('Configuração da instalação inválida.')
    variaveis = config.get('ambiente', {})
    if set(variaveis) - set(AMBIENTE):
        raise InstalacaoErro('Variável não permitida na instalação.')
    for valor in variaveis.values():
        if not isinstance(valor, str) or not Path(valor).is_absolute():
            raise InstalacaoErro('Os dados precisam de caminhos absolutos.')
        if fisico(valor).is_relative_to(fisico(raiz)):
            raise InstalacaoErro('Dados persistentes precisam ficar fora da instalação.')
    return variaveis


def reservar_execucao(executavel=None):
    global _piloto
    raiz = raiz_instalada(executavel)
    if raiz is None:
        return None
    limite = time.monotonic() + 15
    while True:
        try:
            mudanca = Reserva(raiz / 'mudanca.lock')
            break
        except OSError:
            if time.monotonic() >= limite:
                raise InstalacaoErro('Atualização em andamento. Aguarde e abra pelo iniciador Cofre.exe.')
            time.sleep(.1)
    with mudanca:
        atual = estado(raiz)
        exe = Path(executavel or sys.executable).absolute()
        if exe.parent.parent.name != atual['ativa']:
            raise InstalacaoErro('Esta versão está inativa. Abra pelo iniciador Cofre.exe.')
        os.environ.update(ambiente_instalado(raiz))
        _piloto = ler_json(raiz / 'configuracao.json').get('piloto') is True
        if _piloto:
            for nome in ('SENHA_COFRE', 'CNPJ_MATRIZ', 'CNPJ_FILIAL', 'CAMINHO_DOCUMENTO_ENTRADA', 'NUNES_CENTRAL_CONFIG'):
                os.environ.pop(nome, None)
        _reservas.append(Reserva(raiz / 'uso.lock', exclusiva=False))
    return raiz


def relancamento():
    raiz = raiz_instalada()
    return [str(raiz / 'Cofre.exe')] if raiz else None


def piloto():
    return _piloto


def icone_relancamento():
    raiz = raiz_instalada()
    return raiz / 'icone.ico' if raiz else None


def pronto():
    raiz = raiz_instalada()
    if raiz:
        # Fora da pasta imutável da versão; sem dados fiscais.
        atomico(raiz / f'pronto-{os.getpid()}.json',
                {'formato': 1, 'versao': Path(sys.executable).parent.parent.name, 'pid': os.getpid()})
