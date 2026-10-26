"""Falhas e recuperação em disco real temporário; sem portal nem dados fiscais reais."""

from dataclasses import replace
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import recuperar_documentos
from integracao_hub import IntegracaoLocal
from src import gravacao_documentos as gravacao
from src.enums import Empresa, TipoDocumento
from tests import test_downloads
from tests.documentos_sinteticos import CNPJ_EMPRESA, chave_fiscal, pdf_fiscal, xml_fiscal


class TestGravacaoDocumentos(unittest.TestCase):
  def setUp(self):
    self.temporario = Path(self.enterContext(TemporaryDirectory()))
    self.base = self.temporario / 'documentos'
    self.base.mkdir()
    self.projeto = self.temporario / 'projeto'
    self.projeto.mkdir()
    self.enterContext(patch.object(gravacao, 'RAIZ_PROJETO', self.projeto))
    self.contexto = gravacao.ContextoGravacao('SINTETICO', '123', Empresa.MATRIZ, 10, '2026',
                                            TipoDocumento.NFE, CNPJ_EMPRESA, 10, 2026)
    self.enterContext(patch('builtins.print'))
    self.enterContext(patch.dict(os.environ, {
        'NUNES_HUB_DADOS': str(self.temporario / 'presenca'),
        'NUNES_METRICAS_DADOS': str(self.temporario / 'metricas')}))

  def destinos(self, base=None, tipo=TipoDocumento.NFE, nome='SINTETICO 123'):
    raiz = base or self.base
    rotulo = 'NF-e' if tipo == TipoDocumento.NFE else 'CT-e'
    xml = raiz / f'XML - {rotulo}/2026/MATRIZ/OUTUBRO'
    pdf = raiz / f'PDF {rotulo}/2026/MATRIZ/OUTUBRO'
    saidas = [pdf / f'{nome}.pdf', xml / f'{nome}.xml']
    if tipo == TipoDocumento.CTE:
      saidas.append(xml / f'{nome} copia.xml')
    return saidas

  def anterior(self, base, tipo):
    caminhos = self.destinos(base, tipo)
    for caminho in caminhos:
      caminho.parent.mkdir(parents=True, exist_ok=True)
      caminho.write_bytes(b'ARQUIVO ANTERIOR')
    return caminhos

  def dados(self, tipo=TipoDocumento.NFE, outra_chave=False):
    chave = chave_fiscal(tipo)
    xml = xml_fiscal(tipo)
    if outra_chave:
      nova = chave[:22] + '002' + chave[25:]
      xml = xml.replace(chave.encode(), nova.encode()).replace(b'<serie>1</serie>', b'<serie>2</serie>')
      chave = nova
    return xml, pdf_fiscal(chave), chave

  def salvar(self, base=None, tipo=TipoDocumento.NFE, outra_chave=False):
    xml, pdf, _ = self.dados(tipo, outra_chave)
    return gravacao.gravar_conjunto(xml, pdf, replace(self.contexto, tipo=tipo), base or self.base)

  def manifesto(self, base, identificador):
    return gravacao._pasta_registro(base.resolve(), identificador) / 'manifesto.json'

  def test_registros_ficam_no_projeto_independente_do_diretorio_atual(self):
    anterior = Path.cwd()
    try:
      os.chdir(self.base)
      self.salvar()
    finally:
      os.chdir(anterior)
    registros = list((self.projeto / '.cofre-gravacoes').rglob('manifesto.json'))
    self.assertEqual(len(registros), 1)
    self.assertFalse((self.base / '.cofre-gravacoes').exists())
    self.assertEqual(gravacao.listar_gravacoes(self.base)[0]['estado'], 'concluido')

  def test_pendencias_de_destinos_distintos_nao_se_misturam(self):
    identificador = self.pendencia()
    outra_base = self.temporario / 'outros-documentos'
    outra_base.mkdir()
    self.assertEqual(gravacao.listar_gravacoes(outra_base), [])
    with self.assertRaises(ValueError):
      gravacao.recuperar_gravacao(outra_base, identificador)
    self.salvar(outra_base)
    with self.assertRaises(gravacao.GravacaoPendente):
      self.salvar()

  def registro_legado(self):
    identificador = self.pendencia()
    local = self.manifesto(self.base, identificador).parent
    legado = self.base / '.cofre-gravacoes' / identificador
    legado.parent.mkdir()
    local.rename(legado)
    return identificador, legado / 'manifesto.json'

  def test_recupera_legado_gravando_estado_somente_no_projeto(self):
    identificador, legado = self.registro_legado()
    antes = legado.read_bytes()
    self.assertEqual(gravacao.listar_gravacoes(self.base)[0]['estado'], 'pronto')
    self.assertEqual(legado.read_bytes(), antes)
    with self.assertRaises(gravacao.GravacaoPendente):
      self.salvar()
    self.assertEqual(gravacao.recuperar_gravacao(self.base, identificador), 'SINTETICO 123')
    self.assertEqual(legado.read_bytes(), antes)
    self.assertEqual(json.loads(self.manifesto(self.base, identificador).read_text())['estado'], 'concluido')
    self.assertEqual([r['estado'] for r in gravacao.listar_gravacoes(self.base)], ['concluido'])
    self.assertEqual(gravacao.recuperar_gravacao(self.base, identificador), 'SINTETICO 123')

  def test_abandona_legado_sem_alterar_registro_no_compartilhamento(self):
    identificador, legado = self.registro_legado()
    antes = legado.read_bytes()
    gravacao.abandonar_preparacao(self.base, identificador)
    self.assertEqual(legado.read_bytes(), antes)
    self.assertEqual([r['estado'] for r in gravacao.listar_gravacoes(self.base)], ['abandonado'])
    self.assertEqual(self.salvar(), 'SINTETICO 123')

  def test_falha_no_registro_local_nao_cria_registro_no_compartilhamento(self):
    (self.projeto / '.cofre-gravacoes').write_bytes(b'OCUPADO')
    with self.assertRaisesRegex(RuntimeError, 'Nenhum documento foi publicado'):
      self.salvar()
    self.assertFalse((self.base / '.cofre-gravacoes').exists())
    self.assertFalse(any(p.exists() for p in self.destinos()))

  def test_falha_no_manifesto_inicial_nao_bloqueia_outra_baixa(self):
    gravar = gravacao._gravar_bytes
    for parcial in (False, True):
      with self.subTest(parcial=parcial):
        base = self.base / str(parcial)
        base.mkdir()
        def interromper(caminho, conteudo):
          if parcial:
            gravar(caminho, conteudo[:5])
          raise OSError('Falha sintética na escrita inicial')
        with patch.object(gravacao, '_gravar_bytes', side_effect=interromper):
          with self.assertRaisesRegex(RuntimeError, 'Nenhum documento foi publicado'):
            self.salvar(base)
        self.assertEqual(gravacao.listar_gravacoes(base), [])
        self.assertEqual(list(base.rglob('*')), [])
        self.assertEqual(self.salvar(base), 'SINTETICO 123')
        self.assertEqual(gravacao.listar_gravacoes(base)[0]['estado'], 'concluido')

  def test_falha_ao_publicar_registro_inicial_preserva_preparacao_sem_bloquear(self):
    renomear = Path.rename
    def falhar(origem, destino):
      if '.iniciando' in origem.parts:
        raise OSError('Falha sintética ao publicar registro')
      return renomear(origem, destino)
    with patch.object(Path, 'rename', falhar):
      with self.assertRaisesRegex(RuntimeError, 'Nenhum documento foi publicado'):
        self.salvar()
    self.assertEqual(gravacao.listar_gravacoes(self.base), [])
    self.assertEqual(list(self.base.rglob('*')), [])
    manifestos = list((self.projeto / '.cofre-gravacoes' / '.iniciando').rglob('manifesto.json'))
    self.assertEqual(len(manifestos), 1)
    self.assertEqual(json.loads(manifestos[0].read_text(encoding='utf-8'))['estado'], 'preparando')
    self.assertEqual(self.salvar(), 'SINTETICO 123')

  def test_falha_na_primeira_atualizacao_local_do_legado_nao_oculta_registro_antigo(self):
    identificador, legado = self.registro_legado()
    original = legado.read_bytes()
    gravar = gravacao._gravar_bytes
    def interromper(caminho, conteudo):
      gravar(caminho, conteudo[:5])
      raise OSError('Falha sintética ao preparar registro local do legado')
    with patch.object(gravacao, '_gravar_bytes', side_effect=interromper):
      with self.assertRaises(gravacao.GravacaoPendente):
        gravacao.recuperar_gravacao(self.base, identificador)
    self.assertEqual(legado.read_bytes(), original)
    self.assertFalse(self.manifesto(self.base, identificador).parent.exists())
    self.assertEqual(gravacao.listar_gravacoes(self.base)[0]['estado'], 'pronto')
    self.assertEqual(gravacao.recuperar_gravacao(self.base, identificador), 'SINTETICO 123')
    self.assertEqual(legado.read_bytes(), original)
    self.assertEqual(gravacao.listar_gravacoes(self.base)[0]['estado'], 'concluido')

  def test_falha_inicial_nao_conta_nem_sinaliza_nos_dois_fluxos(self):
    for modo in ('web', 'console'):
      with self.subTest(modo=modo), patch.object(gravacao, '_salvar_registro', side_effect=OSError('Falha inicial sintética')):
        resultado, _, flags, metricas, _ = test_downloads.TestDownloads().executar(modo=modo)
      self.assertEqual(resultado['situacao'], 'Erro')
      self.assertEqual((flags, metricas), (0, 0))
      self.assertIn('Nenhum documento foi publicado', resultado['detalhe'])

  def test_registro_local_corrompido_nao_e_ocultado_pelo_legado(self):
    identificador, legado = self.registro_legado()
    gravacao.recuperar_gravacao(self.base, identificador)
    local = self.manifesto(self.base, identificador)
    local.write_bytes(b'{')
    self.assertEqual(gravacao.listar_gravacoes(self.base)[0]['estado'], 'invalido')
    with self.assertRaises(ValueError):
      self.salvar()
    self.assertTrue(legado.exists())
    self.assertEqual(local.read_bytes(), b'{')

  def test_publica_conjunto_completo_e_copia_cte(self):
    for tipo in TipoDocumento:
      with self.subTest(tipo=tipo):
        self.assertEqual(self.salvar(tipo=tipo), 'SINTETICO 123')
        xml, pdf, _ = self.dados(tipo)
        self.assertEqual([p.read_bytes() for p in self.destinos(tipo=tipo)],
                         [pdf, xml] if tipo == TipoDocumento.NFE else [pdf, xml, xml])
    self.assertTrue(all(r['estado'] == 'concluido' for r in gravacao.listar_gravacoes(self.base)))

  def test_chaves_diferentes_preservam_os_dois_conjuntos(self):
    self.salvar()
    anteriores = {p: p.read_bytes() for p in self.destinos()}
    _, _, chave = self.dados(outra_chave=True)
    nome = self.salvar(outra_chave=True)
    self.assertEqual(nome, f'SINTETICO 123 - {chave}')
    self.assertTrue(all(p.read_bytes() == conteudo for p, conteudo in anteriores.items()))
    xml, pdf, _ = self.dados(outra_chave=True)
    self.assertEqual([p.read_bytes() for p in self.destinos(nome=nome)], [pdf, xml])

  def test_mesma_chave_reaproveita_primeiro_conjunto_valido(self):
    self.salvar()
    anteriores = {p: p.read_bytes() for p in self.destinos()}
    xml, _, chave = self.dados()
    pdf_novo = pdf_fiscal(chave, texto=chave + ' NOVA RENDERIZACAO')
    self.assertEqual(gravacao.gravar_conjunto(xml, pdf_novo, self.contexto, self.base), 'SINTETICO 123')
    self.assertTrue(all(p.read_bytes() == conteudo for p, conteudo in anteriores.items()))
    self.assertEqual(len(gravacao.listar_gravacoes(self.base)), 1)

  def test_falha_em_cada_preparacao_preserva_anterior_e_permite_nova_baixa(self):
    original = gravacao._gravar_bytes
    for tipo in TipoDocumento:
      for papel in (('pdf', 'xml') if tipo == TipoDocumento.NFE else ('pdf', 'xml', 'copia')):
        for depois in (False, True):
          with self.subTest(tipo=tipo, papel=papel, depois=depois):
            base = self.base / f'{tipo}-{papel}-{depois}'
            base.mkdir()
            anteriores = self.anterior(base, tipo)

            def interromper(caminho, conteudo):
              if caminho.name.endswith(f'-{papel}.tmp'):
                if depois:
                  original(caminho, conteudo[:5])
                raise OSError('Falha sintética na preparação')
              original(caminho, conteudo)

            with patch.object(gravacao, '_gravar_bytes', side_effect=interromper):
              with self.assertRaises(gravacao.GravacaoPendente) as captura:
                self.salvar(base, tipo)
            identificador = captura.exception.identificador
            self.assertTrue(all(p.read_bytes() == b'ARQUIVO ANTERIOR' for p in anteriores))
            self.assertEqual(gravacao.listar_gravacoes(base)[0]['estado'], 'preparando')
            with self.assertRaises(gravacao.GravacaoPendente):
              self.salvar(base, tipo)
            gravacao.abandonar_preparacao(base, identificador)
            nome = self.salvar(base, tipo)
            self.assertTrue(all(p.exists() for p in self.destinos(base, tipo, nome)))
            self.assertTrue(all(p.read_bytes() == b'ARQUIVO ANTERIOR' for p in anteriores))

  def test_interrupcoes_antes_e_apos_cada_promocao_sao_recuperaveis(self):
    promover = gravacao._promover
    for tipo in TipoDocumento:
      for indice in range(2 if tipo == TipoDocumento.NFE else 3):
        for depois in (False, True):
          with self.subTest(tipo=tipo, indice=indice, depois=depois):
            base = self.base / f'{tipo}-{indice}-{depois}'
            base.mkdir()
            anteriores = self.anterior(base, tipo)
            chamadas = []

            def interromper(origem, destino):
              atual = len(chamadas)
              chamadas.append(destino)
              if atual == indice and not depois:
                raise OSError('Falha sintética antes da promoção')
              promover(origem, destino)
              if atual == indice and depois:
                raise OSError('Interrupção após publicar o arquivo')

            with patch.object(gravacao, '_promover', side_effect=interromper):
              with self.assertRaises(gravacao.GravacaoPendente) as captura:
                self.salvar(base, tipo)
            identificador = captura.exception.identificador
            self.assertEqual(gravacao.listar_gravacoes(base)[0]['estado'], 'pronto')
            nome = gravacao.recuperar_gravacao(base, identificador)
            xml, pdf, _ = self.dados(tipo)
            self.assertEqual([p.read_bytes() for p in self.destinos(base, tipo, nome)],
                             [pdf, xml] if tipo == TipoDocumento.NFE else [pdf, xml, xml])
            self.assertTrue(all(p.read_bytes() == b'ARQUIVO ANTERIOR' for p in anteriores))
            with patch.object(gravacao, '_promover', side_effect=AssertionError('Não repetir publicação')):
              self.assertEqual(gravacao.recuperar_gravacao(base, identificador), nome)

  def pendencia(self):
    with patch.object(gravacao, '_promover', side_effect=PermissionError('Interrupção sintética')):
      with self.assertRaises(gravacao.GravacaoPendente) as captura:
        self.salvar()
    return captura.exception.identificador

  def test_falha_no_registro_final_nao_anuncia_sucesso_e_recupera(self):
    salvar_registro = gravacao._salvar_registro

    def falhar(pasta, registro):
      if registro['estado'] == 'concluido':
        raise OSError('Falha sintética no recibo')
      salvar_registro(pasta, registro)

    with patch.object(gravacao, '_salvar_registro', side_effect=falhar):
      with self.assertRaises(gravacao.GravacaoPendente) as captura:
        self.salvar()
    identificador = captura.exception.identificador
    self.assertTrue(all(p.exists() for p in self.destinos()))
    self.assertEqual(gravacao.listar_gravacoes(self.base)[0]['estado'], 'pronto')
    with patch.object(gravacao, '_promover', side_effect=AssertionError('Arquivos já publicados')):
      gravacao.recuperar_gravacao(self.base, identificador)
    self.assertEqual(gravacao.listar_gravacoes(self.base)[0]['estado'], 'concluido')

  def test_temporario_alterado_bloqueia_recuperacao_antes_de_publicar(self):
    identificador = self.pendencia()
    temporario = next(self.base.rglob(f'.cofre-{identificador}-xml.tmp'))
    temporario.write_bytes(b'ALTERADO')
    with self.assertRaises(gravacao.GravacaoPendente):
      gravacao.recuperar_gravacao(self.base, identificador)
    self.assertFalse(any(p.exists() for p in self.destinos()))
    self.assertEqual(temporario.read_bytes(), b'ALTERADO')
    gravacao.abandonar_preparacao(self.base, identificador)
    self.assertEqual(self.salvar(), 'SINTETICO 123')
    self.assertEqual(temporario.read_bytes(), b'ALTERADO')

  def test_destino_concorrente_nao_e_sobrescrito(self):
    promover = gravacao._promover
    concorrentes = []

    def concorrer(origem, destino):
      destino.write_bytes(b'ESCRITOR CONCORRENTE')
      concorrentes.append(destino)
      promover(origem, destino)

    with patch.object(gravacao, '_promover', side_effect=concorrer):
      with self.assertRaises(gravacao.GravacaoPendente) as captura:
        self.salvar()
    self.assertEqual(concorrentes[0].read_bytes(), b'ESCRITOR CONCORRENTE')
    with self.assertRaises(gravacao.GravacaoPendente):
      gravacao.recuperar_gravacao(self.base, captura.exception.identificador)
    self.assertEqual(concorrentes[0].read_bytes(), b'ESCRITOR CONCORRENTE')

  def test_registro_adulterado_nao_permite_escapar_da_pasta(self):
    identificador = self.pendencia()
    caminho = self.manifesto(self.base, identificador)
    registro = json.loads(caminho.read_text(encoding='utf-8'))
    registro['contexto']['emitente'] = '../FORA'
    caminho.write_text(json.dumps(registro), encoding='utf-8')
    self.assertEqual(gravacao.listar_gravacoes(self.base)[0]['estado'], 'invalido')
    with self.assertRaises(ValueError):
      gravacao.recuperar_gravacao(self.base, identificador)
    with self.assertRaises(ValueError):
      self.salvar(outra_chave=True)
    with self.assertRaises(ValueError):
      gravacao.recuperar_gravacao(self.base, '../FORA')
    self.assertFalse((self.temporario / 'FORA').exists())

  def test_registro_corrompido_e_identificado_sem_ser_apagado(self):
    identificador = self.pendencia()
    caminho = self.manifesto(self.base, identificador)
    caminho.write_bytes(b'{')
    self.assertEqual(gravacao.listar_gravacoes(self.base)[0]['estado'], 'invalido')
    with self.assertRaises(ValueError):
      gravacao.recuperar_gravacao(self.base, identificador)
    self.assertEqual(caminho.read_bytes(), b'{')

  def test_nao_abandona_conjunto_com_publicacao_iniciada(self):
    promover = gravacao._promover

    def interromper(origem, destino):
      if destino.suffix == '.xml':
        raise OSError('Interrupção sintética após publicar PDF')
      promover(origem, destino)

    with patch.object(gravacao, '_promover', side_effect=interromper):
      with self.assertRaises(gravacao.GravacaoPendente) as captura:
        self.salvar()
    identificador = captura.exception.identificador
    with self.assertRaises(ValueError):
      gravacao.abandonar_preparacao(self.base, identificador)
    self.assertEqual(gravacao.listar_gravacoes(self.base)[0]['estado'], 'pronto')

  def test_falha_no_conjunto_nao_conta_nem_sinaliza_nos_dois_fluxos(self):
    promover = gravacao._promover
    for modo in ('web', 'console'):
      for tipo in TipoDocumento:
        for indice in range(2 if tipo == TipoDocumento.NFE else 3):
          with self.subTest(modo=modo, tipo=tipo, indice=indice):
            chamadas = []

            def interromper(origem, destino):
              atual = len(chamadas)
              chamadas.append(destino)
              if atual == indice:
                raise OSError('Interrupção sintética no conjunto')
              promover(origem, destino)

            with patch.object(gravacao, '_promover', side_effect=interromper):
              resultado, _, flags, metricas, _ = test_downloads.TestDownloads().executar(modo=modo, tipo=tipo)
            self.assertEqual(resultado['situacao'], 'Erro')
            self.assertEqual((flags, metricas), (0, 0))
            self.assertIn('Gravação pendente', resultado['detalhe'])

  def test_cli_lista_sem_modificar_arquivos_e_conclui_sem_portal(self):
    identificador = self.pendencia()
    antes = self.manifesto(self.base, identificador).read_bytes()
    self.assertEqual(recuperar_documentos.main(['--pasta', str(self.base)]), 0)
    self.assertEqual(self.manifesto(self.base, identificador).read_bytes(), antes)
    self.assertEqual(recuperar_documentos.main(['--pasta', str(self.base), '--concluir', identificador]), 0)
    self.assertEqual(recuperar_documentos.main(['--pasta', str(self.base), '--concluir', identificador]), 0)
    self.assertFalse((self.temporario / 'metricas').exists())

  def test_cli_retorna_falha_para_identificador_invalido(self):
    self.assertEqual(recuperar_documentos.main(['--pasta', str(self.base), '--concluir', '../FORA']), 1)


  def test_confere_novamente_todos_os_arquivos_antes_de_concluir(self):
    promover = gravacao._promover

    def alterar_anterior(origem, destino):
      promover(origem, destino)
      if destino.suffix == '.xml':
        self.destinos()[0].write_bytes(b'ALTERADO POR OUTRO ESCRITOR')

    with patch.object(gravacao, '_promover', side_effect=alterar_anterior):
      with self.assertRaises(gravacao.GravacaoPendente):
        self.salvar()
    self.assertEqual(gravacao.listar_gravacoes(self.base)[0]['estado'], 'pronto')

  def test_cli_respeita_reserva_do_cofre_antes_de_recuperar(self):
    identificador = self.pendencia()
    with IntegracaoLocal('cofre-nfe', 'Cofre sintético', False), \
         patch('integracao_hub.informar'), \
         patch('recuperar_documentos.recuperar_gravacao', side_effect=AssertionError('Aplicação reservada')):
      self.assertEqual(recuperar_documentos.main(['--pasta', str(self.base), '--concluir', identificador]), 2)
    self.assertEqual(gravacao.listar_gravacoes(self.base)[0]['estado'], 'pronto')

  def test_cli_abandona_somente_preparacao_e_preserva_temporario(self):
    gravar = gravacao._gravar_bytes

    def interromper(caminho, conteudo):
      if caminho.name.endswith('-pdf.tmp'):
        gravar(caminho, conteudo[:5])
        raise OSError('Falha sintética durante preparação')
      gravar(caminho, conteudo)

    with patch.object(gravacao, '_gravar_bytes', side_effect=interromper):
      with self.assertRaises(gravacao.GravacaoPendente) as captura:
        self.salvar()
    identificador = captura.exception.identificador
    temporario = next(self.base.rglob(f'.cofre-{identificador}-pdf.tmp'))
    self.assertEqual(recuperar_documentos.main(['--pasta', str(self.base), '--abandonar', identificador]), 0)
    self.assertEqual(temporario.read_bytes(), b'%PDF-')
    self.assertEqual(gravacao.listar_gravacoes(self.base)[0]['estado'], 'abandonado')
    self.assertEqual(self.salvar(), 'SINTETICO 123')


if __name__ == '__main__':
  unittest.main()
