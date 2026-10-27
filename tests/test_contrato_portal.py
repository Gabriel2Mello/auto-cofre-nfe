"""Contrato observado do portal, com HTTP falso e sem dados operacionais."""
from contextlib import ExitStack
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from requests import HTTPError, Response

import main
from src.config import Config
from src.controlador_web import EstadoInterface, Pedido
from src.core import carregar_dados, marcar_flag, processar_nota, trocar_empresa
from src.enums import Empresa, TipoDocumento
from src.execucao_web import executar_lote
from src.parsers import confirmar_empresa_ativa, confirmar_flag


AMOSTRAS = Path(__file__).with_name('amostras_portal')
CNPJ = '00000000000100'


def resposta(corpo='', status=200):
  resultado = Response()
  resultado.status_code = status
  resultado.url = Config.URL_BASE + '/nfe/empresa'
  resultado.encoding = 'utf-8'
  resultado._content = corpo.encode('utf-8')
  return resultado


def pagina(linhas, total=None):
  dados = {'aaData': linhas}
  if total is not None:
    dados['iTotalDisplayRecords'] = total
  return resposta(json.dumps(dados))


def linha(indice, mes='09', numero='123'):
  return ['', f'EMITENTE FICTICIO {indice}', f'01/{mes}/2026', numero, '10,00',
          f'<a class="linkManifestar" onclick="manifestar(0,\'{str(indice).zfill(22)}\')"></a>'
          f'<a class="iconeXML" href="/nfe/download-arquivo/nfe/1/{indice}.xml"></a>'
          f'<div id="flagArq{indice}" class="flag10"></div>']


class TestEmpresaAtiva(unittest.TestCase):
  def setUp(self):
    self.html = (AMOSTRAS / 'empresa_ativa.html').read_text(encoding='utf-8')
    self.links = {'00.000.000/0001-00': '/login/trocarLogin?vid=123'}

  def test_troca_exige_cnpj_do_cabecalho_ativo(self):
    sessao = Mock(get=Mock(return_value=resposta(self.html)))
    trocar_empresa(sessao, Empresa.MATRIZ, self.links, CNPJ)
    sessao.get.assert_called_once()

  def test_destino_intermediario_le_painel_uma_vez_sem_repetir_troca(self):
    intermediaria = resposta('<html><p>Entrada do portal</p></html>')
    intermediaria.url = Config.URL_BASE + '/empresa'
    sessao = Mock(get=Mock(side_effect=[intermediaria, resposta(self.html)]))
    trocar_empresa(sessao, Empresa.MATRIZ, self.links, CNPJ)
    self.assertEqual(sessao.get.call_count, 2)
    primeira, segunda = sessao.get.call_args_list
    self.assertIn('/login/trocarLogin?', primeira.kwargs['url'])
    self.assertEqual(segunda.kwargs['url'], Config.URL_BASE + '/nfe/empresa')
    self.assertFalse(segunda.kwargs['allow_redirects'])

  def test_painel_apos_intermediaria_recusa_contexto_errado_login_ou_redirecionamento(self):
    for final in (resposta(self.html.replace('0001-00', '0002-00')),
                  resposta('<form><input type="password"></form>'),
                  resposta('', 302), resposta('', 503)):
      with self.subTest(status=final.status_code):
        intermediaria = resposta('<html>Entrada</html>')
        intermediaria.url = Config.URL_BASE + '/empresa'
        sessao = Mock(get=Mock(side_effect=[intermediaria, final]))
        with self.assertRaises((ValueError, HTTPError)):
          trocar_empresa(sessao, Empresa.MATRIZ, self.links, CNPJ)
        self.assertEqual(sessao.get.call_count, 2)

  def test_confirmacao_canonica_recusa_url_externa_e_rota_inesperada(self):
    for url in ('https://externo.invalid/nfe/empresa', Config.URL_BASE + '/login'):
      with self.subTest(url=url):
        intermediaria = resposta('Entrada')
        intermediaria.url = Config.URL_BASE + '/empresa'
        final = resposta(self.html)
        final.url = url
        sessao = Mock(get=Mock(side_effect=[intermediaria, final]))
        with self.assertRaises(ValueError):
          trocar_empresa(sessao, Empresa.MATRIZ, self.links, CNPJ)
        self.assertEqual(sessao.get.call_count, 2)

  def test_painel_sem_cabecalho_nao_repete_confirmacao(self):
    sessao = Mock(get=Mock(return_value=resposta('<html>Sem contexto</html>')))
    with self.assertRaises(ValueError):
      trocar_empresa(sessao, Empresa.MATRIZ, self.links, CNPJ)
    sessao.get.assert_called_once()

  def test_retorno_ao_login_so_libera_com_empresa_confirmada_no_painel(self):
    for final, sucesso in ((resposta(self.html), True),
                           (resposta('<form><input type="password"></form>'), False),
                           (resposta('', 307), False)):
      with self.subTest(sucesso=sucesso, status=final.status_code):
        login = resposta('<form><input type="password"></form>')
        login.url = Config.URL_BASE + '/login/enviar'
        sessao = Mock(get=Mock(side_effect=[login, final]))
        if sucesso:
          trocar_empresa(sessao, Empresa.MATRIZ, self.links, CNPJ)
        else:
          with self.assertRaises(ValueError):
            trocar_empresa(sessao, Empresa.MATRIZ, self.links, CNPJ)
        self.assertEqual(sessao.get.call_count, 2)
        self.assertFalse(sessao.get.call_args.kwargs['allow_redirects'])

  def test_login_lista_vinculos_cabecalho_ambiguo_e_empresa_errada_nao_confirmam(self):
    invalidos = [
      '<form action="/login/enviar"><input type="password"></form>',
      '<a href="/login/trocarLogin?vid=123">EMPRESA</a><span>00.000.000/0001-00</span>',
      self.html.replace('0001-00', '0002-00'), self.html + self.html,
      self.html.replace('EMPRESA FICTICIA', 'OUTRA (00.000.000/0002-00)'),
      self.html.replace('00.000.000/0001-00', ''),
    ]
    for html in invalidos:
      with self.subTest(html=invalidos.index(html)):
        sessao = Mock(get=Mock(return_value=resposta(html)))
        with self.assertRaises(ValueError) as erro:
          trocar_empresa(sessao, Empresa.MATRIZ, self.links, CNPJ)
        self.assertNotIn(CNPJ, str(erro.exception))
        self.assertNotIn('00.000.000', str(erro.exception))

  def test_cnpj_na_lista_de_troca_nao_substitui_contexto_errado(self):
    html = self.html.replace('0001-00', '0002-00') + '<a>00.000.000/0001-00</a>'
    with self.assertRaises(ValueError):
      confirmar_empresa_ativa(html, CNPJ)

  def test_recusa_link_externo_antes_da_requisicao_e_resposta_externa(self):
    sessao = Mock()
    with self.assertRaises(ValueError):
      trocar_empresa(sessao, Empresa.MATRIZ, {'00.000.000/0001-00': 'https://externo.invalid/'}, CNPJ)
    sessao.get.assert_not_called()
    r = resposta(self.html)
    r.url = 'https://externo.invalid/'
    sessao.get.return_value = r
    with self.assertRaises(ValueError):
      trocar_empresa(sessao, Empresa.MATRIZ, self.links, CNPJ)

  def test_falha_de_contexto_bloqueia_consulta_download_gravacao_e_flag_nos_dois_fluxos(self):
    for modo in ('web', 'console'):
      with self.subTest(modo=modo), ExitStack() as pilha:
        prefixo = 'src.execucao_web' if modo == 'web' else 'main'
        config = Mock(caminho_documento_entrada='.', cnpj={Empresa.MATRIZ: CNPJ})
        pilha.enter_context(patch(prefixo + '.Config', return_value=config))
        cliente = pilha.enter_context(patch(prefixo + '.TimeoutScraper'))
        cliente.return_value.__enter__.return_value.get.return_value = resposta(self.html.replace('0001-00', '0002-00'))
        pilha.enter_context(patch(prefixo + '.login', return_value=''))
        pilha.enter_context(patch(prefixo + '.extrair_empresas_href', return_value=self.links))
        pilha.enter_context(patch(prefixo + '.EmitenteHandler'))
        fronteiras = [pilha.enter_context(patch(prefixo + '.' + nome)) for nome in
                      ('ver_arquivos', 'processar_nota', 'baixar_arquivos', 'salvar_arquivos', 'registrar_evento', 'marcar_flag')]
        if modo == 'web':
          pedido = Pedido.de_json({'notas': '123', 'empresa': 'MATRIZ', 'tipo': 'nfe',
                                   'competencia': '2026-10', 'pasta': '2026-10'})
          with self.assertRaises(ValueError):
            executar_lote(pedido, EstadoInterface())
        else:
          pilha.enter_context(patch('main.input_dados', return_value=(
            ['123'], Empresa.MATRIZ, 10, 10, 2026, 2026, TipoDocumento.NFE)))
          pilha.enter_context(patch('main.set_app_id'))
          with self.assertRaises(ValueError):
            main.executar()
        for fronteira in fronteiras:
          fronteira.assert_not_called()


class TestPaginacao(unittest.TestCase):
  def test_documento_e_emitente_da_segunda_pagina_participam_da_decisao(self):
    for tipo in TipoDocumento:
      with self.subTest(tipo=tipo):
        linhas = [linha(i, mes='10' if i in (1, 26) else '09') for i in range(1, 27)]
        if tipo == TipoDocumento.CTE:
          linhas = [l[:2] + ['DESTINATARIO FICTICIO'] + l[2:] for l in linhas]
        sessao = Mock(post=Mock(side_effect=[pagina(linhas[:25], '26'), pagina(linhas[25:], '26')]))
        escolha = Mock(side_effect=lambda opcoes: opcoes[-1])
        with patch('builtins.print'):
          resultado = processar_nota(sessao, '123', tipo, 10, 2026, escolha)
        self.assertEqual(len(escolha.call_args.args[0]), 2)
        self.assertEqual(resultado['codigo_arquivo'], '26')
        self.assertEqual([c.kwargs['data']['iDisplayStart'] for c in sessao.post.call_args_list], ['0', '25'])
        self.assertTrue(all(c.kwargs['allow_redirects'] is False for c in sessao.post.call_args_list))
        self.assertTrue(all(c.kwargs['data']['nro_nota_de'] == '123'
                            and c.kwargs['data']['nro_nota_ate'] == '123'
                            for c in sessao.post.call_args_list))

  def test_sem_total_consulta_ate_pagina_curta(self):
    sessao = Mock(post=Mock(side_effect=[pagina([linha(i) for i in range(25)]), pagina([])]))
    self.assertEqual(len(carregar_dados(sessao, '123', TipoDocumento.NFE)), 25)
    self.assertEqual(sessao.post.call_count, 2)

  def test_total_zero_nao_pede_outra_pagina(self):
    sessao = Mock(post=Mock(return_value=pagina([], 0)))
    self.assertEqual(carregar_dados(sessao, '123', TipoDocumento.NFE), [])
    sessao.post.assert_called_once()

  def test_recusa_pagina_repetida_incompleta_total_mutavel_e_resposta_invalida(self):
    primeira = [linha(i) for i in range(25)]
    cenarios = [
      [pagina(primeira, 50), pagina(primeira, 50)],
      [pagina(primeira, 26), pagina([], 26)],
      [pagina(primeira, 26), pagina([linha(26)], 27)],
      [pagina(primeira, 26), pagina([linha(26)])],
      [pagina([linha(1)], 0)], [pagina([], -1)], [pagina([], True)],
      [resposta('{"aaData":[1]}')], [resposta('{"aaData":null}')],
      [resposta('{"sucesso":false}')], [resposta('<html>LOGIN</html>')], [resposta('', 302)],
    ]
    for indice, respostas in enumerate(cenarios):
      with self.subTest(cenario=indice):
        sessao = Mock(post=Mock(side_effect=respostas))
        with self.assertRaises(ValueError):
          carregar_dados(sessao, '123', TipoDocumento.NFE)


class TestConfirmacaoFlag(unittest.TestCase):
  def setUp(self):
    self.marcacao = (AMOSTRAS / 'marcacao.html').read_text(encoding='utf-8')

  def test_corpo_vazio_exige_releitura_da_flag_do_documento(self):
    sessao = Mock(post=Mock(side_effect=[resposta(''), pagina([[self.marcacao]], 1)]))
    marcar_flag(sessao, '123', nota='123', tipo=TipoDocumento.NFE)
    self.assertEqual(sessao.post.call_count, 2)
    escrita = sessao.post.call_args_list[0]
    self.assertIn('/seta-flag/123/10', escrita.args[0])
    self.assertFalse(escrita.kwargs['allow_redirects'])
    self.assertTrue(sessao.post.call_args_list[1].kwargs['url'].endswith('/load'))

  def test_recusa_redirecionamento_sem_repetir_escrita(self):
    sessao = Mock(post=Mock(return_value=resposta('', 302)))
    with self.assertRaises(RuntimeError):
      marcar_flag(sessao, '123', nota='123', tipo=TipoDocumento.NFE)
    sessao.post.assert_called_once()

  def test_200_nao_comprova_marcacao_ausente_errada_ambigua_ou_de_outro_documento(self):
    invalidos = [[], [[self.marcacao.replace('class="flag10"', 'class="flag0"', 1)]],
                [[self.marcacao.replace('flagArq123', 'flagArq124')]],
                [[self.marcacao], [self.marcacao]],
                [[self.marcacao.replace('class="flag10"', 'class="flag100"', 1)]]]
    for indice, linhas in enumerate(invalidos):
      with self.subTest(cenario=indice):
        sessao = Mock(post=Mock(side_effect=[resposta('{"sucesso":true}'), pagina(linhas, len(linhas))]))
        with self.assertRaises(RuntimeError):
          marcar_flag(sessao, '123', nota='123', tipo=TipoDocumento.NFE)
        self.assertEqual(sessao.post.call_count, 2)

  def test_pagina_login_ou_json_de_erro_na_releitura_nao_confirmam(self):
    for corpo in ('<html>LOGIN</html>', '{"sucesso":false}'):
      sessao = Mock(post=Mock(side_effect=[resposta(''), resposta(corpo)]))
      with self.assertRaises(ValueError):
        marcar_flag(sessao, '123', nota='123', tipo=TipoDocumento.NFE)
      self.assertEqual(sessao.post.call_count, 2)

  def test_opcao_flag10_no_balao_nao_e_confirmacao_do_estado_atual(self):
    with self.assertRaises(RuntimeError):
      confirmar_flag([[self.marcacao.replace('class="flag10"', 'class="flag0"', 1)]], '123', 10)


if __name__ == '__main__':
  unittest.main()
