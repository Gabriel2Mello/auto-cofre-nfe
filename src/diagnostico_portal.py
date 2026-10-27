"""Diagnóstico local do acesso ao portal, sem respostas ou exceções brutas."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha256
import json
import re
from logging import LogRecord
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock
from time import perf_counter
from urllib.parse import urlsplit
from uuid import uuid4

from requests import HTTPError, RequestException, Timeout

from src.caminhos import pasta_preferencias
from src.config import Config
from src.enums import Empresa


_execucao: ContextVar[dict | None] = ContextVar('diagnostico_cofre', default=None)
_trava = Lock()
LIMITE_BYTES = 1_048_576
COPIAS = 3


def caminho_log() -> Path:
  return pasta_preferencias() / 'logs' / 'cofre-portal.jsonl'


@lru_cache(maxsize=1)
def _codigo() -> str:
  try:
    raiz = Path(__file__).parent
    return sha256(b''.join((raiz / nome).read_bytes() for nome in
      ('auth.py', 'core.py', 'parsers.py', 'http_client.py', 'diagnostico_portal.py'))).hexdigest()[:16]
  except OSError:
    return 'indisponivel'


def _registrar(evento: str, **campos) -> None:
  contexto = _execucao.get()
  if contexto is None:
    return
  try:
    registro = {'formato': 1, 'horario': datetime.now(timezone.utc).isoformat(),
                **contexto, 'evento': evento, **campos}
    linha = json.dumps(registro, ensure_ascii=False)
    with _trava:
      caminho = caminho_log()
      caminho.parent.mkdir(parents=True, exist_ok=True)
      handler = RotatingFileHandler(caminho, maxBytes=LIMITE_BYTES,
                                    backupCount=COPIAS, encoding='utf-8')
      try:
        record = LogRecord('cofre.portal', 20, '', 0, linha, (), None)
        # Escrita direta contém falhas sem logging imprimir traceback no stderr.
        if handler.shouldRollover(record):
          handler.doRollover()
        handler.stream.write(linha + '\n')
        handler.flush()
      finally:
        handler.close()
  except Exception:
    # Não impedir a operação nem substituir a falha original por uma falha do log.
    pass


def _erro(erro: BaseException) -> str:
  if isinstance(erro, Timeout):
    return 'timeout'
  if isinstance(erro, HTTPError):
    return 'http'
  if isinstance(erro, RequestException):
    return 'comunicacao'
  if isinstance(erro, (KeyboardInterrupt, EOFError)):
    return 'interrompido'
  if isinstance(erro, ValueError):
    return 'validacao'
  return 'inesperado'


@contextmanager
def diagnostico_execucao(empresa: Empresa, identificador: str | None = None):
  # O identificador é interno e correlaciona acesso e parada, inclusive em
  # threads distintas. Nunca aceitar texto livre como identificador do log.
  identificador = (identificador if isinstance(identificador, str)
    and re.fullmatch(r'[0-9a-f]{32}', identificador) else uuid4().hex)
  token = _execucao.set({'execucao': identificador,
                        'empresa': empresa.value if isinstance(empresa, Empresa) else 'invalida'})
  _registrar('acesso_iniciado', codigo=_codigo())
  try:
    yield
  except BaseException as erro:
    _registrar('acesso_encerrado', resultado='falha', erro=_erro(erro))
    raise
  else:
    _registrar('acesso_encerrado', resultado='confirmado')
  finally:
    _execucao.reset(token)


@contextmanager
def etapa_portal(nome: str):
  inicio = perf_counter()
  _registrar('etapa_iniciada', etapa=nome)
  try:
    yield
  except BaseException as erro:
    _registrar('etapa_encerrada', etapa=nome, resultado='falha', erro=_erro(erro),
               duracao_ms=round((perf_counter() - inicio) * 1000, 2))
    raise
  else:
    _registrar('etapa_encerrada', etapa=nome, resultado='sucesso',
               duracao_ms=round((perf_counter() - inicio) * 1000, 2))


def _pagina(url: str) -> str:
  partes = urlsplit(url)
  origem = urlsplit(Config.URL_BASE)
  if (partes.scheme, partes.netloc) != (origem.scheme, origem.netloc):
    return 'outra_origem'
  # Não guardar URL, querystring, fragmento, vínculo ou identificador.
  return {'/login': 'login', '/login/enviar': 'login',
          '/empresa': 'entrada_empresa',
          '/nfe/empresa': 'empresa',
          '/nfe/empresa/ver-arquivos-nfe': 'arquivos_nfe',
          '/nfe/empresa/ver-arquivos-cte': 'arquivos_cte'}.get(partes.path, 'outra')


def registrar_resposta(etapa: str, resposta) -> None:
  if _execucao.get() is None:
    return
  try:
    html = resposta.text.lower()
    mime = resposta.headers.get('Content-Type', '').split(';', 1)[0].strip().lower()
    _registrar('resposta_portal', etapa=etapa, status=resposta.status_code,
               pagina=_pagina(resposta.url),
               redirecionamentos=[{'status': r.status_code, 'pagina': _pagina(r.url)}
                                  for r in resposta.history],
               conteudo=mime if mime in ('text/html', 'application/json', 'text/plain') else 'outro',
               tamanho_bytes=len(resposta.content),
               formulario_login=bool(re.search(r'<input\b[^>]*\btype\s*=\s*[\"\']?password\b', html)),
               desafio_acesso=any(m in html for m in ('cf-chl-', 'challenge-platform', 'g-recaptcha', 'hcaptcha')))
  except Exception:
    pass


def registrar_confirmacao(motivo: str, cabecalhos: int | None = None,
                         spans: int | None = None, cnpjs: int | None = None,
                         configuracao_valida: bool | None = None) -> None:
  _registrar('confirmacao_empresa', motivo=motivo, cabecalhos=cabecalhos,
             spans_diretos=spans, cnpjs_encontrados=cnpjs,
             configuracao_valida=configuracao_valida)


def registrar_parada(identificador: str | None, empresa: Empresa | None, origem: str,
                    pergunta: str | None, encerrando: bool) -> None:
  # A solicitação chega na thread HTTP, fora do contexto de acesso do worker.
  if not isinstance(identificador, str) or not re.fullmatch(r'[0-9a-f]{32}', identificador):
    return
  token = _execucao.set({'execucao': identificador,
                        'empresa': empresa.value if isinstance(empresa, Empresa) else 'invalida'})
  try:
    _registrar('parada_solicitada', origem=origem if origem in
      ('parar', 'decisao', 'encerramento') else 'outra',
      pergunta=pergunta if pergunta in ('nome', 'emitente') else None,
      encerrando=bool(encerrando))
  finally:
    _execucao.reset(token)
