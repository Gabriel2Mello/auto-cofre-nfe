"""HTML declarativo e legado do portal; documentos e HTTP inteiramente fictícios."""
from html import escape
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup
from requests import Response

from src.config import Config
from src.core import baixar_arquivos, processar_nota
from src.enums import TipoDocumento
from src.parsers import LinhaNFe, extrair_dados
from tests.documentos_sinteticos import ID_PORTAL, CNPJ_EMPRESA, pdf_fiscal, xml_fiscal


AMOSTRAS = Path(__file__).with_name('amostras_portal')


def evento(nome, argumentos):
  return (f'<a class="linkManifestar" data-on-click="{nome}" '
          f'data-on-click-args="{escape(json.dumps(argumentos), quote=True)}">Autorizada</a>')


def documento(acoes):
  return LinhaNFe.de_lista(['', 'EMITENTE FICTICIO', '01/10/26', '55/123/1', '1,00',
      acoes, f'<a class="iconeXML" href="/nfe/download-arquivo/nfe/1/{ID_PORTAL}.xml"></a>'
      '<div id="flagArq123" class="flag10"></div>'])


class TestExtracaoDocumentos(unittest.TestCase):
  def setUp(self):
    self.impressao = patch('builtins.print')
    self.impressao.start()
    self.addCleanup(self.impressao.stop)

  def test_html_atual_seleciona_e_monta_downloads_nfe_cte_nas_duas_empresas(self):
    for tipo in TipoDocumento:
      for empresa_id in ('1', '2'):
        with self.subTest(tipo=tipo, empresa=empresa_id):
          html = (AMOSTRAS / f'{tipo}_atual.html').read_text(encoding='utf-8')
          html = html.replace('/1/', f'/{empresa_id}/')
          modelo = '55' if tipo == TipoDocumento.NFE else '57'
          campos = ['', 'EMITENTE FICTICIO', '01/10/26', f'{modelo}/123/1', '1,00', html]
          if tipo == TipoDocumento.CTE:
            campos.insert(2, 'DESTINATARIO FICTICIO')
          consulta = Mock(status_code=200)
          consulta.json.return_value = {'aaData': [campos], 'iTotalDisplayRecords': 1}
          sessao = Mock(post=Mock(return_value=consulta))
          dados = processar_nota(sessao, '123', tipo, 10, 2026)
          self.assertEqual(dados, {'chave': ID_PORTAL, 'empresa_id': empresa_id,
              'codigo_arquivo': '123', 'emitente': 'EMITENTE FICTICIO'})
          xml, pdf = xml_fiscal(tipo), pdf_fiscal()
          respostas = []
          for conteudo in (xml, pdf):
            resposta = Response()
            resposta.status_code = 200
            resposta._content = conteudo
            respostas.append(resposta)
          sessao.get.side_effect = respostas
          self.assertEqual(baixar_arquivos(sessao, dados['empresa_id'], dados['chave'], tipo,
              nota='123', cnpj_empresa=CNPJ_EMPRESA, mes_nota=10, ano_nota=2026), (xml, pdf))
          caminho_pdf = 'danfe' if tipo == TipoDocumento.NFE else 'dacte'
          self.assertEqual([c.args[0] for c in sessao.get.call_args_list], [
              f'{Config.URL_BASE}/nfe/download-arquivo/{tipo}/{empresa_id}/{ID_PORTAL}.xml',
              f'{Config.URL_BASE}/nfe/ver-{caminho_pdf}/{tipo}/{empresa_id}/{ID_PORTAL}.pdf'])
          self.assertTrue(all(c.kwargs['allow_redirects'] is False for c in sessao.get.call_args_list))

  def test_preserva_onclick_antigo_nfe_cte(self):
    for tipo in TipoDocumento:
      with self.subTest(tipo=tipo):
        html = (AMOSTRAS / f'{tipo}_atual.html').read_text(encoding='utf-8')
        soup = BeautifulSoup(html, 'lxml')
        for link in soup.select('a.linkManifestar'):
          link.attrs.pop('data-on-click')
          link.attrs.pop('data-on-click-args')
          link['onclick'] = f"consultarSituacaoNota('empresa','{ID_PORTAL}')"
        self.assertEqual(extrair_dados(documento(str(soup)))['chave'], ID_PORTAL)

  def test_manifestacao_com_prefixo_de_empresa_tambem_identifica_nota(self):
    acao = evento('manifestarNFE', ['empresa', '1/' + ID_PORTAL])
    self.assertEqual(extrair_dados(documento(acao))['chave'], ID_PORTAL)

  def test_html_misto_prioriza_evento_atual_sem_executar_onclick(self):
    acoes = evento('consultarSituacaoNota', ['empresa', ID_PORTAL])
    acoes += '<a class="linkManifestar" onclick="javascript_invalido()"></a>'
    self.assertEqual(extrair_dados(documento(acoes))['chave'], ID_PORTAL)

  def test_argumentos_invalidos_nao_caem_no_formato_antigo_nem_expoem_conteudo(self):
    invalidos = ['', 'nao e JSON', 'executarCodigo()', 'null', '{}', '[]',
                 '["empresa"]', '["empresa",null]', '["empresa",22]',
                 '["empresa",[]]', '["outro","' + ID_PORTAL + '"]',
                 '["empresa","' + ID_PORTAL + '","extra"]']
    for argumentos in invalidos:
      with self.subTest(argumentos=argumentos):
        acao = ('<a class="linkManifestar" data-on-click="consultarSituacaoNota" '
                f'data-on-click-args="{escape(argumentos, quote=True)}" '
                f'onclick="consultarSituacaoNota(0,\'{ID_PORTAL}\')"></a>')
        with self.assertRaises(ValueError) as erro:
          extrair_dados(documento(acao))
        self.assertEqual(str(erro.exception), 'Não foi possível identificar a chave da nota no Cofre.')

  def test_recusa_identificadores_invalidos_e_nao_confunde_chave_fiscal(self):
    for chave in ('P' * 21, 'P' * 23, '1' * 44, 'P' * 21 + '-', 'Á' * 22,
                  '1/' + ID_PORTAL, '../' + ID_PORTAL):
      with self.subTest(chave=chave), self.assertRaises(ValueError):
        extrair_dados(documento(evento('consultarSituacaoNota', ['empresa', chave])))
    for caminho in (ID_PORTAL, 'x/' + ID_PORTAL, '/1/' + ID_PORTAL, '1/2/' + ID_PORTAL):
      with self.subTest(caminho=caminho), self.assertRaises(ValueError):
        extrair_dados(documento(evento('manifestarNFE', ['empresa', caminho])))

  def test_recusa_eventos_com_identificadores_divergentes(self):
    acoes = evento('consultarSituacaoNota', ['empresa', ID_PORTAL])
    acoes += evento('manifestarNFE', ['empresa', '1/' + 'Q' * 22])
    with self.assertRaisesRegex(ValueError, '^Identificadores da nota divergentes no Cofre\\.$'):
      extrair_dados(documento(acoes))

  def test_evento_desconhecido_ou_sem_argumentos_nao_identifica_documento(self):
    for acao in (evento('outraFuncao', ['empresa', ID_PORTAL]),
                 '<a class="linkManifestar" data-on-click="consultarSituacaoNota"></a>',
                 '<a class="linkManifestar">Autorizada</a>'):
      with self.subTest(acao=acao), self.assertRaises(ValueError):
        extrair_dados(documento(acao))


if __name__ == '__main__':
  unittest.main()
