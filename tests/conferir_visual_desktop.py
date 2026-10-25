"""Capturas reais do WebView2 da sonda sintética e fechamento WinForms.

Não captura diálogos nativos: suas respostas são simuladas neste ensaio.
Uso: python -m tests.conferir_visual_desktop PASTA_DA_SONDA
"""
import json
from pathlib import Path
import re
import sys
import time
from urllib.request import Request, ProxyHandler, build_opener

from integracao_hub import consultar_instancia, ler_registro
from tests.verificar_pacote_desktop import esperar


def main():
  pasta = Path(sys.argv[1]).resolve()
  contador = int(ler_registro(pasta / 'sonda.json').get('comando') or 0)
  evidencias = {'captura': 'renderer WebView2 da janela desktop real', 'dialogo_nativo': 'respostas simuladas', 'estados': {}}

  def sonda():
    erro = pasta / 'sonda-erro.txt'
    if erro.exists():
      raise RuntimeError(erro.read_text(encoding='utf-8'))
    return ler_registro(pasta / 'sonda.json')

  def comando(acao, **dados):
    nonlocal contador
    contador += 1
    temp = pasta / 'comando.tmp'
    temp.write_text(json.dumps({'id': contador, 'acao': acao, **dados}), encoding='utf-8')
    temp.replace(pasta / 'comando.json')
    esperar(lambda: sonda().get('comando') == contador)

  def capturar(nome):
    time.sleep(.2)
    comando('capturar', nome=nome)
    dados = sonda()
    assert not dados['excesso'] and dados['rolagensInternas'] == 0
    evidencias['estados'][nome] = dados

  if '--reconexao' in sys.argv[2:]:
    comando('falha-inicio-prolongada')
    esperar(lambda: sonda().get('confirmacaoPendente'))
    capturar('reconectando-claro')
    comando('escuro')
    capturar('reconectando-escuro')
    assert all(e['confirmacaoPendente'] and e['inicioBloqueado'] for e in evidencias['estados'].values())
    comando('liberar-conexao')
    esperar(lambda: sonda().get('pergunta') and not sonda().get('confirmacaoPendente'))
    assert sonda()['conexao']['inicios'] == 1
    evidencias['recuperacao_automatica'] = sonda()['conexao']
    comando('fechar')
    esperar(lambda: ler_registro(pasta / 'presenca/cofre-nfe.json').get('estado') == 'encerrado')
    (pasta / 'conferencia.json').write_text(json.dumps(evidencias, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'capturas': len(evidencias['estados']), 'pasta': str(pasta), 'recuperacao': True}, ensure_ascii=False))
    return 0

  if '--lista' in sys.argv[2:]:
    assert sonda()['empresa'] == 'FILIAL' and sonda()['tipo'] == 'nfe' and sonda()['pastaBloqueada']
    comando('tres-resultados')
    capturar('padrao-claro-tres-notas')
    assert sonda()['resultadosAoLado'] and sonda()['linhas'] == 3
    comando('escuro')
    capturar('padrao-escuro-tres-notas')
    comando('configurar-pasta')
    esperar(lambda: sonda().get('configuracaoStatus', '').startswith('Pasta salva'))
    assert 'DESTINO-ESCOLHIDO' in sonda()['pastaBase']
    capturar('configuracoes-escuro')
    comando('claro')
    capturar('configuracoes-claro')
    comando('fechar-configuracoes')

  comando('resultados')
  capturar('padrao-claro-resultados')
  assert sonda()['primeiraLinhaVisivel']
  if '--lista' in sys.argv[2:]:
    assert sonda()['acaoVisivel'] and sonda()['resultadosAoLado']
  comando('escuro')
  capturar('padrao-escuro-resultados')
  comando('compacto')
  capturar('compacto-escuro-resultados')
  comando('ver-resultados')
  capturar('compacto-escuro-resultados-lista')
  comando('claro')
  capturar('compacto-claro-resultados')
  comando('ver-resultados')
  capturar('compacto-claro-resultados-lista')
  comando('padrao')
  comando('emitente')
  esperar(lambda: sonda().get('pergunta'))
  capturar('padrao-claro-emitente')
  comando('escuro')
  capturar('padrao-escuro-emitente')
  comando('compacto')
  comando('ver-decisao')
  capturar('compacto-escuro-emitente')
  comando('claro')
  capturar('compacto-claro-emitente')
  pergunta = sonda()['pergunta']
  comando('nome')
  esperar(lambda: sonda().get('pergunta') not in (None, pergunta))
  comando('editar-nome')
  capturar('compacto-claro-nome')
  comando('escuro')
  capturar('compacto-escuro-nome')
  comando('padrao')
  comando('ver-decisao')
  capturar('padrao-escuro-nome')
  comando('claro')
  capturar('padrao-claro-nome')
  assert sonda()['nome'] == 'DECISAO SINTETICA EM EDICAO'
  registro = ler_registro(pasta / 'presenca/cofre-nfe.json')
  opener = build_opener(ProxyHandler({}))
  with opener.open(registro['url']) as resposta:
    token = re.search(rb'name="cofre-token" content="([^"]+)"', resposta.read()).group(1).decode()
  req = Request(registro['url'] + '/api/parar', data=b'{}', method='POST',
    headers={'Authorization': 'Bearer ' + token, 'Origin': registro['url'], 'Content-Type': 'application/json'})
  with opener.open(req) as resposta:
    resposta.read()
  esperar(lambda: not sonda().get('ativo'))
  comando('gravacao')
  comando('x-cancelar')
  assert sonda()['ativo'] and not consultar_instancia(registro).get('encerrando')
  evidencias['x_cancelado_preserva_worker'] = True
  comando('x-confirmar')
  esperar(lambda: consultar_instancia(registro).get('encerrando'))
  assert sonda()['ativo']
  capturar('encerramento-aguarda-fronteira')
  evidencias['x_confirmado_aguarda_fronteira'] = True
  comando('liberar-gravacao')
  esperar(lambda: ler_registro(pasta / 'presenca/cofre-nfe.json').get('estado') == 'encerrado')
  (pasta / 'conferencia.json').write_text(json.dumps(evidencias, ensure_ascii=False, indent=2), encoding='utf-8')
  print(json.dumps({'capturas': len(evidencias['estados']), 'pasta': str(pasta), 'fechamento_WinForms': True}, ensure_ascii=False))
  return 0


if __name__ == '__main__':
  raise SystemExit(main())
