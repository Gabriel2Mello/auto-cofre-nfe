"""Diagnóstico de início com dados sintéticos e destino isolado."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.diagnostico_interface import registrar_inicio


class TestDiagnosticoInterface(unittest.TestCase):
  def test_grava_tipo_http_e_contexto_sem_texto_livre(self):
    with tempfile.TemporaryDirectory() as pasta, \
         patch('src.diagnostico_abertura.pasta_preferencias', return_value=Path(pasta)), \
         patch('sys.frozen', False, create=True):
      caminho = registrar_inicio({'tipo': 'TypeError', 'status': 403})
      self.assertEqual(caminho, Path(pasta) / 'logs/cofre-diagnostico.txt')
      dados = json.loads(caminho.read_text(encoding='utf-8'))
      self.assertEqual(dados['etapa'], 'inicio_TypeError_http_403')
      self.assertEqual(dados['causas'][0]['tipo'], 'TypeError')
      for chave in ('instante', 'aplicacao', 'python', 'bits', 'recursos'):
        self.assertIn(chave, dados)
      self.assertEqual(registrar_inicio({'tipo': 'Error', 'status': None}), caminho)
      self.assertEqual(json.loads(caminho.read_text(encoding='utf-8'))['etapa'], 'inicio_Error_sem_resposta')

  def test_rejeita_campos_livres_tipos_e_codigos_invalidos(self):
    for dados in ({'tipo': 'SEGREDO', 'status': None}, {'tipo': [], 'status': None},
                  {'tipo': 'Error', 'status': True}, {'tipo': 'Error', 'status': 600},
                  {'tipo': 'Error', 'status': '403'}, {'tipo': 'Error'},
                  {'tipo': 'Error', 'status': 403, 'mensagem': 'SEGREDO'}):
      with self.subTest(dados=dados), patch('src.diagnostico_interface.registrar') as gravar:
        with self.assertRaises(ValueError):
          registrar_inicio(dados)
        gravar.assert_not_called()

  def test_falha_de_gravacao_nao_inventa_caminho(self):
    with patch('src.diagnostico_interface.registrar', return_value=None):
      with self.assertRaises(OSError):
        registrar_inicio({'tipo': 'TimeoutError', 'status': None})
