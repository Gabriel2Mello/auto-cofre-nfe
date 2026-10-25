"""Smoke opt-in: pacotes copiados, Hub isolado e nenhuma operação fiscal.

Executar com o Python da Cofre: python -m tests.verificar_pacote_desktop.
Não usa nenhum catálogo ou configuração operacional. Não integra o pacote.
"""
import json
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, ProxyHandler, build_opener

from integracao_hub import ler_registro, consultar_instancia, solicitar_encerramento

RAIZ = Path(__file__).resolve().parents[1]


def esperar(funcao, limite=40):
  fim = time.monotonic() + limite
  while time.monotonic() < fim:
    valor = funcao()
    if valor:
      return valor
    time.sleep(.1)
  raise RuntimeError('O ensaio não confirmou a condição no prazo.')


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--cofre', type=Path, default=RAIZ / 'dist/Cofre NFe/Cofre NFe.exe')
  parser.add_argument('--hub', type=Path)
  parser.add_argument('--hub-desktop', action='store_true', help='Também abre a janela WebView2 do Hub de ensaio.')
  parser.add_argument('--base', type=Path, help='Pasta existente para o ensaio, em vez de TEMP.')
  parser.add_argument('--evidencias', type=Path, default=RAIZ / '.local/qa-desktop')
  args = parser.parse_args()
  evidencias = args.evidencias.resolve()
  evidencias.mkdir(parents=True, exist_ok=True)
  resultado = {'operacao_fiscal': False}
  # Pasta deliberadamente fora da árvore de desenvolvimento e cwd separado.
  pasta = Path(tempfile.mkdtemp(prefix='cofre-desktop-pacote-', dir=args.base))
  print(f'Ensaio isolado: {pasta}', flush=True)
  instalacao = pasta / 'instalacao'
  shutil.copytree(args.cofre.resolve().parent, instalacao)
  exe = instalacao / 'Cofre NFe.exe'
  dados = pasta / 'dados'
  dados.mkdir()
  destino_persistido = pasta / 'DESTINO-PERSISTIDO'
  destino_persistido.mkdir()
  (dados / 'desktop-configuracao.json').write_text(json.dumps({'formato': 1, 'pasta_documentos': str(destino_persistido)}), encoding='utf-8')
  (dados / 'desktop-tema.json').write_text('{"tema":"escuro"}', encoding='utf-8')
  (dados / 'desktop-janela.json').write_text(json.dumps({'formato': 1, 'retangulo': [70, 80, 920, 700], 'maximizada': False}), encoding='utf-8')
  ambiente = dict(os.environ, NUNES_HUB_DADOS=str(pasta / 'presenca'), NUNES_COFRE_DADOS=str(dados),
                  NUNES_METRICAS_DADOS=str(pasta / 'metricas'), NUNES_CENTRAL_CONFIG=str(pasta / 'central-ausente.json'),
                  CAMINHO_DOCUMENTO_ENTRADA=str(pasta / 'documentos-sinteticos'))
  for chave in ('SENHA_COFRE', 'CNPJ_MATRIZ', 'CNPJ_FILIAL'):
    ambiente.pop(chave, None)
  registro = pasta / 'presenca/cofre-nfe.json'
  config = pasta / 'aplicacoes.json'
  config.write_text(json.dumps([{'id': 'cofre-nfe', 'nome': 'Cofre NF-e', 'categoria': 'Fiscal', 'descricao': 'SINTÉTICO',
    'cor': '#166534', 'icone': 'cofre.svg', 'sisplan': False, 'modo': 'desktop', 'pasta': str(instalacao),
    'entrada': 'Cofre NFe.exe', 'ambientes': []}]), encoding='utf-8')
  hub_raiz = RAIZ.parent / 'nunes-hub'
  hub_log = (evidencias / 'pacote-hub.log').open('w', encoding='utf-8')
  if args.hub:
    hub_instalacao = pasta / 'hub-instalacao'
    shutil.copytree(args.hub.resolve().parent, hub_instalacao)
    # Abertura normal do pacote: catálogo externo ao lado do exe e presença
    # pelo override já isolado. Repetir caminhos longos em --dados/--config
    # excedia o limite do comando de reabertura aceito pelo Shell do Windows.
    shutil.copyfile(config, hub_instalacao / 'aplicacoes.json')
    comando_hub = [str(hub_instalacao / args.hub.name)]
    opcoes_catalogo = []
  else:
    comando_hub = [str(hub_raiz / '.venv/Scripts/python.exe'), str(hub_raiz / 'hub.py')]
    opcoes_catalogo = ['--dados', str(pasta / 'presenca'), '--config', str(config)]
  opcoes_hub = [] if args.hub_desktop else ['--sem-navegador']
  hub_proc = subprocess.Popen([*comando_hub, *opcoes_hub, *opcoes_catalogo],
                             cwd=pasta, env=ambiente, stdout=hub_log, stderr=hub_log,
                             creationflags=subprocess.CREATE_NO_WINDOW)
  atual = None

  def saude(caminho):
    r = ler_registro(caminho)
    return r if consultar_instancia(r).get('respondendo') else None

  try:
    registro_hub = esperar(lambda: saude(pasta / 'presenca/nunes-hub.json'))
    if args.hub_desktop:
      esperar(lambda: consultar_instancia(registro_hub).get('paginas', 0) > 0)
    resultado['janela_real_hub'] = args.hub_desktop
    opener = build_opener(ProxyHandler({}))
    with opener.open(registro_hub['url']) as resposta:
      html = resposta.read().decode()
    token = re.search(r'name="hub-token" content="([^"]+)"', html).group(1)

    def pedido(rota, dados):
      req = Request(registro_hub['url'] + rota, data=json.dumps(dados).encode(), method='POST',
        headers={'X-Hub-Token': token, 'Content-Type': 'application/json', 'Origin': registro_hub['url']})
      with opener.open(req, timeout=5) as resposta:
        return json.load(resposta)

    pedido('/api/abrir', {'id': 'cofre-nfe', 'abertura': 'smoke-pacote'})
    atual = esperar(lambda: saude(registro))
    esperar(lambda: consultar_instancia(atual).get('paginas', 0) > 0)
    with opener.open(atual['url']) as resposta:
      pagina = resposta.read()
    assert b'data-tema="escuro"' in pagina
    assert b'name="cofre-desktop" content="1"' in pagina
    assert b'DESTINO-PERSISTIDO' in pagina
    assert re.search(rb'name="empresa" value="FILIAL" checked', pagina)
    resultado['pasta_persistida_no_pacote_e_filial_padrao'] = True
    pedido('/api/mostrar-ferramenta', {'id': 'cofre-nfe'})
    resultado['abertura_e_ativacao_pelo_hub'] = True
    resultado['hub_empacotado'] = bool(args.hub)
    segundo = subprocess.run([str(exe)], cwd=pasta, env=ambiente, capture_output=True, timeout=25,
                             creationflags=subprocess.CREATE_NO_WINDOW)
    assert segundo.returncode == 0, segundo.stderr
    assert saude(registro)['instancia'] == atual['instancia']
    resultado['segunda_abertura_mesma_instancia'] = True
    pedido('/api/encerrar', {})
    assert hub_proc.wait(15) == 0
    assert consultar_instancia(atual)['respondendo']
    resultado['cofre_independente_do_hub_encerrado'] = True
    solicitar_encerramento(atual)
    esperar(lambda: ler_registro(registro).get('estado') == 'encerrado')
    geometria = json.loads((dados / 'desktop-janela.json').read_text(encoding='utf-8'))
    assert geometria['formato'] == 1 and geometria['retangulo'][2] > 0
    resultado.update(pasta_ensaio=str(pasta), pacote=str(exe), tema_persistido=True,
                     geometria_salva=geometria, encerramento_cooperativo=True)
    (evidencias / 'pacote.json').write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(resultado, ensure_ascii=False))
    return 0
  finally:
    if atual and consultar_instancia(atual).get('respondendo'):
      solicitar_encerramento(atual)
    if hub_proc.poll() is None:
      hub_atual = saude(pasta / 'presenca/nunes-hub.json')
      if hub_atual:
        solicitar_encerramento(hub_atual)
      hub_proc.wait(15)
    hub_log.close()


if __name__ == '__main__':
  raise SystemExit(main())
