"""Contratos desktop e persistência isolada; nenhum acesso ao portal."""
import http.client
import json
import os
from pathlib import Path
import tempfile
from threading import Event, Thread
import unittest
from unittest.mock import Mock, patch

import desktop_cofre
from integracao_hub import IntegracaoLocal
from src.caminhos import pasta_dados, pasta_preferencias
from src.controlador_web import EstadoInterface
from src.interface_web import criar_servidor
from tests.test_interface_web import entrada


class TestDesktop(unittest.TestCase):
  def setUp(self):
    self.pasta = Path(self.enterContext(tempfile.TemporaryDirectory()))
    self.enterContext(patch.dict(os.environ, {'NUNES_COFRE_DADOS': str(self.pasta / 'cofre')}))
    self.integracao = self.enterContext(IntegracaoLocal('cofre-nfe', 'Cofre NF-e', False,
                                                       self.pasta / 'presenca', sem_navegador=True))
    self.estado = EstadoInterface()
    self.servidor = criar_servidor(self.estado)
    self.servidor.desktop = Mock(ativar=Event())
    self.servidor.modo_desktop = True
    self.integracao.publicar(self.servidor, self.estado.encerrar)
    self.thread = Thread(target=self.servidor.serve_forever, kwargs={'poll_interval': .01})
    self.thread.start()
    self.addCleanup(self.fechar)

  def fechar(self):
    self.servidor.shutdown()
    self.servidor.server_close()
    self.thread.join(3)
    self.assertFalse(self.thread.is_alive())

  def pedido(self, rota='/desktop/ativar', metodo='POST', corpo=b'{}', headers=None):
    c = http.client.HTTPConnection('127.0.0.1', self.servidor.server_port, timeout=3)
    try:
      c.request(metodo, rota, body=corpo, headers=headers or {})
      r = c.getresponse()
      return r.status, r.read()
    finally:
      c.close()

  def credenciais(self):
    return {'X-Nunes-Instancia': self.integracao.registro['token'], 'Content-Type': 'application/json'}

  def test_ativacao_preserva_estado_e_decisao(self):
    self.estado.dados['pergunta'] = {'id': 'sintetica', 'tipo': 'nome', 'sugestao': 'TESTE'}
    antes = self.estado.snapshot()
    codigo, corpo = self.pedido(headers=self.credenciais())
    self.assertEqual(codigo, 200)
    self.assertEqual(json.loads(corpo)['instancia'], self.integracao.registro['instancia'])
    self.assertTrue(self.servidor.desktop.ativar.is_set())
    self.assertEqual(self.estado.snapshot(), antes)

  def test_recusa_host_origin_token_metodo_corpo(self):
    for extras, metodo, corpo, codigo in [
        ({'Host': 'localhost'}, 'POST', b'{}', 403),
        ({'Origin': 'null'}, 'POST', b'{}', 403),
        ({'X-Nunes-Instancia': 'errado'}, 'POST', b'{}', 403),
        ({}, 'GET', None, 405), ({}, 'POST', b'[]', 400),
        ({'Content-Type': 'text/plain'}, 'POST', b'{}', 400),
        ({}, 'POST', b'{"comando":"outro"}', 400)]:
      with self.subTest(extras=extras, metodo=metodo):
        self.assertEqual(self.pedido(headers=self.credenciais() | extras, metodo=metodo, corpo=corpo)[0], codigo)
        self.assertFalse(self.servidor.desktop.ativar.is_set())

  def test_sem_janela_e_encerrando_nao_ativam(self):
    self.servidor.desktop = None
    self.assertEqual(self.pedido(headers=self.credenciais())[0], 409)
    self.estado.encerrar()
    self.assertEqual(self.pedido(headers=self.credenciais())[0], 409)

  def test_queda_presenca_nao_fecha_desktop(self):
    self.servidor.teve_pagina = True
    self.servidor.sem_paginas_desde = -10000
    self.servidor.service_actions()
    self.assertFalse(self.estado.encerrando)
    self.assertEqual(len(self.servidor.paginas), 0)

  def test_cliente_ativa_somente_instancia_confirmada(self):
    with patch('desktop_windows.permitir_foco') as foco:
      self.assertTrue(desktop_cofre.ativar_existente(self.integracao.caminho, espera=1))
    foco.assert_called_once_with(os.getpid())

  def test_trava_liberada_retorna_ao_iniciador(self):
    with patch('desktop_cofre.trava_ocupada', return_value=False):
      self.assertFalse(desktop_cofre.ativar_existente(self.integracao.caminho))

  def test_tema_http_exige_token_origin_e_persiste(self):
    _, html = self.pedido('/', 'GET', None)
    import re
    token = re.search(rb'name="cofre-token" content="([^"]+)"', html).group(1).decode()
    headers = {'Authorization': 'Bearer ' + token, 'Origin': f'http://127.0.0.1:{self.servidor.server_port}',
               'Content-Type': 'application/json'}
    self.assertEqual(self.pedido('/api/tema', headers=headers, corpo=b'{"tema":"escuro"}')[0], 200)
    self.assertEqual(desktop_cofre.ler_tema(), 'escuro')
    self.assertEqual(self.pedido('/api/tema', headers=headers | {'Origin': 'null'})[0], 403)
    self.assertEqual(self.pedido('/api/tema', headers=headers, corpo=b'{"tema":"outro"}')[0], 400)
    _, html = self.pedido('/', 'GET', None)
    self.assertIn(b'data-tema="escuro"', html)
    self.assertIn(b'name="cofre-desktop" content="1"', html)

  def test_pasta_http_exige_origem_token_e_dialogo_desktop(self):
    import re
    _, html = self.pedido('/', 'GET', None)
    token = re.search(rb'name="cofre-token" content="([^"]+)"', html).group(1).decode()
    headers = {'Authorization': 'Bearer ' + token, 'Origin': f'http://127.0.0.1:{self.servidor.server_port}', 'Content-Type': 'application/json'}
    self.assertEqual(self.pedido('/api/pasta', headers=headers, corpo=b'{"pasta":"C:/qualquer"}')[0], 400)
    self.assertEqual(self.pedido('/api/pasta', headers=headers | {'Origin': 'null'})[0], 403)
    self.assertEqual(self.pedido('/api/pasta', headers=headers | {'Authorization': 'errado'})[0], 403)
    self.servidor.desktop.escolher_pasta.assert_not_called()
    self.servidor.desktop.escolher_pasta.return_value = {'alterado': False}
    codigo, corpo = self.pedido('/api/pasta', headers=headers)
    self.assertEqual((codigo, json.loads(corpo)), (200, {'alterado': False}))
    self.servidor.desktop.escolher_pasta.side_effect = OSError('SINTÉTICO')
    self.assertEqual(self.pedido('/api/pasta', headers=headers)[0], 500)
    self.servidor.modo_desktop = False
    self.assertEqual(self.pedido('/api/pasta', headers=headers)[0], 404)

  def test_exportacao_http_nao_aceita_caminho_da_pagina(self):
    _, html = self.pedido('/', 'GET', None)
    import re
    token = re.search(rb'name="cofre-token" content="([^"]+)"', html).group(1).decode()
    headers = {'Authorization': 'Bearer ' + token, 'Origin': f'http://127.0.0.1:{self.servidor.server_port}',
               'Content-Type': 'application/json'}
    self.assertEqual(self.pedido('/api/exportar', headers=headers, corpo=b'{"caminho":"qualquer"}')[0], 400)
    self.servidor.desktop.exportar.assert_not_called()
    self.assertEqual(self.pedido('/api/exportar', headers=headers | {'Origin': 'null'})[0], 403)
    self.servidor.desktop.exportar.assert_not_called()
    self.servidor.desktop.exportar.return_value = False
    codigo, corpo = self.pedido('/api/exportar', headers=headers)
    self.assertEqual((codigo, json.loads(corpo)), (200, {'salvo': False}))


class TestCicloJanela(unittest.TestCase):
  def test_pasta_nativa_persiste_e_bloqueia_inicio_durante_dialogo(self):
    estado = EstadoInterface(lambda p, e: None)
    desktop = desktop_cofre.Janela(Mock(estado=estado))
    desktop.janela = Mock()
    with tempfile.TemporaryDirectory() as temporario, patch.dict(os.environ, {'NUNES_COFRE_DADOS': temporario + '/perfil'}):
      destino = Path(temporario) / 'DOCUMENTOS DE ENTRADA'
      destino.mkdir()
      def escolher(*args, **kwargs):
        self.assertTrue(estado.snapshot()['configurando'])
        with self.assertRaisesRegex(ValueError, 'escolha da pasta'):
          estado.iniciar(entrada())
        with self.assertRaises(ValueError):
          desktop.escolher_pasta()
        return (str(destino),)
      desktop.janela.create_file_dialog.side_effect = escolher
      self.assertEqual(desktop.escolher_pasta(), {'alterado': True, 'pasta': str(destino.resolve())})
      self.assertFalse(estado.configurando)
      self.assertIsNone(estado.worker)
      self.assertEqual(desktop_cofre.documentos_entrada(), str(destino.resolve()))
      import webview
      self.assertEqual(desktop.janela.create_file_dialog.call_args.args, (webview.FileDialog.FOLDER,))
      desktop.janela.create_file_dialog.side_effect = None
      desktop.janela.create_file_dialog.return_value = None
      self.assertEqual(desktop.escolher_pasta(), {'alterado': False})
      self.assertEqual(desktop_cofre.documentos_entrada(), str(destino.resolve()))
      estado.dados['ativo'] = True
      desktop.janela.create_file_dialog.reset_mock()
      with self.assertRaises(ValueError):
        desktop.escolher_pasta()
      desktop.janela.create_file_dialog.assert_not_called()

  def test_falha_ou_encerramento_no_dialogo_nao_troca_pasta(self):
    estado = EstadoInterface()
    desktop = desktop_cofre.Janela(Mock(estado=estado))
    desktop.janela = Mock()
    with tempfile.TemporaryDirectory() as temporario, patch.dict(os.environ, {'NUNES_COFRE_DADOS': temporario + '/perfil'}):
      desktop.janela.create_file_dialog.return_value = (temporario,)
      with patch('desktop_cofre.salvar_documentos_entrada', side_effect=OSError('SINTÉTICO')):
        with self.assertRaises(OSError):
          desktop.escolher_pasta()
      self.assertFalse(estado.configurando)
      def fechar(*a, **kw):
        estado.encerrar()
        return (temporario,)
      desktop.janela.create_file_dialog.side_effect = fechar
      with self.assertRaisesRegex(ValueError, 'encerrando'):
        desktop.escolher_pasta()
      self.assertFalse(estado.configurando)
      self.assertFalse((Path(temporario) / 'perfil/desktop-configuracao.json').exists())

  def test_exporta_snapshot_por_dialogo_sem_caminho_da_pagina(self):
    estado = EstadoInterface()
    estado.dados['resultados'] = [{'nota': '123', 'situacao': 'Erro', 'detalhe': 'SINTÉTICO'}]
    desktop = desktop_cofre.Janela(Mock(estado=estado))
    desktop.janela = Mock()
    with tempfile.TemporaryDirectory() as temporario:
      destino = Path(temporario) / 'resultado.json'
      desktop.janela.create_file_dialog.return_value = (str(destino),)
      self.assertTrue(desktop.exportar())
      dados = json.loads(destino.read_text(encoding='utf-8'))
      self.assertEqual(dados['resultados'], estado.snapshot()['resultados'])
      self.assertIn('exportado_em', dados)
      desktop.janela.create_file_dialog.return_value = None
      self.assertFalse(desktop.exportar())
      estado.dados['ativo'] = True
      with self.assertRaises(ValueError):
        desktop.exportar()
      estado.dados['ativo'] = False
      desktop.exportando.acquire()
      try:
        with self.assertRaises(ValueError):
          desktop.exportar()
      finally:
        desktop.exportando.release()

  def test_x_confirma_uma_vez_e_aguarda_fronteira_segura(self):
    liberar = Event()
    estado = EstadoInterface(lambda p, e: liberar.wait(3))
    estado.iniciar(entrada())
    janela = Mock()
    servidor = Mock(estado=estado)
    desktop = desktop_cofre.Janela(servidor)
    try:
      janela.create_confirmation_dialog.return_value = False
      self.assertFalse(desktop.fechar(janela))
      self.assertFalse(estado.encerrando)
      janela.create_confirmation_dialog.return_value = True
      self.assertFalse(desktop.fechar(janela))
      self.assertTrue(estado.encerrando)
      self.assertTrue(estado.worker.is_alive())
      self.assertFalse(desktop.fechar(janela))
      self.assertEqual(janela.create_confirmation_dialog.call_count, 2)
    finally:
      liberar.set()
      estado.worker.join(3)
    self.assertFalse(estado.snapshot()['ativo'])
    desktop.liberar = True
    with patch('desktop_windows.salvar_geometria'):
      self.assertTrue(desktop.fechar(janela))

  def test_x_ocioso_solicita_parada_sem_dialogo(self):
    estado = EstadoInterface()
    janela = Mock()
    desktop = desktop_cofre.Janela(Mock(estado=estado))
    self.assertFalse(desktop.fechar(janela))
    self.assertTrue(estado.encerrando)
    janela.create_confirmation_dialog.assert_not_called()

  def test_parada_antes_da_carga(self):
    estado = EstadoInterface()
    desktop = desktop_cofre.Janela(Mock(estado=estado))
    estado.encerrar()
    self.assertFalse(desktop.aguardar(Event(), limite=.1))


class TestPersistencia(unittest.TestCase):
  def test_pasta_da_interface_reabre_sem_alterar_configuracao_do_console(self):
    from src.caminhos import documentos_entrada, salvar_documentos_entrada
    from src.config import Config
    with tempfile.TemporaryDirectory() as temporario, patch.dict(os.environ, {
        'NUNES_COFRE_DADOS': temporario + '/perfil', 'CAMINHO_DOCUMENTO_ENTRADA': temporario + '/legada',
        'SENHA_COFRE': 'SINTETICA', 'CNPJ_MATRIZ': 'SINTETICO', 'CNPJ_FILIAL': 'SINTETICO'}):
      self.assertEqual(documentos_entrada(), temporario + '/legada')
      destino = Path(temporario) / 'DOCUMENTOS DE ENTRADA'
      destino.mkdir()
      salvar_documentos_entrada(str(destino))
      self.assertEqual(documentos_entrada(), str(destino.resolve()))
      self.assertEqual(Config().caminho_documento_entrada, temporario + '/legada')
      os.environ.pop('CAMINHO_DOCUMENTO_ENTRADA')
      self.assertEqual(Config(caminho_documento_entrada=documentos_entrada()).caminho_documento_entrada, str(destino.resolve()))
      with self.assertRaises(ValueError):
        salvar_documentos_entrada('relativa')
      with self.assertRaises(ValueError):
        salvar_documentos_entrada(str(Path(temporario) / 'inexistente'))
      self.assertEqual(documentos_entrada(), str(destino.resolve()))
      (Path(temporario) / 'perfil/desktop-configuracao.json').write_text('[]', encoding='utf-8')
      with self.assertRaisesRegex(ValueError, 'Escolha novamente'):
        documentos_entrada()
      salvar_documentos_entrada(str(destino))
      self.assertEqual(documentos_entrada(), str(destino.resolve()))
      with patch.dict(os.environ, {'NUNES_COFRE_DADOS': temporario + '/outro-perfil'}):
        self.assertEqual(documentos_entrada(), '')

  def test_vinculo_empacotado_persistente_respeita_override_e_fonte(self):
    from src.caminhos import vinculo_central
    with tempfile.TemporaryDirectory() as temporario, patch.dict(os.environ, {'NUNES_COFRE_DADOS': temporario}):
      with patch.dict(os.environ):
        os.environ.pop('NUNES_CENTRAL_CONFIG', None)
        caminho = Path(temporario) / 'central.json'
        with patch('sys.frozen', True, create=True):
          self.assertIsNone(vinculo_central())
          caminho.write_text('{}', encoding='utf-8')
          self.assertEqual(vinculo_central(), caminho)
          with patch.dict(os.environ, {'NUNES_CENTRAL_CONFIG': temporario + '/explicita.json'}):
            self.assertIsNone(vinculo_central())
        self.assertIsNone(vinculo_central())

  def test_pacote_usa_perfil_e_override_nunca_meipass(self):
    with tempfile.TemporaryDirectory() as temporario, patch.dict(os.environ, {'LOCALAPPDATA': temporario}):
      with patch.dict(os.environ, clear=False):
        os.environ.pop('NUNES_COFRE_DADOS', None)
        with patch('sys.frozen', True, create=True), patch('sys._MEIPASS', temporario + '/extracao', create=True):
          self.assertEqual(pasta_dados(), Path(temporario) / 'Nunes/Cofre')
          self.assertEqual(pasta_preferencias(), pasta_dados())
      with patch.dict(os.environ, {'NUNES_COFRE_DADOS': temporario + '/isolado'}):
        self.assertEqual(pasta_dados(), Path(temporario) / 'isolado')

  def test_catalogo_cria_pasta_persistente_e_reabre(self):
    from src.emitente_handler import EmitenteHandler
    with tempfile.TemporaryDirectory() as temporario, patch.dict(os.environ, {'NUNES_COFRE_DADOS': temporario + '/dados'}):
      handler = EmitenteHandler()
      handler.get_nome('SINTETICO', lambda _: 'EXEMPLO')
      handler.close()
      self.assertEqual(EmitenteHandler().get_nome('SINTETICO'), 'EXEMPLO')
