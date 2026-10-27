"""Diagnóstico com HTTP falso e disco temporário; nenhuma credencial real."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import tempfile
from threading import Event
import unittest
from unittest.mock import Mock, patch

from requests import HTTPError, Response, Timeout

from src import diagnostico_portal as diagnostico
from src.auth import login
from src.config import Config
from src.core import trocar_empresa
from src.enums import Empresa, TipoDocumento
from src.parsers import confirmar_empresa_ativa


CNPJ = '00000000000100'
SEGREDO = 'SEGREDO_QUE_NAO_PODE_SER_GRAVADO'
HTML = '<div id="mws-header-container"><span>FICTICIA (00.000.000/0001-00)</span></div>'
LINKS = {'00.000.000/0001-00': '/login/trocarLogin?vid=' + SEGREDO}


def resposta(html=HTML, status=200):
  r = Response()
  r.status_code = status
  r.url = Config.URL_BASE + '/nfe/empresa?token=' + SEGREDO
  r.encoding = 'utf-8'
  r._content = (html + '<!-- ' + SEGREDO + ' -->').encode('utf-8')
  r.headers.update({'Content-Type': 'text/html; charset=utf-8', 'Set-Cookie': SEGREDO})
  return r


class TestDiagnosticoPortal(unittest.TestCase):
  def setUp(self):
    pasta = tempfile.TemporaryDirectory()
    self.addCleanup(pasta.cleanup)
    self.raiz = Path(pasta.name)
    self.enterContext(patch.dict(os.environ, {'NUNES_COFRE_DADOS': pasta.name}))

  def registros(self):
    return [json.loads(linha) for linha in diagnostico.caminho_log().read_text(encoding='utf-8').splitlines()]

  def assertSemSegredos(self):
    for arquivo in (self.raiz / 'logs').glob('*'):
      texto = arquivo.read_text(encoding='utf-8')
      for segredo in (SEGREDO, CNPJ, '00.000.000/0001-00', 'FICTICIA', 'https://', 'trocarLogin', 'Set-Cookie'):
        self.assertNotIn(segredo, texto)

  def test_correlaciona_primeira_execucao_e_falha_na_segunda_sem_requisicoes_extras(self):
    sessoes = []
    for html in (HTML, '<form><input type="password"></form>'):
      sessao = Mock(post=Mock(return_value=resposta()), get=Mock(return_value=resposta(html)))
      sessoes.append(sessao)
      try:
        with diagnostico.diagnostico_execucao(Empresa.FILIAL):
          login(sessao, SEGREDO, CNPJ)
          trocar_empresa(sessao, Empresa.FILIAL, LINKS, CNPJ)
      except ValueError:
        pass
    registros = self.registros()
    inicios = [r for r in registros if r['evento'] == 'acesso_iniciado']
    fins = [r for r in registros if r['evento'] == 'acesso_encerrado']
    self.assertEqual(len(inicios), 2)
    self.assertNotEqual(inicios[0]['execucao'], inicios[1]['execucao'])
    self.assertEqual([r['resultado'] for r in fins], ['confirmado', 'falha'])
    self.assertEqual([r['execucao'] for r in fins], [r['execucao'] for r in inicios])
    confirmacoes = [r for r in registros if r['evento'] == 'confirmacao_empresa']
    self.assertEqual([r['motivo'] for r in confirmacoes], ['confirmado', 'cabecalho_ausente'])
    self.assertEqual(confirmacoes[-1]['spans_diretos'], 0)
    self.assertTrue([r for r in registros if r['evento'] == 'resposta_portal'][-1]['formulario_login'])
    self.assertTrue(all(r['empresa'] == 'FILIAL' for r in registros))
    self.assertTrue(all(r['duracao_ms'] >= 0 for r in registros if 'duracao_ms' in r))
    for sessao in sessoes:
      sessao.post.assert_called_once()
      sessao.get.assert_called_once()
    self.assertSemSegredos()

  def test_distingue_todas_as_causas_sem_alterar_a_recusa(self):
    casos = [
      ('', CNPJ, 'cabecalho_ausente'),
      (HTML + HTML, CNPJ, 'cabecalho_ambiguo'),
      (HTML.replace('0001-00', '0002-00'), CNPJ, 'cnpj_divergente'),
      (HTML.replace('00.000.000/0001-00', ''), CNPJ, 'cnpj_ausente'),
      (HTML.replace('FICTICIA', 'FICTICIA (00.000.000/0002-00)'), CNPJ, 'cnpj_ambiguo'),
      (HTML, 'invalido', 'configuracao_invalida'),
    ]
    for html, cnpj, motivo in casos:
      with self.subTest(motivo=motivo):
        with self.assertRaises(ValueError), diagnostico.diagnostico_execucao(Empresa.MATRIZ):
          confirmar_empresa_ativa(html, cnpj)
        validacao = [r for r in self.registros() if r['evento'] == 'confirmacao_empresa'][-1]
        self.assertEqual(validacao['motivo'], motivo)
    self.assertSemSegredos()

  def test_status_redirecionamentos_e_sinais_sao_categorizados_sem_url_ou_corpo(self):
    r = resposta('<input type = "password"><div class="cf-chl-desafio"></div>', 503)
    r.url = Config.URL_BASE + '/login/enviar?senha=' + SEGREDO
    anterior = resposta(status=307)
    anterior.url = Config.URL_BASE + '/login/trocarLogin?vid=' + SEGREDO
    r.history = [anterior]
    r.headers['Content-Type'] = 'application/' + SEGREDO
    sessao = Mock(post=Mock(return_value=r))
    with self.assertRaises(HTTPError), diagnostico.diagnostico_execucao(Empresa.MATRIZ):
      login(sessao, SEGREDO, CNPJ)
    dados = [x for x in self.registros() if x['evento'] == 'resposta_portal'][0]
    self.assertEqual(dados['status'], 503)
    self.assertEqual(dados['pagina'], 'login')
    self.assertEqual(dados['redirecionamentos'], [{'status': 307, 'pagina': 'outra'}])
    self.assertEqual(dados['conteudo'], 'outro')
    self.assertTrue(dados['formulario_login'])
    self.assertTrue(dados['desafio_acesso'])
    self.assertEqual(dados['tamanho_bytes'], len(r.content))
    self.assertSemSegredos()

  def test_timeout_preserva_excecao_original_e_nao_registra_sua_mensagem(self):
    erro = Timeout(SEGREDO)
    with self.assertRaises(Timeout) as captura, diagnostico.diagnostico_execucao(Empresa.MATRIZ):
      login(Mock(post=Mock(side_effect=erro)), SEGREDO, CNPJ)
    self.assertIs(captura.exception, erro)
    self.assertEqual(self.registros()[-1]['erro'], 'timeout')
    self.assertSemSegredos()

  def test_recusa_anterior_ao_html_nao_inventa_contagens_ou_validade(self):
    sessao = Mock()
    with self.assertRaises(ValueError), diagnostico.diagnostico_execucao(Empresa.MATRIZ):
      trocar_empresa(sessao, Empresa.MATRIZ, {}, CNPJ)
    dados = [r for r in self.registros() if r['evento'] == 'confirmacao_empresa'][0]
    self.assertEqual(dados['motivo'], 'vinculo_ausente')
    for campo in ('cabecalhos', 'spans_diretos', 'cnpjs_encontrados', 'configuracao_valida'):
      self.assertIsNone(dados[campo])
    sessao.get.assert_not_called()

  def test_falha_no_disco_nao_impede_sucesso_nem_substitui_erro_original(self):
    with patch.object(diagnostico, 'RotatingFileHandler', side_effect=OSError(SEGREDO)):
      with diagnostico.diagnostico_execucao(Empresa.MATRIZ):
        login(Mock(post=Mock(return_value=resposta())), SEGREDO, CNPJ)
        confirmar_empresa_ativa(HTML, CNPJ)
      erro = Timeout(SEGREDO)
      with self.assertRaises(Timeout) as captura, diagnostico.diagnostico_execucao(Empresa.MATRIZ):
        login(Mock(post=Mock(side_effect=erro)), SEGREDO, CNPJ)
      self.assertIs(captura.exception, erro)
    self.assertFalse(diagnostico.caminho_log().exists())

  def test_rotacao_limita_arquivos_e_mantem_json_valido(self):
    with patch.object(diagnostico, 'LIMITE_BYTES', 700), patch.object(diagnostico, 'COPIAS', 2):
      for _ in range(12):
        with diagnostico.diagnostico_execucao(Empresa.MATRIZ):
          confirmar_empresa_ativa(HTML, CNPJ)
    arquivos = list((self.raiz / 'logs').iterdir())
    self.assertEqual(len(arquivos), 3)
    for arquivo in arquivos:
      self.assertLessEqual(arquivo.stat().st_size, 700)
      for linha in arquivo.read_text(encoding='utf-8').splitlines():
        json.loads(linha)
    self.assertSemSegredos()

  def test_falha_de_escrita_ou_rotacao_fecha_arquivo_e_preserva_operacao(self):
    for falha in ('escrita', 'rotacao'):
      with self.subTest(falha=falha):
        handler = Mock()
        handler.shouldRollover.return_value = falha == 'rotacao'
        if falha == 'rotacao':
          handler.doRollover.side_effect = OSError(SEGREDO)
        else:
          handler.stream.write.side_effect = OSError(SEGREDO)
        with patch.object(diagnostico, 'RotatingFileHandler', return_value=handler):
          with diagnostico.diagnostico_execucao(Empresa.MATRIZ):
            confirmar_empresa_ativa(HTML, CNPJ)
        self.assertEqual(handler.close.call_count, 3)

  def test_nao_grava_fora_do_contexto_e_nao_herda_execucao_encerrada(self):
    confirmar_empresa_ativa(HTML, CNPJ)
    self.assertFalse(diagnostico.caminho_log().exists())
    with diagnostico.diagnostico_execucao(Empresa.MATRIZ):
      confirmar_empresa_ativa(HTML, CNPJ)
    antes = diagnostico.caminho_log().read_bytes()
    confirmar_empresa_ativa(HTML, CNPJ)
    self.assertEqual(diagnostico.caminho_log().read_bytes(), antes)

  def test_fluxos_web_e_console_geram_diagnostico_sem_acessar_o_portal(self):
    import main
    from src.controlador_web import EstadoInterface, Pedido
    from src.execucao_web import executar_lote
    for modo in ('web', 'console'):
      with self.subTest(modo=modo), ExitStack() as pilha:
        prefixo = 'src.execucao_web' if modo == 'web' else 'main'
        config = Mock(caminho_documento_entrada=str(self.raiz), cnpj={Empresa.MATRIZ: CNPJ})
        pilha.enter_context(patch(prefixo + '.Config', return_value=config))
        pilha.enter_context(patch(prefixo + '.EmitenteHandler'))
        pilha.enter_context(patch(prefixo + '.login', return_value=''))
        pilha.enter_context(patch(prefixo + '.extrair_empresas_href', return_value=LINKS))
        cliente = pilha.enter_context(patch(prefixo + '.TimeoutScraper'))
        cliente.return_value.__enter__.return_value.get.return_value = resposta('')
        if modo == 'web':
          pedido = Pedido.de_json({'notas': '123', 'empresa': 'MATRIZ', 'tipo': 'nfe',
                                   'competencia': '2026-10', 'pasta': '2026-10'})
          with self.assertRaises(ValueError):
            executar_lote(pedido, EstadoInterface())
        else:
          pilha.enter_context(patch('main.set_app_id'))
          pilha.enter_context(patch('main.input_dados', return_value=(
            ['123'], Empresa.MATRIZ, 10, 10, 2026, 2026, TipoDocumento.NFE)))
          with self.assertRaises(ValueError):
            main.executar()
    fins = [r for r in self.registros() if r['evento'] == 'acesso_encerrado']
    self.assertEqual(len(fins), 2)
    self.assertTrue(all(r['resultado'] == 'falha' for r in fins))

  def test_parada_correlaciona_lote_e_distingue_decisao_e_encerramento(self):
    from src.controlador_web import EstadoInterface
    for origem in ('parar', 'decisao', 'encerramento'):
      with self.subTest(origem=origem):
        pronto = Event()
        def executar(pedido, estado):
          with diagnostico.diagnostico_execucao(pedido.empresa, estado.id_execucao):
            confirmar_empresa_ativa(HTML, CNPJ)
          pronto.set()
          if origem == 'decisao':
            estado.solicitar_nome('EMITENTE PRIVADO')
          else:
            estado.parada.wait(3)
            estado.verificar_parada()
        estado = EstadoInterface(executar)
        estado.iniciar({'notas': '72412,3471,\n5036', 'empresa': 'MATRIZ', 'tipo': 'nfe',
                        'competencia': '2026-10', 'pasta': '2026-10'})
        try:
          self.assertTrue(pronto.wait(3))
          if origem == 'decisao':
            with estado.condicao:
              self.assertTrue(estado.condicao.wait_for(lambda: estado.dados['pergunta'] is not None, 3))
          if origem == 'encerramento':
            estado.encerrar()
          else:
            estado.parar(origem=origem)
          estado.parar(origem=origem)
          estado.worker.join(3)
          self.assertFalse(estado.worker.is_alive())
          self.assertTrue(estado.parada.is_set())
          registros = [r for r in self.registros() if r['execucao'] == estado.id_execucao]
          paradas = [r for r in registros if r['evento'] == 'parada_solicitada']
          self.assertEqual(len(paradas), 1)
          self.assertEqual(paradas[0]['origem'], origem)
          self.assertEqual(paradas[0]['pergunta'], 'nome' if origem == 'decisao' else None)
          self.assertEqual(paradas[0]['encerrando'], origem == 'encerramento')
          self.assertTrue(any(r['evento'] == 'acesso_iniciado' for r in registros))
        finally:
          estado.encerrar()
          estado.worker.join(3)
    texto = diagnostico.caminho_log().read_text(encoding='utf-8')
    self.assertNotIn('72412', texto)
    self.assertNotIn('EMITENTE PRIVADO', texto)

  def test_falha_no_log_nao_impede_parada(self):
    from src.controlador_web import EstadoInterface
    pronto = Event()
    def executar(pedido, estado):
      pronto.set()
      estado.parada.wait(3)
      estado.verificar_parada()
    estado = EstadoInterface(executar)
    estado.iniciar({'notas': '123', 'empresa': 'MATRIZ', 'tipo': 'nfe',
                    'competencia': '2026-10', 'pasta': '2026-10'})
    try:
      self.assertTrue(pronto.wait(3))
      with patch.object(diagnostico, 'RotatingFileHandler', side_effect=OSError(SEGREDO)):
        estado.parar()
      estado.worker.join(3)
      self.assertFalse(estado.worker.is_alive())
      self.assertTrue(estado.parada.is_set())
    finally:
      estado.encerrar()
      estado.worker.join(3)


if __name__ == '__main__':
  unittest.main()
