"""Ensaio opt-in do ciclo real com sonda sintética, sem automação fiscal."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, ProxyHandler, build_opener

from integracao_hub import consultar_instancia, ler_registro, solicitar_encerramento
from tests.verificar_pacote_desktop import esperar

RAIZ = Path(__file__).resolve().parents[1]


def main():
  pasta = Path(tempfile.mkdtemp(prefix='cofre-janela-sintetica-'))
  ambiente = dict(os.environ, NUNES_HUB_DADOS=str(pasta / 'presenca'), NUNES_COFRE_DADOS=str(pasta / 'dados'),
                  NUNES_METRICAS_DADOS=str(pasta / 'metricas'), NUNES_CENTRAL_CONFIG=str(pasta / 'ausente.json'))
  log = (pasta / 'processo.log').open('w', encoding='utf-8')
  processo = subprocess.Popen([sys.executable, '-m', 'tests.ensaio_desktop', str(pasta)], cwd=RAIZ, env=ambiente,
                              stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
  caminho = pasta / 'presenca/cofre-nfe.json'
  resultado = {'pasta_ensaio': str(pasta), 'operacao_fiscal': False}
  contador = 0

  def sonda():
    return ler_registro(pasta / 'sonda.json')

  def comando(acao, **dados):
    nonlocal contador
    contador += 1
    temp = pasta / 'comando.tmp'
    temp.write_text(json.dumps({'id': contador, 'acao': acao, **dados}), encoding='utf-8')
    temp.replace(pasta / 'comando.json')
    esperar(lambda: sonda().get('comando') == contador)

  def reabrir():
    r = subprocess.run([sys.executable, str(RAIZ / 'cofre.py')], cwd=pasta, env=ambiente,
      capture_output=True, timeout=25, creationflags=subprocess.CREATE_NO_WINDOW)
    assert r.returncode == 0, r.stderr

  atual = None
  try:
    esperar(lambda: sonda().get('carregamentos') == 1)
    atual = ler_registro(caminho)
    assert consultar_instancia(atual)['respondendo']
    assert sonda()['empresa'] == 'FILIAL' and sonda()['tipo'] == 'nfe' and sonda()['pastaBloqueada']
    assert sonda()['parametrosAntesNotas'] and sonda()['acaoAbaixoNotas'] and sonda()['acaoADireita']
    assert sonda()['rodapeNoFim'] and sonda()['rodapeAposConteudo']
    comando('escuro')
    comando('capturar', nome='layout-inicial')
    resultado['parametros_notas_acao_e_rodape_conforme_referencia'] = True
    comando('configurar-pasta')
    esperar(lambda: sonda().get('configuracaoStatus', '').startswith('Pasta salva'))
    pasta_escolhida = sonda()['pastaBase']
    assert pasta_escolhida == str(pasta / 'DESTINO-ESCOLHIDO')
    comando('fechar-configuracoes')
    resultado['escolha_da_pasta_pelo_fluxo_http_com_dialogo_simulado'] = True
    comando('falha-inicio')
    esperar(lambda: sonda().get('pergunta') and not sonda().get('confirmacaoPendente'))
    conexao = sonda()['conexao']
    assert conexao['inicios'] == 1 and conexao['falhas'] == 1 and conexao['leituras'] >= 2
    assert sonda()['ativo'] and sonda()['inicioBloqueado'] and sonda()['camposBloqueados']
    resultado['recuperacao_automatica_sem_reenvio'] = conexao
    # Concluir a simulação antes de preparar a tabela extensa.
    comando('nome')
    esperar(lambda: sonda().get('nome'))
    with build_opener(ProxyHandler({})).open(atual['url']) as resposta:
      token_inicial = re.search(rb'name="cofre-token" content="([^"]+)"', resposta.read()).group(1).decode()
    req = Request(atual['url'] + '/api/parar', data=b'{}', method='POST',
      headers={'Authorization': 'Bearer ' + token_inicial, 'Origin': atual['url'], 'Content-Type': 'application/json'})
    with build_opener(ProxyHandler({})).open(req) as resposta:
      resposta.read()
    esperar(lambda: not sonda().get('ativo'))
    comando('resultados')
    esperar(lambda: sonda().get('linhas') == 80)
    assert sonda()['primeiraLinhaVisivel'] and sonda()['acaoVisivel'] and sonda()['resultadosAoLado'] and sonda()['rolagensInternas'] == 0
    assert sonda()['rodapeAposConteudo']
    resultado['primeiras_linhas_no_tamanho_padrao_sem_scroll_interno'] = True
    comando('escuro')
    comando('compacto')
    esperar(lambda: sonda().get('largura', 1000) < 800)
    assert not sonda()['excesso']
    assert sonda()['parametrosAntesNotas'] and sonda()['acaoAbaixoNotas'] and sonda()['acaoADireita']
    assert sonda()['rodapeAposConteudo']
    comando('capturar', nome='layout-compacto')
    comando('minimizar')
    esperar(lambda: sonda().get('estado_janela') == 'Minimized')
    reabrir()
    esperar(lambda: sonda().get('estado_janela') != 'Minimized')
    assert sonda()['carregamentos'] == 1 and sonda()['notas'] == '123,124' and sonda()['linhas'] == 80
    resultado['segunda_abertura_campos_resultados_minimizacao'] = True
    comando('desconectar')
    esperar(lambda: consultar_instancia(atual).get('paginas') == 0)
    time.sleep(5)
    assert consultar_instancia(atual)['respondendo'] and not consultar_instancia(atual).get('encerrando')
    resultado['queda_presenca_sem_encerramento'] = True
    comando('reconectar')
    comando('emitente')
    esperar(lambda: sonda().get('pergunta'))
    pergunta = sonda()['pergunta']
    reabrir()
    assert sonda()['pergunta'] == pergunta and sonda()['carregamentos'] == 1
    comando('nome')
    esperar(lambda: sonda().get('pergunta') not in (None, pergunta))
    comando('editar-nome')
    reabrir()
    assert sonda()['nome'] == 'DECISAO SINTETICA EM EDICAO' and sonda()['carregamentos'] == 1
    resultado['decisoes_emitente_nome_preservadas'] = True
    opener = build_opener(ProxyHandler({}))
    with opener.open(atual['url']) as resposta:
      token = re.search(rb'name="cofre-token" content="([^"]+)"', resposta.read()).group(1).decode()

    def api(rota):
      req = Request(atual['url'] + rota, data=b'{}', method='POST',
        headers={'Authorization': 'Bearer ' + token, 'Origin': atual['url'], 'Content-Type': 'application/json'})
      with opener.open(req) as resposta:
        return json.load(resposta)

    api('/api/parar')
    esperar(lambda: not sonda().get('pergunta'))
    comando('gravacao')
    solicitar_encerramento(atual)
    esperar(lambda: consultar_instancia(atual).get('encerrando'))
    time.sleep(1)
    assert processo.poll() is None
    assert 'Encerrando' in sonda()['status']
    comando('liberar-gravacao')
    assert processo.wait(20) == 0
    resultado['parada_aguarda_fronteira_segura'] = True
    geometria = json.loads((pasta / 'dados/desktop-janela.json').read_text(encoding='utf-8'))
    assert geometria['retangulo'][2] > 0
    assert json.loads((pasta / 'dados/desktop-tema.json').read_text(encoding='utf-8'))['tema'] == 'escuro'
    resultado['tema_geometria_salvos'] = True
    # Reabrir o processo comprova persistência fora da memória da janela.
    (pasta / 'comando.json').rename(pasta / 'comando-primeira-abertura.json')
    (pasta / 'sonda.json').rename(pasta / 'sonda-primeira-abertura.json')
    contador = 0
    processo = subprocess.Popen([sys.executable, '-m', 'tests.ensaio_desktop', str(pasta)], cwd=RAIZ, env=ambiente,
                                stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
    esperar(lambda: sonda().get('carregamentos') == 1)
    atual = ler_registro(caminho)
    assert sonda()['pastaBase'] == pasta_escolhida and sonda()['empresa'] == 'FILIAL'
    resultado['pasta_persistida_apos_reiniciar_processo'] = True
    solicitar_encerramento(atual)
    assert processo.wait(20) == 0
    alvo = RAIZ / '.local/qa-desktop/janela.json'
    alvo.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(resultado, ensure_ascii=False))
    return 0
  finally:
    if atual and consultar_instancia(atual).get('respondendo'):
      solicitar_encerramento(atual)
      (pasta / 'comando.json').write_text(json.dumps({'id': contador + 1, 'acao': 'liberar-gravacao'}), encoding='utf-8')
      processo.wait(20)
    log.close()


if __name__ == '__main__':
  raise SystemExit(main())
