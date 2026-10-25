"""Janela Cofre: HTTP local autenticado, sem API Python exposta à página."""
import json
import os
from pathlib import Path
import secrets
import sys
import time
from threading import Event, Thread
from threading import Lock
from datetime import datetime, timezone
from http.client import HTTPException
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, HTTPRedirectHandler, build_opener

import desktop_windows
from integracao_hub import consultar_instancia, gravar_registro, ler_registro, texto, trava_ocupada
from src.caminhos import pasta_preferencias, recursos, documentos_entrada, salvar_documentos_entrada

APP_ID = 'Nunes.Cofre.Desktop.1'
NOME = 'Cofre NF-e'


class SemRedirecionamento(HTTPRedirectHandler):
  def redirect_request(self, req, fp, code, msg, headers, newurl):
    return None


def ler_tema():
  try:
    dados = json.loads((pasta_preferencias() / 'desktop-tema.json').read_text(encoding='utf-8'))
    if isinstance(dados, dict) and dados.get('tema') in ('claro', 'escuro'):
      return dados['tema']
  except (OSError, ValueError):
    pass
  return 'claro'


def salvar_tema(tema):
  if tema not in ('claro', 'escuro'):
    raise ValueError('Tema inválido.')
  pasta = pasta_preferencias()
  pasta.mkdir(parents=True, exist_ok=True)
  gravar_registro(pasta / 'desktop-tema.json', {'tema': tema})


def ativar_existente(caminho, espera=15):
  limite = time.monotonic() + espera
  while time.monotonic() < limite:
    if not trava_ocupada(caminho.with_suffix('.lock')):
      return False
    registro = ler_registro(caminho)
    saude = consultar_instancia(registro)
    if saude.get('respondendo') and not saude.get('encerrando'):
      if registro.get('id') != 'cofre-nfe':
        raise RuntimeError('O registro localizado não pertence ao Cofre NF-e.')
      desktop_windows.permitir_foco(registro['pid'])
      pedido = Request(texto(registro['url']) + '/desktop/ativar', data=b'{}', method='POST',
                       headers={'X-Nunes-Instancia': texto(registro['token']), 'Content-Type': 'application/json'})
      try:
        with build_opener(ProxyHandler({}), SemRedirecionamento()).open(pedido, timeout=3) as resposta:
          dados = json.loads(resposta.read(4096))
      except HTTPError as erro:
        codigo = erro.code
        try:
          motivo = json.loads(erro.read(4096)) if codigo == 409 else {}
        finally:
          erro.close()
        if codigo == 409 and isinstance(motivo, dict) and motivo.get('estado') == 'encerrando':
          time.sleep(.1)
          continue
        raise RuntimeError('A instância existente recusou a ativação. Feche a versão anterior normalmente e reabra.') from erro
      except (OSError, HTTPException):
        time.sleep(.1)
        continue
      if (not isinstance(dados, dict) or dados.get('protocolo') != 1 or dados.get('id') != 'cofre-nfe'
          or dados.get('instancia') != registro.get('instancia') or dados.get('pid') != registro.get('pid')
          or dados.get('desktop') != 1):
        raise RuntimeError('Resposta de ativação de outra instância ou versão da Cofre.')
      return True
    time.sleep(.1)
  raise RuntimeError('A Cofre está iniciando, sem resposta ou encerrando. Aguarde e tente novamente.')


def atender_ativacao(handler):
  if handler.path != '/desktop/ativar':
    return False
  servidor = handler.server
  integracao = getattr(servidor, 'integracao_nunes', None)
  corpo = None
  tamanhos = handler.headers.get_all('Content-Length') or []
  if handler.command == 'POST' and len(tamanhos) == 1 and tamanhos[0].isascii() and tamanhos[0].isdigit():
    tamanho = int(tamanhos[0]) if len(tamanhos[0]) <= 4 else 4097
    if tamanho <= 4096:
      corpo = handler.rfile.read(tamanho)
  if (not handler.host_valido() or integracao is None or handler.headers.get_all('Origin') is not None
      or len(handler.headers.get_all('X-Nunes-Instancia') or []) != 1
      or not secrets.compare_digest(handler.headers.get('X-Nunes-Instancia', '').encode(),
                                    texto(integracao.registro['token']).encode())):
    handler.json(403, {'erro': 'Ativação não autorizada.'})
  elif handler.command != 'POST':
    handler.json(405, {'erro': 'Método não permitido.'})
  elif (handler.headers.get_all('Content-Length') != ['2']
        or handler.headers.get_all('Content-Type') != ['application/json'] or corpo != b'{}'):
    handler.json(400, {'erro': 'Pedido de ativação inválido.'})
  elif servidor.estado.encerrando:
    handler.json(409, {'erro': 'A Cofre está encerrando.', 'estado': 'encerrando'})
  elif servidor.desktop is None:
    handler.json(409, {'erro': 'Instância sem janela desktop.', 'estado': 'sem_desktop'})
  else:
    servidor.desktop.ativar.set()
    handler.json(200, {chave: integracao.registro[chave] for chave in
                      ('protocolo', 'id', 'instancia', 'pid')} | {'desktop': 1})
  return True


class Janela:
  def __init__(self, servidor):
    self.servidor = servidor
    self.ativar = Event()
    self.fechada = Event()
    self.erro = None
    self.liberar = False
    self.exportando = Lock()
    self.janela = None

  def escolher_pasta(self):
    estado = self.servidor.estado
    with estado.condicao:
      if estado.encerrando or estado.dados['ativo'] or estado.configurando or self.janela is None:
        raise ValueError('Aguarde o fim da execução ou da escolha de pasta atual.')
      if not self.exportando.acquire(blocking=False):
        raise ValueError('Há um diálogo aberto. Conclua ou cancele antes de escolher a pasta.')
      estado.configurando = True
    try:
      import webview
      try:
        inicial = documentos_entrada() or str(Path.home())
      except ValueError:
        inicial = str(Path.home())
      destino = self.janela.create_file_dialog(webview.FileDialog.FOLDER, directory=inicial)
      if not destino:
        return {'alterado': False}
      caminho = destino[0] if isinstance(destino, (tuple, list)) else destino
      with estado.condicao:
        if estado.encerrando:
          raise ValueError('A Cofre está encerrando; a pasta não foi alterada.')
        salvo = salvar_documentos_entrada(caminho)
      return {'alterado': True, 'pasta': salvo}
    finally:
      with estado.condicao:
        estado.configurando = False
        estado.condicao.notify_all()
      self.exportando.release()

  def exportar(self):
    if not self.exportando.acquire(blocking=False):
      raise ValueError('Há um diálogo aberto. Conclua ou cancele antes de exportar.')
    try:
      estado = self.servidor.estado.snapshot()
      if estado['ativo'] or estado['encerrando'] or not estado['resultados'] or self.janela is None:
        raise ValueError('Aguarde o fim da execução antes de exportar o resultado.')
      import webview
      destino = self.janela.create_file_dialog(webview.FileDialog.SAVE, directory=str(Path.home()),
        save_filename='resultado-cofre.json', file_types=('JSON (*.json)',))
      if not destino:
        return False
      # O caminho vem exclusivamente do diálogo nativo, nunca do pedido HTTP.
      caminho = Path(destino[0] if isinstance(destino, (list, tuple)) else destino)
      gravar_registro(caminho, {'exportado_em': datetime.now(timezone.utc).isoformat(), **estado})
      return True
    finally:
      self.exportando.release()

  def fechar(self, janela):
    if self.liberar:
      desktop_windows.salvar_geometria(janela.native, pasta_preferencias())
      return True
    estado = self.servidor.estado
    if estado.encerrando:
      return False
    if estado.snapshot()['ativo'] and not janela.create_confirmation_dialog(NOME,
        'Encerrar a Cofre NF-e? A operação em curso será concluída antes da parada. Aguarde a janela fechar.'):
      return False
    estado.encerrar()
    return False

  def aguardar(self, evento, limite=30):
    fim = time.monotonic() + limite
    while not self.fechada.is_set() and not self.servidor.estado.encerrando:
      if evento.wait(.1):
        return True
      if time.monotonic() >= fim:
        raise RuntimeError('A janela ou a interface WebView2 não iniciou no prazo.')
    return False

  def executar(self):
    if os.name != 'nt':
      raise RuntimeError('O desktop da Cofre requer Windows.')
    import webview
    desktop_windows.identidade_processo(APP_ID)
    webview.settings['ALLOW_DOWNLOADS'] = False
    webview.settings['ALLOW_FILE_URLS'] = False
    janela = webview.create_window(NOME, f'http://127.0.0.1:{self.servidor.server_port}',
                                  width=1080, height=780, min_size=(760, 540), text_select=True)
    self.janela = janela

    def restaurar():
      dados = desktop_windows.ler_geometria(pasta_preferencias())
      if dados:
        desktop_windows.restaurar_geometria(janela.native, dados)

    janela.events.before_show += restaurar
    janela.events.closing += lambda: self.fechar(janela)

    def fechou():
      self.fechada.set()
      self.servidor.estado.encerrar()

    janela.events.closed += fechou

    def acompanhar():
      try:
        if not self.aguardar(janela.events.shown):
          self.liberar = True
          janela.destroy()
          return
        hwnd = janela.native.Handle.ToInt64()
        desktop_windows.propriedades_janela(hwnd,
          desktop_windows.comando_reabrir([], Path(__file__).with_name('cofre.py')),
          recursos() / 'icons/icone.ico', app_id=APP_ID, nome=NOME)
        carregou = self.aguardar(janela.events.loaded)
        avisou = False
        while not self.fechada.wait(.1):
          if self.servidor.estado.encerrando and not avisou:
            avisou = True
            janela.set_title('Cofre NF-e · Encerrando — aguarde a operação atual')
            if carregou:
              janela.evaluate_js('atualizar()')
          if self.servidor.fechando:
            self.liberar = True
            janela.destroy()
            return
          if self.ativar.is_set():
            self.ativar.clear()
            desktop_windows.focalizar(hwnd)
      except Exception as erro:
        if not self.fechada.is_set():
          self.erro = erro
          self.servidor.estado.encerrar()
          # Mesmo uma falha da GUI aguarda o executor alcançar a fronteira segura.
          while self.servidor.estado.snapshot()['ativo']:
            time.sleep(.1)
          self.liberar = True
          janela.destroy()

    webview.start(acompanhar, gui='edgechromium', debug=False, private_mode=True,
                  icon=str(recursos() / 'icons/icone.ico'))
    self.fechada.set()
    if self.erro:
      raise RuntimeError('Falha na janela desktop. Confira WebView2 e o diagnóstico local.') from self.erro


def executar(servidor):
  janela = Janela(servidor)
  servidor.desktop = janela
  falhas = []

  def servir():
    try:
      servidor.serve_forever(poll_interval=.1)
    except Exception as erro:
      falhas.append(erro)
      servidor.estado.encerrar()
      servidor.fechando = True

  thread = Thread(target=servir, name='cofre-http', daemon=True)
  thread.start()
  try:
    janela.executar()
    if falhas:
      raise RuntimeError('O backend da Cofre encerrou com falha.') from falhas[0]
  finally:
    servidor.estado.encerrar()
    if servidor.estado.worker:
      servidor.estado.worker.join()
    servidor.shutdown()
    thread.join(5)
    servidor.desktop = None
