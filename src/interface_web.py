"""Servidor do painel, restrito ao próprio computador e sem dependências web."""

from integracao_hub import atender_integracao

import json
from html import escape
import sys
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from secrets import compare_digest, token_urlsafe
from threading import Event, Thread
from time import monotonic

from src.controlador_web import EstadoInterface
from src.caminhos import documentos_entrada, arquivo_emitentes


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
    self.desktop = None
    self.modo_desktop = False

  def finish_request(self, request, client_address) -> None:
    request.settimeout(10)
    super().finish_request(request, client_address)

  def service_actions(self) -> None:
    with self.estado.condicao:
      if not self.modo_desktop and not self.paginas and monotonic() - self.sem_paginas_desde >= (4 if self.teve_pagina else 120):
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
    '/rolagem.js': (raiz / 'src/rolagem.js', 'text/javascript; charset=utf-8'),
    '/nunes-tema.js': (raiz / 'src/nunes-tema.js', 'text/javascript; charset=utf-8'),
    '/icons/icone.svg': (raiz / 'icons/icone.svg', 'image/svg+xml'),
    '/icons/tema-lua.svg': (raiz / 'icons/tema-lua.svg', 'image/svg+xml'),
    '/icons/tema-lua-sol.svg': (raiz / 'icons/tema-lua-sol.svg', 'image/svg+xml'),
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
      from desktop_cofre import atender_ativacao, ler_tema, ler_enter_baixar
      if atender_ativacao(self):
        return
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
            conteudo = conteudo.replace(b'__DESKTOP__', b'1' if servidor.modo_desktop else b'0')
            conteudo = conteudo.replace(b'__TEMA__', ler_tema().encode('ascii'))
            conteudo = conteudo.replace(b'__ENTER_BAIXAR__', b'checked' if ler_enter_baixar() else b'')
            try:
              pasta = documentos_entrada() or 'Pasta não configurada. Escolha DOCUMENTOS DE ENTRADA abaixo.'
            except ValueError as erro:
              pasta = str(erro)
            conteudo = conteudo.replace(b'__DESTINO_BASE__', escape(pasta).encode('utf-8'))
            try:
              catalogo = str(arquivo_emitentes())
            except ValueError as erro:
              catalogo = str(erro)
            conteudo = conteudo.replace(b'__ARQUIVO_EMITENTES__', escape(catalogo).encode('utf-8'))
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
      from desktop_cofre import atender_ativacao, salvar_tema, salvar_enter_baixar
      if atender_ativacao(self):
        return
      if atender_integracao(self):
        return
      if not self.autorizado():
        # Consumir somente corpo pequeno e delimitado evita RST no Windows
        # ao recusar Origin/token com bytes ainda pendentes no socket.
        tamanhos = self.headers.get_all('Content-Length') or []
        if len(tamanhos) == 1 and tamanhos[0].isascii() and tamanhos[0].isdigit() and len(tamanhos[0]) <= 5:
          tamanho = int(tamanhos[0])
          if tamanho <= 65536:
            self.rfile.read(tamanho)
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
        elif self.path == '/api/diagnostico-inicio':
          from src.diagnostico_interface import registrar_inicio
          try:
            caminho = registrar_inicio(dados)
          except OSError:
            self.json(500, {'erro': 'Diagnóstico local indisponível.'})
            return
          self.json(200, {'caminho': str(caminho)})
          return
        elif self.path == '/api/responder':
          estado.responder(dados)
        elif self.path == '/api/parar':
          estado.parar(origem='decisao' if dados.get('origem') == 'decisao' else 'parar')
        elif self.path == '/api/fechar':
          estado.encerrar()
        elif self.path == '/api/entrada-notas':
          if set(dados) != {'enter_baixar'}:
            raise ValueError('Informe somente a opção Enter para baixar.')
          try:
            salvar_enter_baixar(dados['enter_baixar'])
          except OSError:
            self.json(500, {'erro': 'Não foi possível salvar a opção Enter para baixar.'})
            return
        elif self.path == '/api/tema' and servidor.modo_desktop:
          try:
            salvar_tema(dados.get('tema'))
          except OSError:
            self.json(500, {'erro': 'O tema mudou nesta janela, mas não foi salvo. Confira a pasta de preferências.'})
            return
        elif self.path == '/api/pasta' and servidor.modo_desktop and servidor.desktop is not None:
          if dados:
            raise ValueError('A pasta deve ser escolhida no diálogo nativo; não envie caminhos pela página.')
          try:
            resultado = servidor.desktop.escolher_pasta()
          except OSError:
            self.json(500, {'erro': 'Não foi possível salvar a configuração. Confira o acesso à pasta de preferências.'})
            return
          self.json(200, resultado)
          return
        elif self.path == '/api/emitentes' and servidor.modo_desktop and servidor.desktop is not None:
          if dados:
            raise ValueError('O arquivo deve ser escolhido no diálogo nativo; não envie caminhos pela página.')
          try:
            resultado = servidor.desktop.escolher_emitentes()
          except OSError:
            self.json(500, {'erro': 'Não foi possível salvar a configuração. Confira o acesso à pasta de preferências.'})
            return
          self.json(200, resultado)
          return
        elif self.path in ('/api/emitentes/abrir', '/api/emitentes/editar') and servidor.modo_desktop and servidor.desktop is not None:
          if dados:
            raise ValueError('A ação usa o arquivo configurado; não envie caminhos pela página.')
          try:
            servidor.desktop.abrir_emitentes(editar=self.path.endswith('/editar'))
          except OSError:
            self.json(500, {'erro': 'Não foi possível abrir o catálogo. Confira o acesso ao arquivo.'})
            return
          self.json(200, {'aberto': True})
          return
        elif self.path == '/api/pasta/abrir' and servidor.modo_desktop and servidor.desktop is not None:
          if dados:
            raise ValueError('A abertura usa a pasta configurada; não envie caminhos pela página.')
          try:
            servidor.desktop.abrir_pasta()
          except OSError:
            self.json(500, {'erro': 'Não foi possível abrir a pasta configurada. Confira o acesso e tente novamente.'})
            return
          self.json(200, {'aberta': True})
          return
        elif self.path == '/api/exportar' and servidor.desktop is not None:
          if dados:
            raise ValueError('A exportação não recebe caminhos nem conteúdo da página.')
          try:
            salvo = servidor.desktop.exportar()
          except OSError:
            self.json(500, {'erro': 'Não foi possível salvar o resultado. Confira a pasta e tente exportar novamente.'})
            return
          self.json(200, {'salvo': salvo})
          return
        else:
          self.json(404, {'erro': 'Ação não encontrada.'})
          return
        self.json(200, {'ok': True})
      except (ValueError, TypeError, UnicodeError) as erro:
        self.json(400, {'erro': str(erro)})

  servidor = ServidorInterface(Manipulador, estado)
  return servidor
