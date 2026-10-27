"""Falhas sintéticas, sem executar a interface nem operações fiscais."""
import json
from contextlib import nullcontext
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import cofre
from src import diagnostico_abertura as diagnostico


class TestDiagnosticoAbertura(unittest.TestCase):
  def test_preserva_causas_e_codigo_sem_mensagem_ou_ambiente(self):
    try:
      try:
        raise OSError(5, 'senha-secreta-sintetica')
      except OSError as causa:
        raise RuntimeError('token-secreto-sintetico') from causa
    except RuntimeError as erro:
      with patch.dict('os.environ', {'PYTHONNET_RUNTIME': 'valor-secreto'}):
        dados = diagnostico.detalhes(erro, 'janela_webview2')
    self.assertEqual([c['tipo'] for c in dados['causas']], ['RuntimeError', 'OSError'])
    self.assertEqual(dados['causas'][1]['errno'], 5)
    self.assertTrue(dados['causas'][1]['locais'])
    self.assertEqual(dados['pythonnet_runtime'], 'personalizado')
    texto = json.dumps(dados)
    for valor in ('senha-secreta', 'token-secreto', 'valor-secreto'):
      self.assertNotIn(valor, texto)

  def test_cadeia_circular_e_limitada(self):
    erro = RuntimeError()
    erro.__cause__ = erro
    self.assertEqual(len(diagnostico.detalhes(erro, 'teste')['causas']), 1)

  def test_pacote_grava_ao_lado_do_exe_e_recupera_falha_de_permissao(self):
    with tempfile.TemporaryDirectory() as pasta:
      raiz = Path(pasta)
      with patch('sys.frozen', True, create=True), patch('sys.executable', str(raiz / 'Cofre.exe')):
        caminho = diagnostico.registrar(RuntimeError('secreto'), 'janela_webview2')
      self.assertEqual(caminho, raiz / 'cofre-diagnostico.txt')
      self.assertEqual(json.loads(caminho.read_text())['etapa'], 'janela_webview2')
      with patch('sys.frozen', True, create=True), patch('sys.executable', str(raiz / 'programa/Cofre.exe')), \
           patch.object(diagnostico, 'pasta_preferencias', return_value=raiz / 'perfil'), \
           patch('diagnostico_nunes.gravar_registro', side_effect=[PermissionError(), None]) as gravar:
        self.assertEqual(diagnostico.registrar(RuntimeError(), 'teste'), raiz / 'perfil/logs/cofre-diagnostico.txt')
        self.assertEqual(gravar.call_count, 2)

  def test_falha_na_janela_informa_etapa_e_preserva_encerramento(self):
    publicacao = Mock(registro={})
    servidor = Mock()
    estado = Mock(worker=None)
    with patch('src.controlador_web.EstadoInterface', return_value=estado), \
         patch('src.interface_web.criar_servidor', return_value=servidor), \
         patch('desktop_windows.identidade_processo'), \
         patch('desktop_cofre.executar', side_effect=RuntimeError('sintetico')), \
         patch('cofre.informar_falha_abertura') as informar:
      self.assertEqual(cofre.executar_painel(publicacao, Mock(etapa=lambda _: nullcontext())), 1)
    self.assertEqual(informar.call_args.args[1], 'janela_webview2')
    estado.encerrar.assert_called_once()
    servidor.server_close.assert_called_once()
