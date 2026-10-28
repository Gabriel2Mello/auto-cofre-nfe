"""Integração com central temporária, sem acesso ao portal ou documentos reais."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Event, Thread
import unittest
from unittest.mock import Mock, patch

import cofre
import main
import sincronizar_estatisticas as sync
from metricas_nunes import registrar_evento
from src.controlador_web import EstadoInterface
from src.enums import Empresa, TipoDocumento
import tests.test_metricas_integracao as cenarios

# Dependência exclusiva de teste. O cliente distribuído nunca importa a central.
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ.parent / 'nunes-estatisticas'))
from central import Armazem, Servidor


class TestEstatisticasCofre(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pasta = Path(self.temp.name)
        self.origem = self.pasta / 'metricas'
        self.armazem = Armazem(self.pasta / 'central.sqlite3', 'c' * 32)
        self.servidor = Servidor(self.armazem, 'token_sintetico_' * 3, 0)
        self.porta = self.servidor.server_port
        self.config = {'protocolo': 1, 'central_id': 'c' * 32, 'token': self.servidor.token,
                       'url': f'http://127.0.0.1:{self.porta}'}
        self.arquivo = self.pasta / 'cliente.json'
        self.arquivo.write_text(json.dumps(self.config), encoding='utf-8')
        self.enterContext(patch.dict(os.environ, {
            'NUNES_METRICAS_DADOS': str(self.origem), 'NUNES_CENTRAL_CONFIG': str(self.arquivo)}))
        self.abrir()
        self.addCleanup(self.fechar)

    def abrir(self):
        self.thread = Thread(target=self.servidor.serve_forever, kwargs={'poll_interval': .01})
        self.thread.start()

    def fechar(self):
        if self.thread.is_alive():
            self.servidor.shutdown(); self.servidor.server_close(); self.thread.join(3)

    def cliente(self):
        return sync.Cliente(self.config, self.origem, aplicacao='cofre-nfe')

    def simular(self, prefixo, pilha, falha_salvar=None, falha_flag=None):
        cenarios.TestMetricasIntegracao.simular(self, prefixo, pilha, falha_salvar, falha_flag)

    def console(self):
        with ExitStack() as pilha:
            self.simular('main', pilha)
            for nome in ('set_app_id', 'sleep', 'pause'):
                pilha.enter_context(patch('main.' + nome))
            pilha.enter_context(patch('main.input_dados', return_value=(
                ['123'], Empresa.MATRIZ, 10, 10, 2026, 2026, TipoDocumento.NFE)))
            main.main()

    def test_console_com_central_desligada_conclui_e_reabertura_envia_sem_duplicar(self):
        self.fechar()
        self.console()
        self.assertEqual(len(self.cliente().pendentes()), 1)
        self.servidor = Servidor(Armazem(self.armazem.caminho, 'c' * 32), self.config['token'], self.porta)
        self.abrir()
        # Abre/fecha o observador sem repetir a operação fiscal.
        confirmado = Event()
        sincronizar_real = sync.Cliente.sincronizar
        def sincronizar(cliente):
            resultado = sincronizar_real(cliente)
            confirmado.set()
            return resultado
        with patch.object(sync.Cliente, 'sincronizar', sincronizar):
            with sync.Sincronizador(aplicacao='cofre-nfe', relatar=lambda _: None):
                self.assertTrue(confirmado.wait(5), 'A confirmação local deve terminar antes da conferência.')
        self.assertEqual(self.armazem.resumo('cofre-nfe')['total'], 1)
        self.assertEqual(self.cliente().pendentes(), [])
        self.console()
        self.assertEqual(self.armazem.resumo('cofre-nfe')['total'], 1)

    def test_web_sincroniza_apos_finalizar_worker_sem_sobrescrever_status(self):
        estado = EstadoInterface()
        gravando, concluir = Event(), Event()
        def salvar(*args, **kwargs):
            gravando.set()
            if not concluir.wait(3):
                raise RuntimeError('O encerramento não aguardou a gravação sintética.')
            return 'documento-sintetico'
        encerrar_original = estado.encerrar
        def encerrar():
            encerrar_original()
            concluir.set()
        with ExitStack() as pilha:
            self.simular('src.execucao_web', pilha, falha_salvar=salvar)
            pilha.enter_context(patch('desktop_windows.identidade_processo'))
            pilha.enter_context(patch('src.controlador_web.EstadoInterface', return_value=estado))
            pilha.enter_context(patch.object(estado, 'encerrar', side_effect=encerrar))
            servidor = Mock()
            def executar():
                estado.iniciar({'notas': '123', 'empresa': 'MATRIZ', 'tipo': 'nfe',
                                'competencia': '2026-10', 'pasta': '2026-10'})
                self.assertTrue(gravando.wait(3))
            pilha.enter_context(patch('desktop_cofre.executar', side_effect=lambda servidor: executar()))
            pilha.enter_context(patch('src.interface_web.criar_servidor', return_value=servidor))
            pilha.enter_context(patch('cofre.informar_falha', side_effect=AssertionError))
            self.assertEqual(cofre.main(Mock(registro={})), 0)
        self.assertFalse(estado.worker.is_alive())
        self.assertEqual(self.cliente().pendentes(), [])
        self.assertEqual(self.armazem.resumo('cofre-nfe')['tipos'], {'nfe': 1, 'cte': 0})
        self.assertNotIn('Estatísticas', estado.dados['status'])

    def test_fila_duplicada_e_cte_sao_enviados_sem_misturar_find_move(self):
        registrar_evento('documento_baixado', 'cte-sintetico', '456', empresa='FILIAL', tipo='cte')
        registrar_evento('arquivo_transferido', 'arquivo-sintetico', '1234', tipo='busca_pdf')
        evento = self.cliente().pendentes()[0]
        fila = self.origem / 'recuperar'; fila.mkdir()
        arquivo = fila / 'sintetico.json'; arquivo.write_text(json.dumps(evento), encoding='utf-8')
        self.assertEqual(self.cliente().sincronizar()['confirmados_neste_ciclo'], 1)
        self.assertEqual(self.armazem.resumo('cofre-nfe')['tipos'], {'nfe': 0, 'cte': 1})
        self.assertEqual(self.armazem.resumo()['total'], 0)
        self.assertTrue(arquivo.exists())
        self.assertEqual(len(sync.Cliente(self.config, self.origem).pendentes()), 1)
        self.assertTrue((self.origem / 'sincronizacao-cofre-nfe.sqlite3').exists())

    def test_resposta_perdida_apos_commit_reenvia_sem_duplicar(self):
        registrar_evento('documento_baixado', 'documento-sintetico', '123', empresa='MATRIZ', tipo='nfe')
        original = sync.requisitar
        def perder(*args, **kwargs):
            original(*args, **kwargs)
            raise OSError('falha sintética após commit')
        with patch.object(sync, 'requisitar', side_effect=perder), self.assertRaises(OSError):
            self.cliente().sincronizar()
        self.assertEqual(self.armazem.resumo('cofre-nfe')['total'], 1)
        self.assertEqual(len(self.cliente().pendentes()), 1)
        self.assertEqual(self.cliente().sincronizar()['pendentes'], 0)
        self.assertEqual(self.armazem.resumo('cofre-nfe')['total'], 1)

    def test_cliente_individual_sem_repositorios_irmaos_e_contrato_igual(self):
        destino = self.pasta / 'individual'; destino.mkdir()
        for nome in ('contrato_estatisticas.py', 'sincronizar_estatisticas.py', 'metricas_nunes.py'):
            shutil.copy2(RAIZ / nome, destino / nome)
        for nome in ('contrato_estatisticas.py', 'sincronizar_estatisticas.py'):
            self.assertEqual((RAIZ / nome).read_bytes(), (RAIZ.parent / 'nunes-hub' / nome).read_bytes())
        resultado = subprocess.run([sys.executable, '-I', '-c',
            'import sys;sys.path.insert(0,sys.argv[1]);'
            'import sincronizar_estatisticas as s;'
            'assert s.Cliente(s.ler_configuracao(),aplicacao="cofre-nfe").sincronizar()["pendentes"]==0',
            str(destino)], cwd=destino, capture_output=True, timeout=10)
        self.assertEqual(resultado.returncode, 0, resultado.stderr.decode(errors='replace'))


if __name__ == '__main__':
    unittest.main()
