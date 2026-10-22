"""Servidor do painel, restrito ao próprio computador e sem dependências web."""

from integracao_hub import atender_integracao

import json
import sys
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from secrets import compare_digest, token_urlsafe
from threading import Event, Thread
from time import monotonic

from src.controlador_web import EstadoInterface


class ServidorInterface(ThreadingHTTPServer):
  daemon_threads = True

  def __init__(self, handler, estado: EstadoInterface) -> None:
    super().__init__(('127.0.0.1', 0), handler)
    self.estado = estado
    self.paginas: dict[str, Event] = {}
    self.teve_pagina = False
    self.sem_paginas_desde = monotonic()
    self.finalizando = Event()
    self.fechando = False

  def finish_request(self, request, client_address) -> None:
    request.settimeout(10)
    super().finish_request(request, client_address)

  def service_actions(self) -> None:
    with self.estado.condicao:
      if not self.paginas and monotonic() - self.sem_paginas_desde >= (4 if self.teve_pagina else 120):
        self.estado.encerrar()
      if self.estado.encerrando and not self.estado.dados['ativo'] and not self.fechando:
        self.fechando = True
        Thread(target=self.shutdown, daemon=True).start()

  def server_close(self) -> None:
    self.finalizando.set()
    self.estado.encerrar()
    super().server_close()


def criar_servidor(estado: EstadoInterface) -> ServidorInterface:
  token = token_urlsafe(32)
  raiz = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
  arquivos = {
    '/': (raiz / 'src/cofre.html', 'text/html; charset=utf-8'),
    '/cofre.css': (raiz / 'src/cofre.css', 'text/css; charset=utf-8'),
    '/cofre.js': (raiz / 'src/cofre.js', 'text/javascript; charset=utf-8'),
    '/nunes-tema.js': (raiz / 'src/nunes-tema.js', 'text/javascript; charset=utf-8'),
    '/icons/icone.svg': (raiz / 'icons/icone.svg', 'image/svg+xml'),
    '/icons/icone-192.png': (raiz / 'icons/icone-192.png', 'image/png'),
    '/favicon.ico': (raiz / 'icons/icone.ico', 'image/x-icon'),
  }

  class Manipulador(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
      pass

    def responder(self, status: int, conteudo: bytes, tipo: str = 'application/json; charset=utf-8') -> None:
      self.send_response(status)
      self.send_header('Content-Type', tipo)
      self.send_header('Content-Length', str(len(conteudo)))
      self.send_header('Cache-Control', 'no-store')
      self.send_header('X-Content-Type-Options', 'nosniff')
      self.send_header('Referrer-Policy', 'no-referrer')
      self.send_header('Content-Security-Policy', "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
      self.end_headers()
      try:
        self.wfile.write(conteudo)
      except (BrokenPipeError, ConnectionResetError):
        pass

    def json(self, status: int, dados: dict) -> None:
      self.responder(status, json.dumps(dados, ensure_ascii=False).encode('utf-8'))

    def host_valido(self) -> bool:
      return self.headers.get_all('Host') == [f'127.0.0.1:{servidor.server_port}']

    def autorizado(self) -> bool:
      origem = f'http://127.0.0.1:{servidor.server_port}'
      return (self.host_valido()
              and compare_digest(self.headers.get('Authorization', '').encode('utf-8'),
                                 ('Bearer ' + token).encode('ascii'))
              and self.headers.get('Origin') in ((origem,) if self.command == 'POST' else (None, origem)))

    def acompanhar_pagina(self) -> None:
      pagina = self.headers.get('X-Cofre-Pagina', '')
      if not pagina or len(pagina) > 100 or not pagina.isascii():
        self.json(400, {'erro': 'Identificação de página inválida.'})
        return
      evento = Event()
      with estado.condicao:
        if estado.encerrando:
          self.json(409, {'erro': 'O programa está encerrando.'})
          return
        anterior = servidor.paginas.get(pagina)
        if anterior:
          anterior.set()
        servidor.paginas[pagina] = evento
        servidor.teve_pagina = True
        estado.condicao.notify_all()
      try:
        self.connection.settimeout(3)
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        # Esta conexão detecta o fechamento da aba; não consulta o estado nem altera a tela.
        while not servidor.finalizando.is_set() and not evento.is_set():
          self.wfile.write(b': presenca\n\n')
          self.wfile.flush()
          evento.wait(1)
      except OSError:
        pass
      finally:
        with estado.condicao:
          if servidor.paginas.get(pagina) is evento:
            servidor.paginas.pop(pagina)
            servidor.sem_paginas_desde = monotonic()
            estado.condicao.notify_all()

    def do_GET(self) -> None:
      if atender_integracao(self):
        return
      if not self.host_valido():
        self.json(403, {'erro': 'Acesso local inválido.'})
      elif self.path in arquivos:
        arquivo, tipo = arquivos[self.path]
        try:
          conteudo = arquivo.read_bytes()
          if self.path == '/':
            conteudo = conteudo.replace(b'__TOKEN__', token.encode('ascii')).replace(
              b'__MES__', date.today().strftime('%Y-%m').encode('ascii'))
          self.responder(200, conteudo, tipo)
        except OSError:
          self.json(500, {'erro': 'Recurso da interface ausente. Confira a instalação.'})
      elif self.path == '/api/estado':
        if self.autorizado():
          self.json(200, estado.snapshot())
        else:
          self.json(403, {'erro': 'Acesso não autorizado.'})
      elif self.path == '/api/presenca' and self.autorizado():
        self.acompanhar_pagina()
      else:
        self.json(404, {'erro': 'Endereço não encontrado.'})

    def do_POST(self) -> None:
      if atender_integracao(self):
        return
      if not self.autorizado():
        self.json(403, {'erro': 'Acesso não autorizado.'})
        return
      try:
        tamanhos = self.headers.get_all('Content-Length', [])
        if len(tamanhos) != 1 or not tamanhos[0].isascii() or not tamanhos[0].isdigit():
          raise ValueError('Tamanho da requisição inválido.')
        tamanho = int(tamanhos[0])
        if not 0 < tamanho <= 65536:
          raise ValueError('Requisição vazia ou muito grande.')
        if self.headers.get('Content-Type') != 'application/json':
          raise ValueError('Envie os dados no formato JSON.')
        dados = json.loads(self.rfile.read(tamanho))
        if not isinstance(dados, dict):
          raise ValueError('Os dados enviados devem ser um objeto.')
        if self.path == '/api/iniciar':
          estado.iniciar(dados)
        elif self.path == '/api/responder':
          estado.responder(dados)
        elif self.path == '/api/parar':
          estado.parar()
        elif self.path == '/api/fechar':
          estado.encerrar()
        else:
          self.json(404, {'erro': 'Ação não encontrada.'})
          return
        self.json(200, {'ok': True})
      except (ValueError, TypeError, UnicodeError) as erro:
        self.json(400, {'erro': str(erro)})

  servidor = ServidorInterface(Manipulador, estado)
  return servidor
