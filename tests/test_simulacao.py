"""Cenários manuais reproduzíveis, sem integração fiscal nem dados reais."""
import json
import os
from pathlib import Path
import re
import socket
from http.client import HTTPConnection
from threading import Event, Thread
import unittest
from unittest.mock import patch

from src.controlador_web import EstadoInterface, mensagem_erro_documento
from src.interface_web import criar_servidor
from tests.preview_interface import ambiente_isolado, criar_previa, simular
from tests.test_interface_web import entrada


class TestSimulacao(unittest.TestCase):
  def setUp(self):
    self.raiz = self.enterContext(ambiente_isolado())
    self.enterContext(patch('tests.preview_interface.pausar', side_effect=lambda estado, segundos: estado.verificar_parada()))

  def executar(self, notas, **campos):
    estado = EstadoInterface(simular)
    self.addCleanup(estado.encerrar)
    estado.iniciar(entrada(notas=notas, **campos))
    return estado

  def concluir(self, estado):
    estado.worker.join(2)
    self.assertFalse(estado.worker.is_alive())
    return estado.snapshot()

  def test_resultados_previsiveis_para_nfe_cte_matriz_e_filial(self):
    for tipo, empresa in [('nfe', 'MATRIZ'), ('cte', 'FILIAL')]:
      dados = self.concluir(self.executar('1001,1002,1005,1006,1007,1008,001009', tipo=tipo, empresa=empresa))
      self.assertEqual([r['situacao'] for r in dados['resultados']], ['Concluído', 'Erro', 'Erro', 'Erro', 'Erro', 'Conferir sinalização', 'Concluído'])
      self.assertEqual(dados['resultados'][1]['detalhe'], 'Nenhuma nota encontrada')
      self.assertEqual(dados['resultados'][-1]['nota'], '001009')
    self.assertEqual(list(self.raiz.rglob('*.xml')), [])
    self.assertEqual(list(self.raiz.rglob('*.pdf')), [])
    self.assertEqual(list(self.raiz.rglob('*.sqlite3')), [])

  def test_lote_extenso_contem_todos_os_estados_sem_perguntas(self):
    dados = self.concluir(self.executar(','.join(str(n) for n in range(2000, 2080))))
    situacoes = [r['situacao'] for r in dados['resultados']]
    self.assertEqual(situacoes.count('Concluído'), 40)
    self.assertEqual(situacoes.count('Erro'), 20)
    self.assertEqual(situacoes.count('Conferir sinalização'), 20)

  def test_http503_no_acesso_encerra_o_lote_antes_de_processar(self):
    dados = self.concluir(self.executar('1012,1001'))
    self.assertFalse(dados['ativo'])
    self.assertIsNone(dados['pergunta'])
    self.assertEqual(dados['status'], 'Erro 503: Falha na comunicação com o Cofre.')
    self.assertEqual(dados['aviso_portal']['status'], 503)
    self.assertRegex(dados['aviso_portal']['id'], r'^[0-9a-f]{32}$')
    self.assertEqual([r['situacao'] for r in dados['resultados']], ['Não processado', 'Não processado'])

  def test_http503_por_documento_preserva_diferenca_entre_baixa_e_sinalizacao(self):
    for nota, situacao in [('1013', 'Erro'), ('1014', 'Conferir sinalização')]:
      with self.subTest(nota=nota), patch('tests.preview_interface.mensagem_erro_documento', wraps=mensagem_erro_documento) as traduzir:
        dados = self.concluir(self.executar(nota + ',1001'))
        self.assertEqual([r['situacao'] for r in dados['resultados']], [situacao, 'Concluído'])
        esperado = ('XML e PDF salvos; não foi possível confirmar a sinalização no Cofre.'
                    if nota == '1014' else 'Falha na comunicação com o Cofre.')
        self.assertEqual(dados['aviso_portal']['status'], 503)
        self.assertEqual(dados['resultados'][0]['detalhe'], esperado)
        self.assertEqual(traduzir.call_args.args[0].response.status_code, 503)
        if nota == '1014':
          self.assertTrue(dados['resultados'][0]['detalhe'].startswith('XML e PDF salvos;'))
          self.assertEqual(dados['aviso_portal']['tipo'], 'sinalizacao')
    for extensao in ['*.xml', '*.pdf', '*.sqlite3']:
      self.assertEqual(list(self.raiz.rglob(extensao)), [])

  def pergunta(self, estado):
    with estado.condicao:
      self.assertTrue(estado.condicao.wait_for(lambda: estado.dados['pergunta'] is not None, 2))
      return estado.snapshot()['pergunta']

  def test_orientacoes_e_detalhes_dos_novos_cenarios(self):
    for nota, tipo, detalhe in (
      ('1015', 'timeout', 'O Cofre não respondeu dentro do prazo.'),
      ('1016', 'comunicacao', 'Falha na comunicação com o Cofre.'),
      ('1017', 'pasta_destino', 'Não foi possível acessar a pasta DOCUMENTOS DE ENTRADA.'),
      ('1018', 'emitentes', 'O arquivo de emitentes está indisponível.'),
      ('1007', 'gravacao', 'Não foi possível gravar os arquivos do documento.'),
      ('1008', 'sinalizacao', 'XML e PDF salvos; não foi possível confirmar a sinalização no Cofre.'),
    ):
      with self.subTest(nota=nota):
        estado = self.executar(nota)
        dados = self.concluir(estado)
        self.assertEqual(dados['aviso_portal']['tipo'], tipo)
        self.assertIsNone(dados['aviso_portal']['status'])
        texto = dados['status'] if int(nota) >= 1015 else dados['resultados'][0]['detalhe']
        self.assertIn(detalhe, texto)
        identificador = dados['aviso_portal']['id']
        self.assertEqual(estado.snapshot()['aviso_portal']['id'], identificador)

  def test_escolha_de_emitente_e_apelido_usam_validacoes_reais(self):
    estado = self.executar('1003,1004,1011')
    self.addCleanup(lambda: estado.worker.join(2))
    pergunta = self.pergunta(estado)
    self.assertEqual(pergunta['nota'], '1003')
    with self.assertRaises(ValueError):
      estado.responder({'id': pergunta['id'], 'valor': '5'})
    estado.responder({'id': pergunta['id'], 'valor': '1'})
    for apelido in ['FORNECEDOR NOVO', 'FORNECEDOR LONGO']:
      with estado.condicao:
        self.assertTrue(estado.condicao.wait_for(lambda: estado.dados['pergunta'] is not None and estado.dados['pergunta']['id'] != pergunta['id'], 2))
        pergunta = estado.snapshot()['pergunta']
      self.assertEqual(pergunta['tipo'], 'nome')
      with self.assertRaises(ValueError):
        estado.responder({'id': pergunta['id'], 'valor': '///'})
      estado.responder({'id': pergunta['id'], 'valor': apelido})
    dados = self.concluir(estado)
    self.assertTrue(all(r['situacao'] == 'Concluído' for r in dados['resultados']))
    self.assertIn('Emitente B', dados['resultados'][0]['detalhe'])
    self.assertGreater(len(dados['resultados'][-1]['detalhe']), 200)

  def test_parada_interrompe_a_espera_e_preserva_concluidos(self):
    esperando = Event()

    def pausar(estado, segundos):
      if segundos == 12:
        esperando.set()
        estado.parada.wait(2)
      estado.verificar_parada()

    with patch('tests.preview_interface.pausar', side_effect=pausar):
      estado = self.executar('1001,1010,1009')
      self.assertTrue(esperando.wait(2))
      estado.parar()
      dados = self.concluir(estado)
    self.assertEqual([r['situacao'] for r in dados['resultados']], ['Concluído', 'Não processado', 'Não processado'])

  def test_rede_e_preferencias_ficam_isoladas(self):
    self.assertTrue(Path(os.environ['LOCALAPPDATA']).is_relative_to(self.raiz))
    for nome in ['NUNES_COFRE_DADOS', 'NUNES_HUB_DADOS', 'NUNES_METRICAS_DADOS', 'NUNES_CENTRAL_CONFIG']:
      self.assertTrue(Path(os.environ[nome]).is_relative_to(self.raiz))
    with socket.socket() as sock:
      for metodo in [sock.connect, sock.connect_ex]:
        with self.assertRaisesRegex(OSError, 'Rede externa bloqueada'):
          metodo(('203.0.113.1', 443))
    with self.assertRaisesRegex(OSError, 'Rede externa bloqueada'):
      socket.getaddrinfo('example.com', 443)


class TestHTTPPrevia(unittest.TestCase):
  def setUp(self):
    self.enterContext(ambiente_isolado())
    self.servidor = criar_previa()
    self.thread = Thread(target=self.servidor.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
    self.thread.start()
    self.addCleanup(self.fechar)
    self.origem = f'http://127.0.0.1:{self.servidor.server_port}'
    _, pagina = self.requisitar('GET', '/')
    self.token = re.search(rb'name="cofre-token" content="([^"]+)"', pagina).group(1).decode()

  def fechar(self):
    self.servidor.estado.encerrar()
    if self.servidor.estado.worker:
      self.servidor.estado.worker.join(2)
    self.servidor.shutdown()
    self.servidor.server_close()
    self.thread.join(2)

  def requisitar(self, metodo, caminho, dados=None, autorizado=False, host=None):
    conexao = HTTPConnection('127.0.0.1', self.servidor.server_port, timeout=3)
    headers = {'Host': host or f'127.0.0.1:{self.servidor.server_port}'}
    if autorizado:
      headers.update(Authorization='Bearer ' + self.token, Origin=self.origem)
    corpo = None
    if dados is not None:
      headers['Content-Type'] = 'application/json'
      corpo = json.dumps(dados)
    conexao.request(metodo, caminho, body=corpo, headers=headers)
    resposta = conexao.getresponse()
    retorno = resposta.status, resposta.read()
    conexao.close()
    return retorno

  def test_painel_e_recursos_exclusivos_da_previa(self):
    codigo, pagina = self.requisitar('GET', '/')
    self.assertEqual(codigo, 200)
    self.assertIn(b'id="simulacao"', pagina)
    self.assertEqual(pagina.count(b'<option '), 21)
    self.assertIn(b'HTTP 503 ao acessar o Cofre', pagina)
    self.assertIn(b'HTTP 503 na consulta / baixa', pagina)
    self.assertIn('HTTP 503 na sinalização'.encode('utf-8'), pagina)
    for recurso in ['/simulacao.css', '/simulacao.js']:
      self.assertEqual(self.requisitar('GET', recurso)[0], 200)
      self.assertEqual(self.requisitar('GET', recurso, host='example.com')[0], 403)
    self.assertEqual(self.requisitar('GET', '/simulacao/../preview_interface.py')[0], 404)
    producao = criar_servidor(EstadoInterface())
    try:
      self.assertNotEqual(producao.RequestHandlerClass, self.servidor.RequestHandlerClass)
    finally:
      producao.server_close()

  def test_inicio_continua_autenticado_e_pastas_ficam_bloqueadas(self):
    self.assertEqual(self.requisitar('POST', '/api/iniciar', entrada(notas='1001'))[0], 403)
    self.assertEqual(self.requisitar('POST', '/api/iniciar', entrada(notas='1001'), autorizado=True)[0], 200)
    self.servidor.estado.worker.join(2)
    self.assertEqual(self.servidor.estado.snapshot()['resultados'][0]['situacao'], 'Concluído')
    for caminho in ['/api/pasta', '/api/emitentes', '/api/emitentes/editar', '/api/pasta/abrir', '/api/exportar']:
      self.assertEqual(self.requisitar('POST', caminho, {}, autorizado=True)[0], 403)

  def test_http503_do_portal_mantem_api_local_disponivel(self):
    self.assertEqual(self.requisitar('POST', '/api/iniciar', entrada(notas='1012,1001'), autorizado=True)[0], 200)
    self.servidor.estado.worker.join(3)
    status, corpo = self.requisitar('GET', '/api/estado', autorizado=True)
    self.assertEqual(status, 200)
    dados = json.loads(corpo)
    self.assertFalse(dados['ativo'])
    self.assertTrue(all(r['situacao'] == 'Não processado' for r in dados['resultados']))
    self.assertEqual(dados['status'], 'Erro 503: Falha na comunicação com o Cofre.')
