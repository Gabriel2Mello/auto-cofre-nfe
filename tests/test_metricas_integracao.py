from contextlib import ExitStack
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import main
from metricas_nunes import consultar_metricas
from src.controlador_web import EstadoInterface, Pedido, executar_lote
from src.enums import Empresa, TipoDocumento


class TestMetricasIntegracao(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch('sincronizar_estatisticas.ler_configuracao', return_value=None))
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        ambiente = patch.dict(os.environ, {'NUNES_METRICAS_DADOS': self.temp.name})
        ambiente.start(); self.addCleanup(ambiente.stop)

    def total(self):
        return consultar_metricas({'inicio': '2026-01-01', 'fim': '2099-12-31'})['totais']['documento_baixado']

    def simular(self, prefixo, pilha, falha_salvar=None, falha_flag=None):
        config = Mock(caminho_documento_entrada=self.temp.name, cnpj={Empresa.MATRIZ: '00000000000000'})
        pilha.enter_context(patch(prefixo + '.Config', return_value=config))
        for nome in ('TimeoutScraper', 'login', 'extrair_empresas_href', 'trocar_empresa', 'ver_arquivos', 'EmitenteHandler'):
            pilha.enter_context(patch(prefixo + '.' + nome))
        pilha.enter_context(patch(prefixo + '.processar_nota', return_value={
            'emitente': 'SINTETICO', 'empresa_id': '1', 'chave': 'sintetica', 'codigo_arquivo': '1'}))
        pilha.enter_context(patch(prefixo + '.baixar_arquivos', return_value=(b'<xml/>', b'%PDF')))
        pilha.enter_context(patch(prefixo + '.salvar_arquivos', side_effect=falha_salvar))
        pilha.enter_context(patch(prefixo + '.marcar_flag', side_effect=falha_flag))

    def test_falha_ao_salvar_nao_conta_e_falha_de_sinalizacao_nao_desfaz_baixa(self):
        pedido = Pedido.de_json({'notas': '123', 'empresa': 'MATRIZ', 'tipo': 'nfe',
                                  'competencia': '2026-10', 'pasta': '2026-10'})
        for falha_salvar, falha_flag, esperado in [(OSError('sintetico'), None, 0), (None, RuntimeError('sintetico'), 1), (None, None, 1)]:
            with self.subTest(esperado=esperado), ExitStack() as pilha:
                self.simular('src.controlador_web', pilha, falha_salvar, falha_flag)
                estado = EstadoInterface()
                estado.dados['resultados'] = [{'nota': '123', 'situacao': 'Aguardando', 'detalhe': ''}]
                executar_lote(pedido, estado)
                self.assertEqual(self.total(), esperado)

    def test_console_conta_xml_pdf_como_um_documento(self):
        with ExitStack() as pilha:
            self.simular('main', pilha)
            pilha.enter_context(patch('main.set_app_id'))
            pilha.enter_context(patch('main.sleep'))
            pilha.enter_context(patch('main.pause'))
            pilha.enter_context(patch('main.input_dados', return_value=(['123'], Empresa.MATRIZ, 10, 10, 2026, 2026, TipoDocumento.NFE)))
            main.main()
            main.main()
        self.assertEqual(self.total(), 1)
