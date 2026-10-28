"""Opt-in: troca real de monitor no Cofre com executor e dados sintéticos.

Uso: python -m tests.verificar_dpi_desktop. Não altera escala dos monitores.
Capturas e evidências ficam em .local/qa-desktop/dpi.json e na pasta TEMP informada.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from integracao_hub import consultar_instancia, ler_registro, solicitar_encerramento
from tests.verificar_pacote_desktop import esperar

RAIZ = Path(__file__).resolve().parents[1]


def main():
  pasta = Path(tempfile.mkdtemp(prefix='cofre-dpi-sintetico-'))
  print(f'Ensaio DPI isolado: {pasta}', flush=True)
  ambiente = dict(os.environ, NUNES_HUB_DADOS=str(pasta / 'presenca'),
    NUNES_COFRE_DADOS=str(pasta / 'dados'), NUNES_METRICAS_DADOS=str(pasta / 'metricas'),
    NUNES_CENTRAL_CONFIG=str(pasta / 'central-ausente.json'))
  contador = 0
  processo = None
  amostras = []
  caminho = pasta / 'presenca/cofre-nfe.json'
  resultado = {'pasta_ensaio': str(pasta), 'operacao_fiscal': False}

  def sonda():
    erro = pasta / 'sonda-erro.txt'
    if erro.exists():
      raise RuntimeError(erro.read_text(encoding='utf-8'))
    dados = ler_registro(pasta / 'sonda.json')
    if processo.poll() is not None and not dados:
      raise RuntimeError('A janela encerrou antes da sonda; consulte processo.log.')
    return dados

  def comando(acao, **dados):
    nonlocal contador
    contador += 1
    temp = pasta / 'comando.tmp'
    temp.write_text(json.dumps({'id': contador, 'acao': acao, **dados}), encoding='utf-8')
    temp.replace(pasta / 'comando.json')
    esperar(lambda: sonda().get('comando') == contador)

  def iniciar(log):
    return subprocess.Popen([sys.executable, '-m', 'tests.ensaio_desktop', str(pasta)],
      cwd=RAIZ, env=ambiente, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)

  def conferir(nome, inicial):
    dados = sonda()
    assert dados['perMonitorV2'] and dados['dpi'] == dados['dpiWinForms'], dados
    assert dados['janelaFixa'] and not dados['excesso'], dados
    escala = dados['dpi'] / 96
    assert abs(dados['pixelsJanela']['largura'] / escala - 1009) <= 2, dados
    assert abs(dados['pixelsJanela']['altura'] / escala - 618) <= 2, dados
    assert abs(dados['webDpi']['largura'] - inicial['webDpi']['largura']) <= 2, dados
    assert abs(dados['webDpi']['dpr'] / escala - inicial['webDpi']['dpr'] / (inicial['dpi'] / 96)) < .01, dados
    assert dados['notas'] == inicial['notas'] and dados['carregamentos'] == 1, dados
    amostras.append(dict(cenario=nome, **dados))
    print(f"{nome}: DPI {dados['dpi']}; DPR {dados['webDpi']['dpr']:.3f}; "
          f"janela {dados['pixelsJanela']['largura']}x{dados['pixelsJanela']['altura']}", flush=True)

  with (pasta / 'processo.log').open('w', encoding='utf-8') as log:
    try:
      processo = iniciar(log)
      esperar(lambda: sonda().get('carregamentos') == 1)
      inicial = sonda()
      conferir('abertura', inicial)
      for tema in ('claro', 'escuro'):
        comando(tema)
        for indice, monitor in enumerate(inicial['monitores']):
          comando('mover-monitor', monitor=indice)
          esperar(lambda: sonda().get('monitor') == monitor)
          # O renderer recebe a mudança depois do HWND e do evento WinForms.
          esperar(lambda: abs(sonda()['webDpi']['dpr'] / (sonda()['dpi'] / 96)
            - inicial['webDpi']['dpr'] / (inicial['dpi'] / 96)) < .01)
          conferir(f'{tema}-monitor-{indice}', inicial)
          comando('capturar', nome=f'dpi-{tema}-monitor-{indice}')

      comando('emitente')
      esperar(lambda: sonda().get('pergunta'))
      pergunta = sonda()['pergunta']
      comando('nome')
      esperar(lambda: sonda().get('pergunta') not in (None, pergunta))
      comando('editar-nome')
      pergunta = sonda()['pergunta']
      for indice in list(range(len(inicial['monitores']))) * 2:
        comando('mover-monitor', monitor=indice)
        dados = sonda()
        assert dados['pergunta'] == pergunta and dados['nome'] == 'Decisao sintetica em edicao', dados
        assert dados['ativo'] and dados['carregamentos'] == 1 and dados['notas'] == '123', dados
      resultado['decisao_e_edicao_preservadas'] = True
      ultimo_monitor = sonda()['monitor']
      solicitar_encerramento(ler_registro(caminho))
      assert processo.wait(25) == 0
      resultado['encerramento_cooperativo'] = True
      (pasta / 'comando.json').rename(pasta / 'comando-primeira-abertura.json')
      (pasta / 'sonda.json').rename(pasta / 'sonda-primeira-abertura.json')
      contador = 0
      processo = iniciar(log)
      esperar(lambda: sonda().get('carregamentos') == 1)
      conferir('reabertura', inicial)
      assert sonda()['monitor'] == ultimo_monitor, sonda()
      resultado['monitor_restaurado'] = ultimo_monitor
      solicitar_encerramento(ler_registro(caminho))
      assert processo.wait(25) == 0
      dpis = sorted({d['dpi'] for d in amostras})
      resultado.update(dpis=dpis, escalas_distintas_validadas=len(dpis) > 1, amostras=amostras)
      alvo = RAIZ / '.local/qa-desktop/dpi.json'
      alvo.parent.mkdir(parents=True, exist_ok=True)
      alvo.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding='utf-8')
      print(json.dumps({'dpis': dpis, 'amostras': len(amostras), 'evidencias': str(alvo)}, ensure_ascii=False), flush=True)
      return 0
    finally:
      if processo and processo.poll() is None:
        registro = ler_registro(caminho)
        if consultar_instancia(registro).get('respondendo'):
          solicitar_encerramento(registro)
        processo.wait(25)


if __name__ == '__main__':
  raise SystemExit(main())
