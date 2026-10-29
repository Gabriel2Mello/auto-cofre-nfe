"""Fluxo com parser e sinalização reais sobre HTTP e documentos sintéticos."""
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup
from requests import Response

import main
from src.controlador_web import EstadoInterface, Pedido
from src.enums import Empresa, TipoDocumento
from src.execucao_web import executar_lote
from tests.documentos_sinteticos import CNPJ_EMPRESA, pdf_fiscal, xml_fiscal


AMOSTRAS = Path(__file__).with_name('amostras_portal')


def resposta(conteudo=b''):
  resultado = Response()
  resultado.status_code = 200
  resultado._content = conteudo
  return resultado


class TestSinalizacaoFluxo(unittest.TestCase):
  def executar(self, modo, tipo, notas, falha, flag_inicial=0):
    with TemporaryDirectory() as temporario, ExitStack() as pilha:
      base = Path(temporario)
      empresa = Empresa.FILIAL
      prefixo = 'src.execucao_web' if modo == 'web' else 'main'
      config = Mock(caminho_documento_entrada=str(base),
                    cnpj={Empresa.MATRIZ: CNPJ_EMPRESA, empresa: CNPJ_EMPRESA})
      pilha.enter_context(patch(prefixo + '.Config', return_value=config))
      pilha.enter_context(patch('src.gravacao_documentos.RAIZ_PROJETO', base / 'registros'))
      for nome in ('login', 'extrair_empresas_href', 'trocar_empresa', 'ver_arquivos'):
        pilha.enter_context(patch(prefixo + '.' + nome))
      handler = pilha.enter_context(patch(prefixo + '.EmitenteHandler'))
      handler.return_value.get_nome.return_value = 'SINTETICO'
      metrica = pilha.enter_context(patch(prefixo + '.registrar_evento'))
      sessao = pilha.enter_context(patch(prefixo + '.TimeoutScraper')).return_value.__enter__.return_value
      marcacoes = {nota: flag_inicial for nota in notas}
      escritas = []

      def postar(url, **opcoes):
        if '/seta-flag/' in url:
          codigo, valor = url.rsplit('/', 2)[1:]
          # A flag só pode ser enviada depois de publicar XML e PDF (e cópia CT-e).
          rotulo = 'NF-e' if tipo == TipoDocumento.NFE else 'CT-e'
          for pasta, ext in ((f'XML - {rotulo}', 'xml'), (f'PDF {rotulo}', 'pdf')):
            self.assertTrue((base / pasta / '2026' / empresa / 'OUTUBRO' / f'SINTETICO {codigo}.{ext}').is_file())
          if tipo == TipoDocumento.CTE:
            self.assertTrue((base / 'XML - CT-e/2026' / empresa / 'OUTUBRO' / f'SINTETICO {codigo} copia.xml').is_file())
          escritas.append(codigo)
          marcacoes[codigo] = int(valor)
          return resposta()
        self.assertTrue(url.endswith('/load'))
        nota = opcoes['data']['nro_nota_de']
        html = (AMOSTRAS / f'{tipo}_atual.html').read_text(encoding='utf-8')
        html = html.replace('flagArq123', 'flagArq' + nota).replace('class="flag10"', f'class="flag{marcacoes[nota]}"')
        if nota == falha:
          soup = BeautifulSoup(html, 'lxml')
          for link in soup.select('a.linkManifestar'):
            link.attrs.pop('data-on-click')
            link.attrs.pop('data-on-click-args')
          html = str(soup)
        campos = ['', 'EMITENTE FICTICIO', '01/10/26', nota, '1,00', html]
        if tipo == TipoDocumento.CTE:
          campos.insert(2, 'DESTINATARIO FICTICIO')
        consulta = Mock(status_code=200)
        consulta.json.return_value = {'aaData': [campos], 'iTotalDisplayRecords': 1}
        return consulta

      sessao.post.side_effect = postar
      sessao.get.side_effect = lambda url, **opcoes: resposta(
          xml_fiscal(tipo) if url.endswith('.xml') else pdf_fiscal())
      pilha.enter_context(patch('builtins.print'))
      if modo == 'web':
        pedido = Pedido.de_json({'notas': ','.join(notas), 'empresa': str(empresa), 'tipo': str(tipo),
            'competencia': '2026-10', 'pasta': '2026-10'})
        estado = EstadoInterface()
        estado.dados['resultados'] = [{'nota': n, 'situacao': 'Aguardando', 'detalhe': ''} for n in notas]
        executar_lote(pedido, estado)
        resultados = estado.snapshot()['resultados']
      else:
        for nome in ('set_app_id', 'sleep', 'pause'):
          pilha.enter_context(patch('main.' + nome))
        erro = pilha.enter_context(patch('main.handle_error'))
        pilha.enter_context(patch('main.input_dados', return_value=(notas, empresa,
            10, 10, 2026, 2026, tipo)))
        self.assertEqual(main.executar(), 1)
        self.assertEqual(str(erro.call_args.args[0]), 'Não foi possível identificar a chave da nota no Cofre.')
        resultados = []
      return escritas, marcacoes, metrica.call_count, sessao.get.call_count, resultados

  def test_erro_real_de_extracao_nao_baixa_conta_nem_envia_flag(self):
    for modo in ('web', 'console'):
      for tipo in TipoDocumento:
        with self.subTest(modo=modo, tipo=tipo):
          escritas, flags, metricas, downloads, resultados = self.executar(modo, tipo, ['123'], '123')
          self.assertEqual((escritas, flags, metricas, downloads), ([], {'123': 0}, 0, 0))
          if modo == 'web':
            self.assertEqual(resultados[0]['situacao'], 'Erro')
            self.assertIn('Não foi possível identificar a chave da nota no Cofre.', resultados[0]['detalhe'])

  def test_erro_na_segunda_nota_nao_reaproveita_sinalizacao_da_primeira(self):
    for modo in ('web', 'console'):
      for tipo in TipoDocumento:
        with self.subTest(modo=modo, tipo=tipo):
          escritas, flags, metricas, downloads, resultados = self.executar(modo, tipo, ['123', '124'], '124')
          self.assertEqual((escritas, flags, metricas, downloads), (['123'], {'123': 10, '124': 0}, 1, 2))
          if modo == 'web':
            self.assertEqual([r['situacao'] for r in resultados], ['Concluído', 'Erro'])

  def test_erro_nao_reenvia_nem_remove_flag_anterior(self):
    for modo in ('web', 'console'):
      for tipo in TipoDocumento:
        with self.subTest(modo=modo, tipo=tipo):
          escritas, flags, metricas, downloads, _ = self.executar(modo, tipo, ['123'], '123', flag_inicial=10)
          self.assertEqual((escritas, flags, metricas, downloads), ([], {'123': 10}, 0, 0))


if __name__ == '__main__':
  unittest.main()
