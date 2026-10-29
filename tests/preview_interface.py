"""Laboratório manual isolado: mesma interface, somente resultados fictícios."""
from contextlib import contextmanager
from html import escape
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
from threading import Thread

from src.controlador_web import (EstadoInterface, mensagem_erro_documento,
                                 PastaDestinoIndisponivel, EmitentesIndisponiveis,
                                 FalhaGravacaoDocumento)
from src.interface_web import criar_servidor


CENARIOS = (
  ('Sucesso', '1001', 'Conclui uma nota fictícia.'),
  ('Nenhuma nota encontrada', '1002', 'Exibe a ausência de documento na competência.'),
  ('Escolher entre emitentes', '1003', 'Abre a escolha entre dois fornecedores fictícios.'),
  ('Emitente novo / apelido', '1004', 'Pede o apelido. Experimente vazio ou caracteres inválidos antes de confirmar.'),
  ('XML inválido', '1005', 'Exibe uma falha de validação do XML.'),
  ('PDF inválido', '1006', 'Exibe uma falha de validação do PDF.'),
  ('Falha ao gravar', '1007', 'Exibe uma falha de acesso à pasta, sem gravar arquivos.'),
  ('Conferir sinalização', '1008', 'Simula documentos salvos com confirmação pendente no portal.'),
  ('Arquivos já existentes', '1009', 'Simula o reaproveitamento de arquivos válidos.'),
  ('Parar durante o processamento', '1010, 1001', 'Mantém a primeira nota processando por 12 segundos para testar Parar processamento.'),
  ('Nomes e mensagens longos', '1011', 'Mostra textos extensos na decisão e no resultado.'),
  ('Lote misto', '1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008, 1009', 'Combina sucessos, perguntas, erros e atenção.'),
  ('Lote com 80 notas', ', '.join(str(n) for n in range(2000, 2080)), 'Alterna resultados para testar contadores e rolagem.'),
  ('Perda de resposta / reconexão', '1001', 'Perde a resposta de início e duas leituras de estado. A interface deve recuperar sem reenviar o lote.'),
  ('HTTP 503 ao acessar o Cofre', '1012, 1001', 'Simula serviço indisponível no acesso inicial. O lote encerra e as notas ficam não processadas.'),
  ('HTTP 503 na consulta / baixa', '1013, 1001', 'Simula uma falha do portal por documento. A primeira nota fica com erro e a próxima continua.'),
  ('HTTP 503 na sinalização', '1014, 1001', 'Simula falha de sinalização após a gravação fictícia. A primeira nota pede conferência e a próxima continua.'),
  ('Tempo de resposta excedido', '1015', 'Simula o Cofre sem responder dentro do prazo.'),
  ('Falha de conexão sem HTTP', '1016', 'Simula falha de comunicação sem resposta HTTP.'),
  ('Pasta de destino indisponível', '1017', 'Simula indisponibilidade de DOCUMENTOS DE ENTRADA.'),
  ('Arquivo de emitentes indisponível', '1018', 'Simula catálogo de emitentes indisponível.'),
)


def pausar(estado, segundos):
  estado.parada.wait(segundos)
  estado.verificar_parada()


def falhar_http503():
  from requests import Response
  resposta = Response()
  resposta.status_code = 503
  resposta.reason = 'Service Unavailable'
  resposta.url = 'https://cofre.invalid/simulacao'
  resposta.raise_for_status()


def simular(pedido, estado):
  from requests import Timeout, ConnectionError
  falhas_iniciais = {1015: Timeout, 1016: ConnectionError,
                    1017: PastaDestinoIndisponivel, 1018: EmitentesIndisponiveis}
  for nota in pedido.notas:
    if int(nota) in falhas_iniciais:
      raise falhas_iniciais[int(nota)]()
  if any(int(nota) == 1012 for nota in pedido.notas):
    estado.informar('Conectando ao Cofre NF-e…')
    pausar(estado, .8)
    falhar_http503()
  for indice, nota in enumerate(pedido.notas):
    estado.verificar_parada()
    estado.atualizar_nota(indice, 'Processando', 'SIMULAÇÃO · Preparando resultado fictício.')
    pausar(estado, 12 if int(nota) == 1010 else .35)
    codigo = int(nota)
    if 2000 <= codigo < 2080:
      codigo = (1001, 1007, 1008, 1009)[(codigo - 2000) % 4]
    detalhe = 'SIMULAÇÃO · XML e PDF conferidos; nenhum arquivo fiscal foi gravado.'
    situacao = 'Concluído'
    if codigo == 1002:
      situacao, detalhe = 'Erro', 'Nenhuma nota encontrada'
    elif codigo == 1003:
      escolhido = estado.perguntar('emitente', nota=nota, opcoes=[
        {'nome': 'FORNECEDOR FICTÍCIO A', 'data': '01/10/2026', 'valor': '100,00'},
        {'nome': 'FORNECEDOR FICTÍCIO B', 'data': '02/10/2026', 'valor': '200,00'},
      ])
      detalhe = f'SIMULAÇÃO · Emitente {"A" if escolhido == "0" else "B"} confirmado.'
    elif codigo in (1004, 1011):
      emitente = 'FORNECEDOR FICTÍCIO DE DEMONSTRAÇÃO'
      if codigo == 1011:
        emitente += ' COM NOME EXTENSO PARA CONFERÊNCIA DE QUEBRA DE LINHA E ACENTUAÇÃO'
      nome = estado.solicitar_nome(emitente)
      detalhe = f'SIMULAÇÃO · Apelido {nome} confirmado somente nesta execução.'
      if codigo == 1011:
        detalhe += ' · DOCUMENTOS DE ENTRADA / FORNECEDOR COM RAZÃO SOCIAL EXTENSA / ' + ('SUBPASTA-DE-DEMONSTRAÇÃO-' * 8)
    elif codigo in (1005, 1006):
      situacao = 'Erro'
      detalhe = 'SIMULAÇÃO · ' + {
        1005: 'XML inválido: conteúdo incompleto. Arquivos anteriores preservados.',
        1006: 'PDF inválido: arquivo protegido ou incompleto. Arquivos anteriores preservados.',
      }[codigo]
    elif codigo == 1007:
      erro = FalhaGravacaoDocumento()
      estado.avisar_falha_operacao(erro)
      situacao, detalhe = 'Erro', mensagem_erro_documento(erro, False)
    elif codigo == 1008:
      erro = RuntimeError()
      estado.avisar_falha_operacao(erro, True)
      situacao, detalhe = 'Conferir sinalização', mensagem_erro_documento(erro, True)
    elif codigo == 1009:
      detalhe = 'SIMULAÇÃO · Arquivos válidos já existentes foram reaproveitados.'
    elif codigo in (1013, 1014):
      from requests import HTTPError
      try:
        falhar_http503()
      except HTTPError as erro:
        salvo = codigo == 1014
        estado.avisar_falha_operacao(erro, salvo)
        situacao = 'Conferir sinalização' if salvo else 'Erro'
        detalhe = mensagem_erro_documento(erro, salvo)
    estado.atualizar_nota(indice, situacao, detalhe)


def criar_previa():
  estado = EstadoInterface(simular)
  estado.informar('SIMULAÇÃO · Selecione um cenário, prepare as notas e clique em Baixar.')
  servidor = criar_servidor(estado)
  base = servidor.RequestHandlerClass
  pasta = Path(__file__).parent
  opcoes = ''.join(f'<option value="{i}" data-notas="{escape(notas, quote=True)}" data-ajuda="{escape(ajuda, quote=True)}">{escape(nome)}</option>'
                    for i, (nome, notas, ajuda) in enumerate(CENARIOS))
  painel = ('<section id="simulacao" aria-labelledby="titulo-simulacao">'
            '<h2 id="titulo-simulacao">SIMULAÇÃO · Sem portal, arquivos fiscais ou estatísticas reais</h2>'
            '<div class="simulacao-controles"><label for="cenario">Cenário de teste</label>'
            f'<select id="cenario">{opcoes}</select>'
            '<button id="preparar-cenario" type="button">Preparar cenário</button></div>'
            '<p id="ajuda-cenario" role="status"></p></section>').encode('utf-8')

  class Previa(base):
    def responder(self, status, conteudo, tipo='application/json; charset=utf-8'):
      if status == 200 and self.path == '/' and tipo.startswith('text/html'):
        conteudo = conteudo.replace(b'</head>', b'<link rel="stylesheet" href="/simulacao.css"><script src="/simulacao.js" defer></script></head>')
        conteudo = conteudo.replace(b'</header>', b'</header>' + painel, 1)
        conteudo = conteudo.replace(b'<title>Cofre NF-e', '<title>SIMULAÇÃO · Cofre NF-e'.encode('utf-8'))
      super().responder(status, conteudo, tipo)

    def do_GET(self):
      if self.path in ('/simulacao.js', '/simulacao.css'):
        if not self.host_valido():
          self.json(403, {'erro': 'Acesso local inválido.'})
          return
        tipo = 'text/javascript' if self.path.endswith('.js') else 'text/css'
        self.responder(200, (pasta / self.path[1:]).read_bytes(), tipo + '; charset=utf-8')
        return
      super().do_GET()

    def do_POST(self):
      # Configurações e diálogos de arquivos não fazem parte da simulação.
      if self.path not in ('/api/iniciar', '/api/responder', '/api/parar', '/api/fechar', '/api/entrada-notas', '/api/tema'):
        self.close_connection = True
        tamanhos = self.headers.get_all('Content-Length') or []
        if len(tamanhos) == 1 and tamanhos[0].isascii() and tamanhos[0].isdigit() and len(tamanhos[0]) <= 5:
          tamanho = int(tamanhos[0])
          if tamanho <= 65536:
            self.rfile.read(tamanho)
        self.json(403, {'erro': 'Ação indisponível no modo de simulação.'})
        return
      super().do_POST()

  servidor.RequestHandlerClass = Previa
  return servidor


@contextmanager
def ambiente_isolado():
  from unittest.mock import patch
  with tempfile.TemporaryDirectory(prefix='cofre-simulacao-', ignore_cleanup_errors=True) as temporario:
    raiz = Path(temporario)
    perfil = raiz / 'perfil/Nunes/Cofre'
    perfil.mkdir(parents=True)
    (perfil / 'desktop-emitentes.json').write_text(json.dumps({'formato': 1, 'arquivo': str(raiz / 'emitentes-ficticios.json')}), encoding='utf-8')
    variaveis = {'LOCALAPPDATA': str(raiz / 'perfil'), 'NUNES_COFRE_DADOS': str(raiz / 'dados'),
                 'NUNES_HUB_DADOS': str(raiz / 'presenca'), 'NUNES_METRICAS_DADOS': str(raiz / 'metricas'),
                 'NUNES_CENTRAL_CONFIG': str(raiz / 'sem-central.json'),
                 'CAMINHO_DOCUMENTO_ENTRADA': str(raiz / 'DOCUMENTOS-FICTICIOS')}
    conectar, conectar_ex, resolver = socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo

    def conferir(destino):
      if not isinstance(destino, tuple) or destino[0] not in ('127.0.0.1', '::1', 'localhost'):
        raise OSError('Rede externa bloqueada no modo de simulação.')

    def local(sock, destino):
      conferir(destino)
      return conectar(sock, destino)

    def local_ex(sock, destino):
      conferir(destino)
      return conectar_ex(sock, destino)

    def resolver_local(host, *args, **kwargs):
      if host not in ('127.0.0.1', '::1', 'localhost', None):
        raise OSError('Rede externa bloqueada no modo de simulação.')
      return resolver(host, *args, **kwargs)

    with patch.dict(os.environ, variaveis), patch.object(socket.socket, 'connect', local), patch.object(socket.socket, 'connect_ex', local_ex), patch.object(socket, 'getaddrinfo', resolver_local):
      yield raiz


def executar_desktop(servidor):
  from dpi_windows import preparar, validar_janela
  preparar('CofreSimulacao')
  import desktop_windows
  desktop_windows.identidade_processo('Nunes.Cofre.Simulacao.1')
  import webview
  servidor.modo_desktop = True
  webview.settings['ALLOW_DOWNLOADS'] = False
  webview.settings['ALLOW_FILE_URLS'] = False
  janela = webview.create_window('Cofre NF-e · SIMULAÇÃO', f'http://127.0.0.1:{servidor.server_port}',
                               width=1009, height=700, min_size=(390, 420), resizable=True, text_select=True)
  liberar = False
  falhas = []

  def fechar():
    if liberar:
      return True
    if servidor.estado.snapshot()['ativo'] and not janela.create_confirmation_dialog('Simulação', 'Parar a simulação e fechar a janela?'):
      return False
    servidor.estado.encerrar()
    return False

  janela.events.closing += fechar

  def acompanhar():
    nonlocal liberar
    try:
      if not janela.events.shown.wait(30):
        raise RuntimeError('A janela de simulação não iniciou.')
      validar_janela(janela.native.Handle.ToInt64())
      while not servidor.finalizando.wait(.1):
        if servidor.fechando:
          break
    except Exception as erro:
      falhas.append(erro)
      servidor.estado.encerrar()
    liberar = True
    janela.destroy()

  thread = Thread(target=servidor.serve_forever, kwargs={'poll_interval': .1}, daemon=True)
  thread.start()
  try:
    webview.start(acompanhar, gui='edgechromium', private_mode=True)
    if falhas:
      raise RuntimeError('Falha ao abrir a simulação.') from falhas[0]
  finally:
    servidor.estado.encerrar()
    servidor.shutdown()
    thread.join(5)


def main():
  import argparse
  parser = argparse.ArgumentParser(description='Simulação isolada do Cofre NF-e')
  parser.add_argument('--desktop', action='store_true', help='Abrir em janela WebView2')
  args = parser.parse_args()
  with ambiente_isolado():
    servidor = criar_previa()
    if sys.stdout is not None:
      print(f'http://127.0.0.1:{servidor.server_port}', flush=True)
    try:
      if args.desktop:
        executar_desktop(servidor)
      else:
        servidor.serve_forever(poll_interval=.1)
    finally:
      servidor.server_close()
      if servidor.estado.worker:
        servidor.estado.worker.join()


if __name__ == '__main__':
  try:
    main()
  except Exception as erro:
    if os.name != 'nt':
      raise
    import ctypes
    ctypes.windll.user32.MessageBoxW(None, str(erro), 'Falha na simulação do Cofre NF-e', 0x10)
    raise SystemExit(1)
