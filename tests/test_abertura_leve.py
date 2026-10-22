"""Abertura em processo novo sem carregar bibliotecas de download/validação."""
from pathlib import Path
import subprocess
import sys
import unittest


class TestAberturaLeve(unittest.TestCase):
  def test_painel_cria_estado_e_servidor_sem_dependencias_de_execucao(self):
    codigo = '''
import importlib.abc
import sys
class RecusarExecucao(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('bs4', 'cloudscraper', 'pypdf', 'requests'):
            raise ImportError('Dependência de execução antecipada: ' + fullname)
sys.meta_path.insert(0, RecusarExecucao())
from src.controlador_web import EstadoInterface, Pedido
from src.interface_web import criar_servidor
pedido = Pedido.de_json(dict(notas='123', empresa='MATRIZ', tipo='nfe', competencia='2026-10', pasta='2026-10'))
estado = EstadoInterface()
servidor = criar_servidor(estado)
try:
    assert not estado.dados['ativo']
    assert estado.worker is None
finally:
    servidor.server_close()
estado = EstadoInterface()
estado.iniciar(dict(notas='123', empresa='MATRIZ', tipo='nfe', competencia='2026-10', pasta='2026-10'))
estado.worker.join(3)
assert not estado.worker.is_alive()
assert not estado.dados['ativo']
assert 'Faltam dependências' in estado.dados['status']
assert estado.dados['resultados'][0]['situacao'] == 'Não processado'
'''
    resultado = subprocess.run([sys.executable, '-c', codigo],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=15)
    self.assertEqual(resultado.returncode, 0, resultado.stderr)
