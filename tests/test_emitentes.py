"""Persistência do catálogo em diretório temporário, sem cadastros reais."""

import json
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from src.emitente_handler import EmitenteHandler


class TestCatalogoEmitentes(unittest.TestCase):
  def setUp(self):
    temporario = self.enterContext(TemporaryDirectory())
    self.raiz = Path(temporario)
    self.catalogo = self.raiz / 'emitentes_conhecidos.json'
    self.anterior = b'{ "ANTIGO": "NOME APROVADO" }\n'
    self.catalogo.write_bytes(self.anterior)
    self.enterContext(patch('src.emitente_handler.obter_caminho_json', return_value=self.catalogo))
    self.enterContext(patch('builtins.print'))

  def adicionar(self):
    handler = EmitenteHandler()
    self.assertEqual(handler.get_nome('NOVO', lambda _: 'Nome Novo'), 'NOME NOVO')
    return handler

  def test_interrupcao_na_pergunta_nao_cria_nome_nem_altera_catalogo(self):
    for interrupcao in (KeyboardInterrupt, EOFError):
      with self.subTest(interrupcao=interrupcao):
        handler = EmitenteHandler()
        with patch('builtins.input', side_effect=interrupcao), self.assertRaises(interrupcao):
          handler.get_nome('NOVO')
        handler.close()
        self.assertEqual(handler.emitentes_conhecidos, {'ANTIGO': 'NOME APROVADO'})
        self.assertEqual(self.catalogo.read_bytes(), self.anterior)

  def test_promocao_com_falha_preserva_original_e_temporario_recuperavel(self):
    handler = self.adicionar()
    falha = PermissionError('Falha sintética de promoção')
    with patch('os.rename', side_effect=falha), patch('os.replace', side_effect=falha):
      with self.assertRaises(RuntimeError) as captura:
        handler.close()
    self.assertIs(captura.exception.__cause__, falha)
    self.assertIn('catálogo de emitentes', str(captura.exception))
    self.assertIn('Temporário mantido', str(captura.exception))
    self.assertTrue(self.catalogo.exists(), 'O catálogo anterior deve continuar disponível')
    self.assertEqual(self.catalogo.read_bytes(), self.anterior)
    temporarios = list(self.raiz.glob('*.tmp'))
    self.assertEqual(len(temporarios), 1)
    self.assertEqual(json.loads(temporarios[0].read_text(encoding='utf-8')),
                     {'ANTIGO': 'NOME APROVADO', 'NOVO': 'NOME NOVO'})

  def test_pode_tentar_salvar_novamente_apos_falha(self):
    handler = self.adicionar()
    with patch('os.rename', side_effect=PermissionError('sintético')), \
         patch('os.replace', side_effect=PermissionError('sintético')):
      with self.assertRaises(RuntimeError):
        handler.close()
    self.assertTrue(self.catalogo.exists())
    self.assertEqual(self.catalogo.read_bytes(), self.anterior)
    handler.close()
    recarregado = EmitenteHandler()
    self.assertEqual(recarregado.get_nome('ANTIGO'), 'NOME APROVADO')
    self.assertEqual(recarregado.get_nome('NOVO'), 'NOME NOVO')

  def test_nao_sobrescreve_temporario_de_outra_tentativa(self):
    pendente = self.catalogo.with_suffix('.tmp')
    pendente.write_bytes(b'PENDENCIA ANTERIOR')
    self.adicionar().close()
    self.assertTrue(pendente.exists())
    self.assertEqual(pendente.read_bytes(), b'PENDENCIA ANTERIOR')

  def test_catalogo_invalido_nao_vira_base_vazia(self):
    invalidos = [b'{', b'\xff', b'[]', b'null', b'true', b'1', b'"texto"',
                 b'{"NOME": null}', b'{"NOME": 1}', b'{"": "NOME"}',
                 b'{"NOME": ""}', b'{"NOME": "   "}']
    for conteudo in invalidos:
      with self.subTest(conteudo=conteudo):
        self.catalogo.write_bytes(conteudo)
        with self.assertRaises(ValueError) as captura:
          EmitenteHandler()
        self.assertIn('catálogo', str(captura.exception).lower())
        self.assertEqual(self.catalogo.read_bytes(), conteudo)
        self.assertEqual(list(self.raiz.glob('*.tmp')), [])

  def test_sucesso_mantem_mapeamentos_e_nao_grava_ao_fechar_novamente(self):
    handler = self.adicionar()
    handler.close()
    self.assertEqual(json.loads(self.catalogo.read_text(encoding='utf-8')),
                     {'ANTIGO': 'NOME APROVADO', 'NOVO': 'NOME NOVO'})
    with patch('os.replace', side_effect=AssertionError('Não deve salvar novamente')):
      handler.close()
    self.assertEqual(list(self.raiz.glob('*.tmp')), [])

  def test_sem_alteracoes_preserva_bytes_e_nome_aprovado(self):
    perguntar = Mock()
    handler = EmitenteHandler()
    self.assertEqual(handler.get_nome(' antigo ', perguntar), 'NOME APROVADO')
    perguntar.assert_not_called()
    handler.close()
    self.assertEqual(self.catalogo.read_bytes(), self.anterior)
    self.assertEqual(list(self.raiz.glob('*.tmp')), [])

  def test_catalogo_ausente_pode_ser_criado_e_lido_em_utf8(self):
    self.catalogo.unlink()
    handler = EmitenteHandler()
    handler.get_nome('EMITENTE FICTÍCIO', lambda _: 'Nome Fictício')
    handler.close()
    self.assertEqual(json.loads(self.catalogo.read_text(encoding='utf-8')),
                     {'EMITENTE FICTÍCIO': 'NOME FICTICIO'})
    self.assertEqual(EmitenteHandler().get_nome('EMITENTE FICTÍCIO'), 'NOME FICTICIO')

  def test_erro_de_acesso_nao_vira_base_vazia(self):
    self.catalogo.unlink()
    self.catalogo.mkdir()
    with self.assertRaises(OSError):
      EmitenteHandler()


  def test_falha_ao_criar_temporario_preserva_catalogo(self):
    handler = self.adicionar()
    falha = PermissionError('Falha sintética ao criar temporário')
    with patch('src.emitente_handler.NamedTemporaryFile', side_effect=falha):
      with self.assertRaises(RuntimeError) as captura:
        handler.close()
    self.assertIs(captura.exception.__cause__, falha)
    self.assertEqual(self.catalogo.read_bytes(), self.anterior)
    self.assertEqual(list(self.raiz.glob('*.tmp')), [])

  def test_falha_de_escrita_preserva_original_e_identifica_temporario_incompleto(self):
    handler = self.adicionar()
    falha = OSError('Disco sintético cheio')

    def abrir_com_falha(**opcoes):
      arquivo = NamedTemporaryFile(**opcoes)
      escrever = arquivo.write

      def gravar_parcial(conteudo):
        escrever(conteudo[:5])
        raise falha

      self.enterContext(patch.object(arquivo, 'write', side_effect=gravar_parcial))
      return arquivo

    with patch('src.emitente_handler.NamedTemporaryFile', side_effect=abrir_com_falha):
      with self.assertRaises(RuntimeError) as captura:
        handler.close()
    self.assertIs(captura.exception.__cause__, falha)
    self.assertIn('pode estar incompleto', str(captura.exception))
    self.assertEqual(self.catalogo.read_bytes(), self.anterior)
    temporarios = list(self.raiz.glob('*.tmp'))
    self.assertEqual(len(temporarios), 1)
    self.assertEqual(len(temporarios[0].read_text(encoding='utf-8')), 5)

  def test_falha_ao_sincronizar_nao_promove_temporario(self):
    handler = self.adicionar()
    falha = OSError('Falha sintética na sincronização')
    with patch('src.emitente_handler.fsync', side_effect=falha):
      with self.assertRaises(RuntimeError) as captura:
        handler.close()
    self.assertIs(captura.exception.__cause__, falha)
    self.assertEqual(self.catalogo.read_bytes(), self.anterior)
    temporarios = list(self.raiz.glob('*.tmp'))
    self.assertEqual(len(temporarios), 1)
    self.assertEqual(json.loads(temporarios[0].read_text(encoding='utf-8')),
                     {'ANTIGO': 'NOME APROVADO', 'NOVO': 'NOME NOVO'})


if __name__ == '__main__':
  unittest.main()
