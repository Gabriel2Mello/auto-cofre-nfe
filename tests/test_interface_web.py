import json
import tempfile
import socket
import unittest
from pathlib import Path
from http.client import HTTPConnection
from threading import Event, Thread
from time import monotonic
from unittest.mock import MagicMock, patch
from requests import HTTPError, Timeout

from src.controlador_web import (EstadoInterface, Pedido, executar_lote,
                                 PastaDestinoIndisponivel, EmitentesIndisponiveis)
from src.enums import Empresa, TipoDocumento
from src.interface_web import criar_servidor
from src.parsers import LinhaNFe, NotaNaoEncontrada, encontrar_linha


def entrada(**alteracoes):
  return {'notas': '00123,124', 'empresa': 'MATRIZ', 'tipo': 'nfe',
          'competencia': '2026-10', 'pasta': '2026-11', **alteracoes}


class TestPedido(unittest.TestCase):
  def test_preserva_zeros_remove_repeticoes_e_aceita_linhas(self):
    p = Pedido.de_json(entrada(notas='00123,123\n124;125'))
    self.assertEqual(p.notas, ['00123', '124', '125'])
    self.assertEqual((p.mes_nota, p.ano_nota, p.mes_pasta, p.ano_pasta), (10, 2026, 11, 2026))
    self.assertEqual((p.empresa, p.tipo), (Empresa.MATRIZ, TipoDocumento.NFE))

  def test_rejeita_entrada_invalida_antes_de_executar(self):
    for dados in [entrada(notas=''), entrada(notas='../123'), entrada(notas='123abc'), entrada(notas='12a34'), entrada(notas='0'),
                  entrada(notas='1234567890'), entrada(notas='１２３'), entrada(tipo='outro'),
                  entrada(empresa=''), entrada(competencia='2026-13'), entrada(pasta='0000-01'),
                  entrada(competencia=3), entrada(notas=None)]:
      with self.subTest(dados=dados), self.assertRaises(ValueError):
        Pedido.de_json(dados)


class TestDecisoes(unittest.TestCase):
  def test_resposta_explicita_e_rejeicao_de_resposta_antiga(self):
    disponivel = Event()
    nomes = []

    def executor(pedido, estado):
      # O teste observa a condição, sem depender de pausas e relógio real.
      disponivel.set()
      nomes.append(estado.solicitar_nome('FORNECEDOR TESTE'))

    estado = EstadoInterface(executor)
    estado.iniciar(entrada())
    self.assertTrue(disponivel.wait(2))
    with estado.condicao:
      self.assertTrue(estado.condicao.wait_for(lambda: estado.dados['pergunta'] is not None, 2))
      p = estado.snapshot()['pergunta']
    with self.assertRaises(ValueError):
      estado.responder({'id': 'antigo', 'valor': 'TESTE'})
    with self.assertRaises(ValueError):
      estado.responder({'id': p['id'], 'valor': '///'})
    estado.responder({'id': p['id'], 'valor': 'FORNECEDOR'})
    estado.worker.join(2)
    self.assertFalse(estado.worker.is_alive())
    self.assertEqual(nomes, ['FORNECEDOR'])
    with self.assertRaises(ValueError):
      estado.responder({'id': p['id'], 'valor': 'TESTE'})

  def test_fechar_acorda_decisao_e_impede_nova_execucao(self):
    estado = EstadoInterface(lambda pedido, e: e.solicitar_nome('TESTE'))
    estado.iniciar(entrada())
    with estado.condicao:
      self.assertTrue(estado.condicao.wait_for(lambda: estado.dados['pergunta'] is not None, 2))
    estado.encerrar()
    estado.worker.join(2)
    self.assertFalse(estado.worker.is_alive())
    self.assertFalse(estado.snapshot()['ativo'])
    self.assertIsNone(estado.snapshot()['pergunta'])
    self.assertTrue(all(r['situacao'] == 'Não processado' for r in estado.snapshot()['resultados']))
    with self.assertRaises(ValueError):
      estado.iniciar(entrada())

  def test_nao_inicia_dois_lotes(self):
    liberar = Event()
    estado = EstadoInterface(lambda p, e: liberar.wait(2))
    try:
      estado.iniciar(entrada())
      with self.assertRaises(ValueError):
        estado.iniciar(entrada())
    finally:
      liberar.set()
      estado.worker.join(2)


class TestFluxo(unittest.TestCase):
  def test_preparacao_identifica_destino_e_catalogo_sem_acessar_portal(self):
    with tempfile.TemporaryDirectory() as pasta:
      raiz = Path(pasta)
      config = MagicMock(caminho_documento_entrada=str(raiz / 'ausente'))
      with patch('src.execucao_web.Config', return_value=config), \
           patch('src.execucao_web.documentos_entrada', return_value=pasta), \
           patch('src.execucao_web.arquivo_emitentes', return_value=raiz / 'emitentes-ausente.csv'), \
           patch('src.execucao_web.arquivo_emitentes_padrao', return_value=raiz / 'padrao.csv'), \
           patch('src.execucao_web.login') as login:
        pedido = Pedido.de_json(entrada())
        with self.assertRaises(PastaDestinoIndisponivel):
          executar_lote(pedido, EstadoInterface())
        config.caminho_documento_entrada = pasta
        with self.assertRaises(EmitentesIndisponiveis):
          executar_lote(pedido, EstadoInterface())
        login.assert_not_called()

  def test_fluxo_completo_realiza_escolhas_no_painel(self):
    linhas = [LinhaNFe('', 'FORNECEDOR A', '01/10/2026', '123', '10,00'),
              LinhaNFe('', 'FORNECEDOR B', '02/10/2026', '123', '20,00')]
    config = MagicMock(senha_cofre='segredo-sintetico', cnpj={Empresa.MATRIZ: '00000000000000'})
    escolhas = []

    def consultar(*args):
      selecionado = args[-1](linhas)
      escolhas.append(selecionado)
      return {'emitente': 'FORNECEDOR B', 'empresa_id': '1', 'chave': 'teste', 'codigo_arquivo': '1'}

    with tempfile.TemporaryDirectory() as pasta:
      config.caminho_documento_entrada = pasta
      with patch('src.execucao_web.Config', return_value=config), \
           patch('src.execucao_web.TimeoutScraper'), patch('src.execucao_web.login', return_value=''), \
           patch('src.execucao_web.extrair_empresas_href', return_value={}), \
           patch('src.execucao_web.trocar_empresa'), patch('src.execucao_web.ver_arquivos'), \
           patch('src.execucao_web.processar_nota', side_effect=consultar), \
           patch('src.execucao_web.baixar_arquivos', return_value=(b'<xml/>', b'%PDF')), \
           patch('src.execucao_web.EmitenteHandler') as handler, \
           patch('src.execucao_web.salvar_arquivos') as salvar, \
           patch('src.execucao_web.marcar_flag') as flag:
        handler.return_value.get_nome.side_effect = lambda emitente, perguntar: perguntar(emitente)
        estado = EstadoInterface()
        estado.iniciar(entrada(notas='00123'))
        for tipo, resposta in [('emitente', '1'), ('nome', 'FORNECEDOR B')]:
          with estado.condicao:
            self.assertTrue(estado.condicao.wait_for(
              lambda: estado.dados['pergunta'] is not None and estado.dados['pergunta']['tipo'] == tipo, 3))
            pergunta = estado.snapshot()['pergunta']
          if tipo == 'emitente':
            self.assertEqual(pergunta['nota'], '00123', 'Preservar o número solicitado, inclusive zeros à esquerda.')
          estado.responder({'id': pergunta['id'], 'valor': resposta})
        estado.worker.join(3)
        self.assertFalse(estado.worker.is_alive())
        self.assertEqual(escolhas, [linhas[1]])
        self.assertEqual(estado.snapshot()['resultados'][0]['situacao'], 'Concluído')
        self.assertEqual(salvar.call_args.args[4:8], (Empresa.MATRIZ, 11, '2026', TipoDocumento.NFE))
        flag.assert_called_once()
        handler.return_value.close.assert_called_once()

  def executar_simulado(self, falha_salvar=None, falha_flag=None, parar_ao_salvar=False, falha_consulta=None, com_aviso=False):
    estado = EstadoInterface()
    pedido = Pedido.de_json(entrada(notas='123'))
    estado.dados['resultados'] = [{'nota': '123', 'situacao': 'Aguardando', 'detalhe': ''}]
    config = MagicMock(caminho_documento_entrada='.', cnpj={Empresa.MATRIZ: '00000000000000'})
    def salvar(*args, **kwargs):
      if falha_salvar:
        raise falha_salvar
      if parar_ao_salvar:
        estado.parada.set()
    with patch('src.execucao_web.Config', return_value=config), \
         patch('src.execucao_web.TimeoutScraper'), patch('src.execucao_web.login', return_value=''), \
         patch('src.execucao_web.extrair_empresas_href', return_value={}), \
         patch('src.execucao_web.trocar_empresa'), patch('src.execucao_web.ver_arquivos'), \
         patch('src.execucao_web.processar_nota', side_effect=falha_consulta, return_value={
           'emitente': 'TESTE', 'empresa_id': '1', 'chave': 'teste', 'codigo_arquivo': '1'}), \
         patch('src.execucao_web.baixar_arquivos', return_value=(b'<xml/>', b'%PDF')), \
         patch('src.execucao_web.EmitenteHandler'), \
         patch('src.execucao_web.salvar_arquivos', side_effect=salvar), \
         patch('src.execucao_web.marcar_flag', side_effect=falha_flag) as flag:
      executar_lote(pedido, estado)
    dados = estado.snapshot()
    retorno = (dados['resultados'][0], flag)
    return (*retorno, dados.get('aviso_portal')) if com_aviso else retorno

  def test_executor_publica_orientacao_sem_expor_excecao(self):
    for falha, tipo, salvo in (
      ({'falha_consulta': Timeout('SEGREDO')}, 'timeout', False),
      ({'falha_consulta': HTTPError('SEGREDO')}, 'comunicacao', False),
      ({'falha_salvar': PermissionError('SEGREDO')}, 'gravacao', False),
      ({'falha_flag': Timeout('SEGREDO')}, 'sinalizacao', True),
      ({'falha_flag': RuntimeError('SEGREDO')}, 'sinalizacao', True),
    ):
      with self.subTest(tipo=tipo, salvo=salvo):
        resultado, flag, aviso = self.executar_simulado(**falha, com_aviso=True)
        self.assertEqual(aviso['tipo'], tipo)
        self.assertNotIn('SEGREDO', json.dumps([resultado, aviso]))
        self.assertEqual(resultado['situacao'], 'Conferir sinalização' if salvo else 'Erro')
        if salvo:
          flag.assert_called_once()
          self.assertTrue(resultado['detalhe'].startswith('XML e PDF salvos;'))
        else:
          flag.assert_not_called()

  def test_nota_ausente_exibe_mensagem_curta_sem_sinalizar(self):
    for linhas in ([], [['', 'SINTETICO', '01/10/2026', '456', '10,00']]):
      with self.subTest(linhas=linhas):
        with self.assertRaises(NotaNaoEncontrada) as erro:
          encontrar_linha(linhas, '123', 10, 2026, TipoDocumento.NFE)
        resultado, flag = self.executar_simulado(falha_consulta=erro.exception)
        self.assertEqual(resultado, {'nota': '123', 'situacao': 'Erro', 'detalhe': 'Nenhuma nota encontrada'})
        flag.assert_not_called()

  def test_falha_ao_salvar_nao_sinaliza_portal(self):
    resultado, flag = self.executar_simulado(falha_salvar=OSError('teste'))
    self.assertEqual(resultado['situacao'], 'Erro')
    flag.assert_not_called()

  def test_falha_ao_sinalizar_distingue_arquivos_salvos(self):
    resultado, flag = self.executar_simulado(falha_flag=RuntimeError('teste'))
    self.assertEqual(resultado['situacao'], 'Conferir sinalização')
    self.assertIn('XML e PDF salvos', resultado['detalhe'])
    flag.assert_called_once()

  def test_falha_de_comunicacao_usa_mensagens_curtas_sem_perder_estado(self):
    resultado, flag = self.executar_simulado(falha_consulta=HTTPError('HTTP 503'))
    self.assertEqual(resultado['situacao'], 'Erro')
    self.assertEqual(resultado['detalhe'], 'Falha na comunicação com o Cofre.')
    flag.assert_not_called()
    resultado, flag = self.executar_simulado(falha_flag=HTTPError('HTTP 503'))
    self.assertEqual(resultado['situacao'], 'Conferir sinalização')
    self.assertEqual(resultado['detalhe'], 'XML e PDF salvos; não foi possível confirmar a sinalização no Cofre.')
    flag.assert_called_once()

  def test_gravacao_e_timeout_exibem_detalhes_objetivos(self):
    resultado, _ = self.executar_simulado(falha_salvar=OSError('teste'))
    self.assertEqual(resultado['detalhe'], 'Não foi possível gravar os arquivos do documento.')
    resultado, _ = self.executar_simulado(falha_consulta=Timeout('teste'))
    self.assertEqual(resultado['detalhe'], 'O Cofre não respondeu dentro do prazo.')

  def test_parada_apos_salvar_conclui_sinalizacao_sem_repetir(self):
    resultado, flag = self.executar_simulado(parar_ao_salvar=True)
    self.assertEqual(resultado['situacao'], 'Concluído')
    flag.assert_called_once()


class TestHTTP(unittest.TestCase):
  def setUp(self):
    self.estado = EstadoInterface(lambda p, e: None)
    self.servidor = criar_servidor(self.estado)
    self.thread = Thread(target=self.servidor.serve_forever, daemon=True)
    self.thread.start()
    self.origem = f'http://127.0.0.1:{self.servidor.server_port}'
    status, pagina = self.requisicao('GET', '/')
    self.assertEqual(status, 200)
    self.token = pagina.decode().split('name="cofre-token" content="')[1].split('"')[0]

  def tearDown(self):
    self.servidor.shutdown()
    self.servidor.server_close()
    self.thread.join(2)

  def requisicao(self, metodo, caminho, dados=None, headers=None):
    conexao = HTTPConnection('127.0.0.1', self.servidor.server_port, timeout=3)
    try:
      conexao.request(metodo, caminho, body=dados, headers=headers or {})
      resposta = conexao.getresponse()
      return resposta.status, resposta.read()
    finally:
      conexao.close()

  def cabecalhos(self):
    return {'Authorization': 'Bearer ' + self.token, 'Origin': self.origem, 'Content-Type': 'application/json'}

  def test_estado_exige_token_e_host_local(self):
    self.assertEqual(self.requisicao('GET', '/api/estado')[0], 403)
    self.assertEqual(self.requisicao('GET', '/api/estado', headers=self.cabecalhos())[0], 200)
    self.assertEqual(self.requisicao('GET', '/', headers={'Host': 'host-externo'})[0], 403)
    self.assertEqual(self.requisicao('GET', '/../README.md')[0], 404)

  def test_post_rejeita_origem_externa_e_json_invalido(self):
    headers = self.cabecalhos()
    headers['Origin'] = 'https://exemplo.invalid'
    self.assertEqual(self.requisicao('POST', '/api/iniciar', '{}', headers)[0], 403)
    for corpo in ['[]', '{', json.dumps(entrada(notas='../'))]:
      self.assertEqual(self.requisicao('POST', '/api/iniciar', corpo, self.cabecalhos())[0], 400)
    self.assertIsNone(self.estado.worker)

  def test_recursos_e_datas_estao_disponiveis(self):
    for caminho in ['/cofre.css', '/cofre.js', '/rolagem.js', '/nunes-tema.js', '/icons/icone.svg',
                    '/icons/tema-lua.svg', '/icons/tema-lua-sol.svg', '/favicon.ico']:
      self.assertEqual(self.requisicao('GET', caminho)[0], 200)
    _, pagina = self.requisicao('GET', '/')
    self.assertNotIn(b'__TOKEN__', pagina)
    self.assertNotIn(b'__MES__', pagina)

  def test_diagnostico_inicio_exige_autorizacao_e_dados_limitados(self):
    dados = json.dumps({'tipo': 'TypeError', 'status': None})
    with patch('src.diagnostico_interface.registrar_inicio', return_value='C:/teste/cofre-diagnostico.txt') as gravar:
      self.assertEqual(self.requisicao('POST', '/api/diagnostico-inicio', dados)[0], 403)
      externo = {**self.cabecalhos(), 'Origin': 'https://exemplo.invalid'}
      self.assertEqual(self.requisicao('POST', '/api/diagnostico-inicio', dados, externo)[0], 403)
      gravar.assert_not_called()
      status, corpo = self.requisicao('POST', '/api/diagnostico-inicio', dados, self.cabecalhos())
      self.assertEqual(status, 200)
      self.assertEqual(json.loads(corpo)['caminho'], 'C:/teste/cofre-diagnostico.txt')
      gravar.assert_called_once_with({'tipo': 'TypeError', 'status': None})
    invalido = json.dumps({'tipo': 'Error', 'status': 403, 'mensagem': 'PRIVADO'})
    self.assertEqual(self.requisicao('POST', '/api/diagnostico-inicio', invalido, self.cabecalhos())[0], 400)
    with patch('src.diagnostico_interface.registrar_inicio', side_effect=OSError('PRIVADO')):
      status, corpo = self.requisicao('POST', '/api/diagnostico-inicio', dados, self.cabecalhos())
      self.assertEqual(status, 500)
      self.assertNotIn(b'PRIVADO', corpo)
    self.assertIsNone(self.estado.worker)

  def test_fechar_solicita_parada_sem_matar_operacao(self):
    liberar = Event()
    self.estado.executor = lambda p, e: liberar.wait(2)
    self.estado.iniciar(entrada())
    try:
      self.assertEqual(self.requisicao('POST', '/api/fechar', '{}', self.cabecalhos())[0], 200)
      self.assertTrue(self.estado.encerrando)
      self.assertTrue(self.estado.snapshot()['ativo'])
      self.assertTrue(self.estado.parada.is_set())
    finally:
      liberar.set()
      self.estado.worker.join(2)

  def test_parada_identifica_origem_sem_aceitar_texto_livre(self):
    for dados, origem in (({}, 'parar'), ({'origem': 'decisao'}, 'decisao'),
                           ({'origem': 'CONTEUDO PRIVADO'}, 'parar')):
      with self.subTest(origem=origem), patch.object(self.estado, 'parar') as parar:
        self.assertEqual(self.requisicao('POST', '/api/parar', json.dumps(dados), self.cabecalhos())[0], 200)
        parar.assert_called_once_with(origem=origem)

  def test_ausencia_da_ultima_aba_encerra_programa(self):
    with self.estado.condicao:
      self.servidor.teve_pagina = True
      self.servidor.sem_paginas_desde = monotonic() - 5
    self.servidor.service_actions()
    self.assertTrue(self.estado.encerrando)

  def test_aba_conectada_preserva_programa_ocioso(self):
    with self.estado.condicao:
      self.servidor.teve_pagina = True
      self.servidor.sem_paginas_desde = monotonic() - 5
      self.servidor.paginas['teste'] = Event()
    self.servidor.service_actions()
    self.assertFalse(self.estado.encerrando)

  def test_desconectar_ultima_aba_remove_presenca(self):
    conexao = HTTPConnection('127.0.0.1', self.servidor.server_port, timeout=3)
    headers = {**self.cabecalhos(), 'X-Cofre-Pagina': 'pagina-teste'}
    try:
      conexao.request('GET', '/api/presenca', headers=headers)
      resposta = conexao.getresponse()
      self.assertEqual(resposta.status, 200)
      self.assertEqual(resposta.read(len(b': presenca\n\n')), b': presenca\n\n')
      self.assertIn('pagina-teste', self.servidor.paginas)
      resposta.fp.raw._sock.shutdown(socket.SHUT_RDWR)
      resposta.close()
      conexao.close()
      with self.estado.condicao:
        self.assertTrue(self.estado.condicao.wait_for(lambda: not self.servidor.paginas, 4))
        self.servidor.sem_paginas_desde = monotonic() - 5
      self.servidor.service_actions()
      self.assertTrue(self.estado.encerrando)
    finally:
      conexao.close()


if __name__ == '__main__':
  unittest.main()
