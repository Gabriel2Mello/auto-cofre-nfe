"""O laboratório instalado não pode iniciar operação fiscal."""
import unittest
from unittest.mock import patch

from src.controlador_web import EstadoInterface


class TestPiloto(unittest.TestCase):
    def test_piloto_recusa_antes_de_ler_pedido_ou_iniciar_worker(self):
        estado = EstadoInterface()
        with patch('cofre_instalacao.piloto', return_value=True):
            with self.assertRaisesRegex(ValueError, 'fiscais estão desativadas'):
                estado.iniciar({})
        self.assertIsNone(estado.worker)


if __name__ == '__main__':
    unittest.main()
