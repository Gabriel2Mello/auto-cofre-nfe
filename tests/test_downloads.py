"""Fluxos reais de download/salvamento, com HTTP falso e diretórios temporários."""

from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from requests import Response

import main
from src.config import Config
from src.controlador_web import EstadoInterface, Pedido, executar_lote
from src.enums import Empresa, TipoDocumento
from tests.documentos_sinteticos import CNPJ_EMPRESA, ID_PORTAL, chave_fiscal, pdf_fiscal, xml_fiscal


class TestDownloads(unittest.TestCase):
  def executar(self, modo='web', xml=None, pdf=None, tipo=TipoDocumento.NFE,
               status_xml=200, status_pdf=200):
    with TemporaryDirectory() as temporario, ExitStack() as pilha:
      pilha.enter_context(patch('sincronizar_estatisticas.ler_configuracao', return_value=None))
      raiz = Path(temporario)
      prefixo = 'src.controlador_web' if modo == 'web' else 'main'
      config = Mock(caminho_documento_entrada=str(raiz), cnpj={Empresa.MATRIZ: CNPJ_EMPRESA})
      pilha.enter_context(patch(prefixo + '.Config', return_value=config))
      for nome in ('login', 'extrair_empresas_href', 'trocar_empresa', 'ver_arquivos'):
        pilha.enter_context(patch(prefixo + '.' + nome))
      handler = pilha.enter_context(patch(prefixo + '.EmitenteHandler'))
      handler.return_value.get_nome.return_value = 'SINTETICO'
      pilha.enter_context(patch(prefixo + '.processar_nota', return_value={
          'emitente': 'SINTETICO', 'empresa_id': '1', 'chave': ID_PORTAL, 'codigo_arquivo': '1'}))
      cliente = pilha.enter_context(patch(prefixo + '.TimeoutScraper'))
      sessao = cliente.return_value.__enter__.return_value
      requisicoes = []

      def obter(url, **opcoes):
        requisicoes.append((url, opcoes))
        resposta = Response()
        resposta.url = url
        resposta.status_code = status_xml if url.endswith('.xml') else status_pdf
        resposta._content = (xml if xml is not None else xml_fiscal(tipo)) if url.endswith('.xml') else (pdf if pdf is not None else pdf_fiscal(chave_fiscal(tipo)))
        # Cabeçalhos aparentemente corretos não comprovam o conteúdo.
        resposta.headers['Content-Type'] = 'application/xml' if url.endswith('.xml') else 'application/pdf'
        return resposta

      sessao.get.side_effect = obter
      flag = pilha.enter_context(patch(prefixo + '.marcar_flag'))
      registrar = pilha.enter_context(patch(prefixo + '.registrar_evento'))
      pilha.enter_context(patch('builtins.print'))
      tipo_pasta = 'NF-e' if tipo == TipoDocumento.NFE else 'CT-e'
      arquivos = {}
      for extensao, pasta in [('xml', f'XML - {tipo_pasta}'), ('pdf', f'PDF {tipo_pasta}')]:
        destino = raiz / pasta / '2026' / 'MATRIZ' / Config.MONTHS[10] / f'SINTETICO 123.{extensao}'
        destino.parent.mkdir(parents=True)
        destino.write_bytes(b'ARQUIVO ANTERIOR')
        arquivos[extensao] = destino
      if modo == 'web':
        pedido = Pedido.de_json({'notas': '123', 'empresa': 'MATRIZ', 'tipo': str(tipo),
                                 'competencia': '2026-10', 'pasta': '2026-10'})
        estado = EstadoInterface()
        estado.dados['resultados'] = [{'nota': '123', 'situacao': 'Aguardando', 'detalhe': ''}]
        executar_lote(pedido, estado)
        resultado = estado.snapshot()['resultados'][0]
      else:
        for nome in ('set_app_id', 'sleep', 'pause'):
          pilha.enter_context(patch('main.' + nome))
        pilha.enter_context(patch('main.input_dados', return_value=(['123'], Empresa.MATRIZ, 10, 10, 2026, 2026, tipo)))
        erro = pilha.enter_context(patch('main.handle_error'))
        main.main()
        resultado = {'situacao': 'Erro' if erro.called else 'Concluído',
                     'detalhe': str(erro.call_args.args[0]) if erro.called else ''}
      if flag.called:
        self.assertTrue(all(caminho.read_bytes() == b'ARQUIVO ANTERIOR' for caminho in arquivos.values()))
      saidas = {}
      for ext, caminho in arquivos.items():
        qualificado = caminho.with_stem(caminho.stem + ' - ' + chave_fiscal(tipo))
        saidas[ext] = (qualificado if qualificado.exists() else caminho).read_bytes()
      return resultado, saidas, flag.call_count, registrar.call_count, requisicoes

  def test_respostas_invalidas_nao_substituem_arquivos_nem_concluem(self):
    chave = chave_fiscal()
    xml_valido = xml_fiscal()
    casos = {
      'html_xml': {'xml': b'<html><body>Login</body></html>'},
      'xml_vazio': {'xml': b''},
      'xml_truncado': {'xml': xml_valido[:-12]},
      'xml_resumo': {'xml': b'<resNFe xmlns="http://www.portalfiscal.inf.br/nfe"/>'},
      'xml_numero_divergente': {'xml': xml_fiscal(numero='124')},
      'xml_empresa_divergente': {'xml': xml_fiscal(empresa='00000000000300')},
      'xml_tipo_divergente': {'xml': xml_fiscal(TipoDocumento.CTE)},
      'xml_competencia_divergente': {'xml': xml_fiscal(chave=chave_fiscal(competencia='2609'), emissao='2026-09-01T12:00:00-03:00')},
      'xml_id_divergente': {'xml': xml_fiscal(chave=chave_fiscal(numero='124'))},
      'xml_protocolo_divergente': {'xml': xml_valido.replace(f'<chNFe>{chave}</chNFe>'.encode(), f'<chNFe>{chave_fiscal(numero="124")}</chNFe>'.encode())},
      'xml_empresa_apenas_autorizada': {'xml': xml_valido.replace(b'<dest>', b'<autXML>').replace(b'</dest>', b'</autXML>')},
      'xml_documentos_duplicados': {'xml': xml_valido.replace(b'</NFe>', b'</NFe>' + xml_fiscal(processado=False))},
      'xml_dtd': {'xml': b'<!DOCTYPE nfeProc [<!ENTITY senha SYSTEM "file:///nao-deve-ser-lido">]>' + xml_valido},
      'pdf_html': {'pdf': b'<html><body>Login</body></html>'},
      'pdf_vazio': {'pdf': b''},
      'pdf_falso': {'pdf': b'%PDF-1.7\nconteudo invalido\n%%EOF'},
      'pdf_truncado': {'pdf': pdf_fiscal()[:-30]},
      'pdf_outro_documento': {'pdf': pdf_fiscal(chave_fiscal(numero='124'))},
      'pdf_tipo_divergente_com_referencia': {'pdf': pdf_fiscal(rotulo='DACTE')},
      'pdf_identidade_ambigua': {'pdf': pdf_fiscal(texto=chave + ' ' + chave_fiscal(numero='124'))},
      'pdf_sem_texto': {'pdf': pdf_fiscal(texto='')},
      'pdf_sem_paginas': {'pdf': pdf_fiscal(sem_paginas=True)},
      'pdf_protegido': {'pdf': pdf_fiscal(senha='SENHA-FICTICIA')},
      'redirecionamento_xml': {'status_xml': 302},
      'redirecionamento_pdf': {'status_pdf': 302},
      'parcial_xml': {'status_xml': 206},
      'parcial_pdf': {'status_pdf': 206},
    }
    for modo in ('web', 'console'):
      for nome, alteracoes in casos.items():
        with self.subTest(modo=modo, caso=nome):
          resultado, arquivos, flags, metricas, _ = self.executar(modo=modo, **alteracoes)
          self.assertEqual(resultado['situacao'], 'Erro')
          self.assertTrue(resultado['detalhe'])
          self.assertEqual(arquivos, {'xml': b'ARQUIVO ANTERIOR', 'pdf': b'ARQUIVO ANTERIOR'})
          self.assertEqual((flags, metricas), (0, 0))

  def test_par_valido_conclui_uma_vez_nos_dois_fluxos_e_tipos(self):
    for modo in ('web', 'console'):
      for tipo in TipoDocumento:
        for processado in (True, False):
          with self.subTest(modo=modo, tipo=tipo, processado=processado):
            chave = chave_fiscal(tipo)
            agrupada = ' '.join(chave[i:i + 4] for i in range(0, 44, 4))
            resultado, arquivos, flags, metricas, requisicoes = self.executar(
                modo=modo, tipo=tipo, xml=xml_fiscal(tipo, processado=processado), pdf=pdf_fiscal(chave=chave, texto=agrupada if processado else chave))
            self.assertEqual(resultado['situacao'], 'Concluído')
            self.assertTrue(arquivos['xml'].startswith(b'<'))
            self.assertTrue(arquivos['pdf'].startswith(b'%PDF-'))
            self.assertEqual((flags, metricas), (1, 1))
            self.assertTrue(all(opcoes.get('allow_redirects') is False for _, opcoes in requisicoes))
            self.assertTrue(all(ID_PORTAL in url for url, _ in requisicoes))


  def test_cte_aceita_referencia_nfe_e_empresa_participante(self):
    chave = chave_fiscal(TipoDocumento.CTE)
    for modo in ('web', 'console'):
      for papel in ('rem', 'exped', 'receb', 'toma4'):
        with self.subTest(modo=modo, papel=papel):
          xml = xml_fiscal(TipoDocumento.CTE)
          if papel == 'toma4':
            xml = xml.replace(CNPJ_EMPRESA.encode(), b'00000000000300').replace(
                b'</ide>', f'<toma4><toma>4</toma><CNPJ>{CNPJ_EMPRESA}</CNPJ></toma4></ide>'.encode())
          else:
            xml = xml.replace(b'<dest>', f'<{papel}>'.encode()).replace(b'</dest>', f'</{papel}>'.encode())
          resultado, _, flags, metricas, _ = self.executar(
              modo=modo, tipo=TipoDocumento.CTE, xml=xml,
              pdf=pdf_fiscal(chave, texto=chave + ' Referencia NFe ' + chave_fiscal()))
          self.assertEqual(resultado['situacao'], 'Concluído')
          self.assertEqual((flags, metricas), (1, 1))


if __name__ == '__main__':
  unittest.main()
