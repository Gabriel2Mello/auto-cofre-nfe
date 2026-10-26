from contextlib import ExitStack
import json
import os
from pathlib import Path
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
                self.simular('src.execucao_web', pilha, falha_salvar, falha_flag)
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

    def test_console_retorna_falha_inclusive_quando_arquivos_foram_salvos(self):
        for falha_salvar, falha_flag in ((OSError('disco sintético'), None),
                                       (None, RuntimeError('sinalização sintética'))):
            with self.subTest(falha_salvar=falha_salvar), ExitStack() as pilha:
                self.simular('main', pilha, falha_salvar, falha_flag)
                for nome in ('set_app_id', 'sleep', 'pause', 'handle_error'):
                    pilha.enter_context(patch('main.' + nome))
                pilha.enter_context(patch('main.input_dados', return_value=(['123', '456'], Empresa.MATRIZ, 10, 10, 2026, 2026, TipoDocumento.NFE)))
                self.assertEqual(main.main(), 1)

    def test_console_sem_falhas_retorna_zero(self):
        with ExitStack() as pilha:
            self.simular('main', pilha)
            for nome in ('set_app_id', 'sleep', 'pause'):
                pilha.enter_context(patch('main.' + nome))
            pilha.enter_context(patch('main.input_dados', return_value=(['123'], Empresa.MATRIZ, 10, 10, 2026, 2026, TipoDocumento.NFE)))
            self.assertEqual(main.main(), 0)

    def test_interrupcao_no_nome_nao_salva_conta_sinaliza_nem_avanca_lote(self):
        for interrupcao in (KeyboardInterrupt, EOFError):
            with self.subTest(interrupcao=interrupcao), ExitStack() as pilha:
                self.simular('main', pilha)
                for nome in ('set_app_id', 'sleep', 'pause', 'handle_error'):
                    pilha.enter_context(patch('main.' + nome))
                pilha.enter_context(patch('main.input_dados', return_value=(
                    ['123', '124'], Empresa.MATRIZ, 10, 10, 2026, 2026, TipoDocumento.NFE)))
                main.EmitenteHandler.return_value.get_nome.side_effect = interrupcao
                with self.assertRaises(interrupcao):
                    main.main()
                main.processar_nota.assert_called_once()
                main.salvar_arquivos.assert_not_called()
                main.marcar_flag.assert_not_called()
                main.EmitenteHandler.return_value.close.assert_called_once()
                self.assertEqual(self.total(), 0)

    def test_interrupcao_preserva_nomes_ja_aprovados_e_documento_anterior(self):
        from src.emitente_handler import EmitenteHandler
        catalogo = Path(self.temp.name) / 'emitentes.json'
        with ExitStack() as pilha:
            self.simular('main', pilha)
            pilha.enter_context(patch('src.emitente_handler.obter_caminho_json', return_value=catalogo))
            main.EmitenteHandler.return_value = EmitenteHandler()
            main.processar_nota.side_effect = [
                {'emitente': emitente, 'empresa_id': '1', 'chave': emitente, 'codigo_arquivo': '1'}
                for emitente in ('PRIMEIRO', 'SEGUNDO')]
            for nome in ('set_app_id', 'sleep', 'pause', 'handle_error'):
                pilha.enter_context(patch('main.' + nome))
            pilha.enter_context(patch('main.input_dados', return_value=(
                ['123', '124'], Empresa.MATRIZ, 10, 10, 2026, 2026, TipoDocumento.NFE)))
            pilha.enter_context(patch('builtins.input', side_effect=['NOME APROVADO', KeyboardInterrupt]))
            with self.assertRaises(KeyboardInterrupt):
                main.main()
            main.salvar_arquivos.assert_called_once()
            main.marcar_flag.assert_called_once()
        self.assertEqual(json.loads(catalogo.read_text(encoding='utf-8')), {'PRIMEIRO': 'NOME APROVADO'})
        self.assertEqual(self.total(), 1)
