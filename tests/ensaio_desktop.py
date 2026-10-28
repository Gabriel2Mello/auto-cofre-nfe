"""Sonda opt-in da janela real, apenas em desenvolvimento e com executor sintético.

Uso: python -m tests.ensaio_desktop PASTA_ISOLADA. Não integra o pacote.
Comandos de ensaio em comando.json: resultados, emitente, nome, compacto,
minimizar, claro, escuro, fechar. Observações em sonda.json.
"""
import json
import os
from pathlib import Path
import sys
import time
from threading import Thread, Event


def main():
  pasta = Path(sys.argv[1]).resolve()
  pasta.mkdir(parents=True, exist_ok=True)
  os.environ.update(NUNES_HUB_DADOS=str(pasta / 'presenca'),
                    NUNES_METRICAS_DADOS=str(pasta / 'metricas'),
                    NUNES_COFRE_DADOS=str(pasta / 'dados'),
                    CAMINHO_DOCUMENTO_ENTRADA=str(pasta / 'DOCUMENTOS-SINTETICOS'),
                    NUNES_CENTRAL_CONFIG=str(pasta / 'central-ausente.json'))
  # Bloqueio de conexões externas também protege contra futuros imports acidentais.
  import socket
  conectar = socket.socket.connect

  def somente_local(sock, destino):
    if isinstance(destino, tuple) and destino[0] not in ('127.0.0.1', '::1'):
      raise RuntimeError('Rede externa bloqueada no ensaio sintético.')
    return conectar(sock, destino)

  socket.socket.connect = somente_local
  import webview
  import cofre
  import src.controlador_web as controlador
  original = controlador.EstadoInterface
  estados = []
  aberturas_pasta = []
  # Simula somente a abertura no Explorer; a rota e a configuração continuam reais.
  os.startfile = lambda caminho, operacao: aberturas_pasta.append({'pasta': caminho, 'operacao': operacao})
  liberar_gravacao = Event()

  def simular(pedido, estado):
    estado.perguntar('emitente', opcoes=[{'nome': 'FORNECEDOR SINTÉTICO A', 'data': '01/10/2026', 'valor': '100,00'},
                                        {'nome': 'FORNECEDOR SINTÉTICO B', 'data': '02/10/2026', 'valor': '200,00'}])
    estado.solicitar_nome('FORNECEDOR DE DEMONSTRAÇÃO')
    estado.atualizar_nota(0, 'Concluído', 'SIMULAÇÃO · nenhum arquivo fiscal salvo; portal não acessado.')

  class EstadoSintetico(original):
    def __init__(self):
      super().__init__(simular)
      estados.append(self)

  controlador.EstadoInterface = EstadoSintetico
  criar = webview.create_window

  def observar(*args, **kwargs):
    janela = criar(*args, **kwargs)
    cargas = []

    def carregou():
      cargas.append(True)
      janela.evaluate_js("el('notas').value='123,124';el('competencia').value='2026-10';destino()")

    janela.events.loaded += carregou

    def capturar(nome):
      # Captura o renderer WebView2 da própria janela de ensaio; sem navegador externo.
      from System import Action
      from System.IO import FileStream, FileMode, FileAccess
      from Microsoft.Web.WebView2.Core import CoreWebView2CapturePreviewImageFormat
      destino = pasta / (nome + '.png')
      stream = FileStream(str(destino), FileMode.Create, FileAccess.Write)
      tarefas = []
      try:
        janela.native.Invoke(Action(lambda: tarefas.append(janela.native.webview.CoreWebView2.CapturePreviewAsync(
          CoreWebView2CapturePreviewImageFormat.Png, stream))))
        if not tarefas[0].Wait(10000):
          raise RuntimeError('A captura WebView2 não terminou no prazo.')
      finally:
        stream.Dispose()

    def sonda():
      janela.events.loaded.wait(30)
      ultimo = None
      while not janela.events.closed.is_set():
        try:
          comando = pasta / 'comando.json'
          if comando.exists():
            try:
              pedido = json.loads(comando.read_text(encoding='utf-8'))
            except PermissionError:
              # O controlador substitui esse arquivo atomicamente no Windows.
              # Uma leitura concorrente pode ser recusada por um instante.
              time.sleep(.05)
              continue
            if pedido.get('id') != ultimo:
              ultimo = pedido['id']
              acao = pedido['acao']
              if acao in ('resultados', 'tres-resultados'):
                if acao == 'tres-resultados':
                  janela.evaluate_js("el('notas').value='1000, 1001, 1002'")
                estado = estados[0]
                with estado.condicao:
                  estado.dados.update(status='Execução sintética finalizada. Confira os itens com atenção.',
                    resultados=[{'nota': str(1000 + i),
                      'situacao': ['Concluído', 'Erro', 'Conferir sinalização', 'Não processado'][i % 4],
                      'detalhe': ['SIMULAÇÃO · XML e PDF conferidos.',
                                 'SIMULAÇÃO · Falha ao acessar a pasta. Confira as permissões antes de tentar novamente.',
                                 'SIMULAÇÃO · Arquivos salvos. Confira a sinalização no portal antes de repetir.',
                                 'SIMULAÇÃO · Execução interrompida antes deste documento.'][i % 4]}
                      for i in range(3 if acao == 'tres-resultados' else 80)])
                janela.evaluate_js('atualizar()')
              elif acao == 'emitente':
                janela.evaluate_js("el('notas').value='123';el('mesma-pasta').checked=false;el('pasta').value='2026-11';destino()")
                estados[0].iniciar(dict(notas='123', empresa='FILIAL', tipo='nfe', competencia='2026-10', pasta='2026-11'))
                janela.evaluate_js('atualizar()')
              elif acao == 'gravacao':
                janela.evaluate_js("el('notas').value='123';el('mesma-pasta').checked=false;el('pasta').value='2026-11';destino()")
                def gravar_sintetico(p, e):
                  e.informar('SIMULAÇÃO · Operação em curso. Aguarde a fronteira segura.')
                  liberar_gravacao.wait(90)
                  e.atualizar_nota(0, 'Concluído', 'SIMULAÇÃO · Fronteira segura alcançada, nenhum arquivo fiscal salvo.')
                estados[0].executor = gravar_sintetico
                estados[0].iniciar(dict(notas='123', empresa='FILIAL', tipo='nfe', competencia='2026-10', pasta='2026-11'))
                janela.evaluate_js('atualizar()')
              elif acao == 'liberar-gravacao':
                liberar_gravacao.set()
              elif acao == 'nome':
                p = estados[0].snapshot()['pergunta']
                estados[0].responder({'id': p['id'], 'valor': '1'})
              elif acao == 'editar-nome':
                janela.evaluate_js("el('nome').value='Decisao sintetica em edicao';el('nome').focus()")
              elif acao == 'configurar-pasta':
                destino = pasta / 'DESTINO-ESCOLHIDO'
                destino.mkdir(exist_ok=True)
                janela.create_file_dialog = lambda *a, **kw: (str(destino),)
                janela.evaluate_js("el('configuracoes').open=true;el('escolher-pasta').click()")
              elif acao == 'ver-configuracoes':
                janela.evaluate_js("el('configuracoes').open=true;window.scrollTo(0,0)")
              elif acao == 'abrir-pasta':
                janela.evaluate_js("el('configuracoes').open=true;el('abrir-pasta').click()")
              elif acao == 'fechar-configuracoes':
                janela.evaluate_js("el('configuracoes').open=false")
              elif acao == 'areas-clique':
                janela.evaluate_js("""(() => {
                  const opcao=document.querySelector('.opcao'),check=el('mesma-pasta');
                  const inicial=check.checked,form=document.querySelector('#formulario').getBoundingClientRect();
                  const rect=opcao.getBoundingClientRect(),foco=document.activeElement;
                  const fora=document.elementFromPoint(form.right-2,rect.top+rect.height/2);
                  fora.click();const foraPreservou=check.checked===inicial;
                  check.checked=inicial;destino();
                  opcao.querySelector('span').click();const textoAlternou=check.checked!==inicial;
                  check.click();const checkboxAlternou=check.checked===inicial;
                  check.checked=inicial;destino();el('iniciar').focus();
                  const titulo=el('rotulo-notas'),tituloRect=titulo.getBoundingClientRect();
                  titulo.click();const tituloNaoFocou=document.activeElement!==el('notas');
                  document.elementFromPoint(form.right-2,tituloRect.top+tituloRect.height/2).click();
                  const foraNotasNaoFocou=document.activeElement!==el('notas');
                  el('notas').focus();const campoRecebeFoco=document.activeElement===el('notas');
                  foco?.focus();
                  window.ensaioAreasClique={foraPreservou,textoAlternou,checkboxAlternou,
                    tituloNaoFocou,foraNotasNaoFocou,campoRecebeFoco,
                    nomeAcessivel:el('notas').getAttribute('aria-labelledby')===titulo.id};
                })()""")
              elif acao in ('falha-inicio', 'falha-inicio-prolongada'):
                janela.evaluate_js("""(() => {
                  const original=window.fetch;let falhar=false;
                  window.ensaioManterFalha=__MANTER__;
                  window.ensaioConexao={inicios:0,leituras:0,falhas:0};
                  window.fetch=async(caminho,opcoes)=>{
                    if(caminho==='/api/iniciar'){
                      ensaioConexao.inicios++;const r=await original(caminho,opcoes);falhar=true;return r;
                    }
                    if(caminho==='/api/estado'){
                      ensaioConexao.leituras++;
                      if(falhar||window.ensaioManterFalha){falhar=false;ensaioConexao.falhas++;throw new TypeError('Falha sintética transitória');}
                    }
                    return original(caminho,opcoes);
                  };
                  el('formulario').requestSubmit();
                })()""".replace('__MANTER__', 'true' if acao == 'falha-inicio-prolongada' else 'false'))
              elif acao == 'liberar-conexao':
                janela.evaluate_js('window.ensaioManterFalha=false')
              elif acao == 'compacto':
                janela.resize(780, 600)
              elif acao == 'mover-monitor':
                from System import Action
                from System.Drawing import Point
                from System.Windows.Forms import Screen, FormStartPosition
                def mover():
                  area = Screen.AllScreens[int(pedido['monitor'])].WorkingArea
                  janela.native.StartPosition = FormStartPosition.Manual
                  janela.native.Location = Point(area.X + 32, area.Y + 32)
                janela.native.Invoke(Action(mover))
              elif acao == 'padrao':
                janela.resize(1009, 618)
              elif acao == 'fim-resultados':
                janela.evaluate_js("const painel=document.querySelector('.rolagem-resultados');painel.scrollTop=painel.scrollHeight")
              elif acao == 'minimizar':
                janela.minimize()
              elif acao == 'desconectar':
                janela.evaluate_js('saindo=true;presenca?.abort()')
              elif acao == 'reconectar':
                janela.evaluate_js('saindo=false;acompanhar();atualizar()')
              elif acao == 'ver-resultados':
                janela.evaluate_js("el('titulo-resultados').scrollIntoView({block:'start'})")
              elif acao == 'ver-decisao':
                janela.evaluate_js("el('titulo-decisao').scrollIntoView({block:'start'})")
              elif acao in ('claro', 'escuro'):
                janela.evaluate_js("tema.aplicar('" + acao + "');api('/api/tema',{tema:'" + acao + "'})")
              elif acao == 'alternar-tema':
                janela.evaluate_js("el('tema').click()")
              elif acao == 'fechar':
                estados[0].encerrar()
              elif acao == 'capturar':
                nome = pedido.get('nome', 'captura')
                if not nome.replace('-', '').isalnum():
                  raise ValueError('Nome inválido para captura sintética.')
                capturar(nome)
              elif acao in ('x-cancelar', 'x-confirmar'):
                # Exercita o fechamento real do WinForms, simulando somente a resposta
                # ao diálogo. Não automatiza janelas externas nem muda código de produção.
                janela.create_confirmation_dialog = lambda *a: acao == 'x-confirmar'
                janela.destroy()
          dados = janela.evaluate_js("""({notas:el('notas').value,nome:el('nome').value,
            tema:document.documentElement.dataset.tema,linhas:el('linhas').children.length,
            iconeTema:getComputedStyle(el('tema'),'::before').maskImage,
            rotuloTema:el('tema').getAttribute('aria-label'),
            temaAoLado:!el('configuracoes').contains(el('tema'))&&Math.abs(el('tema').getBoundingClientRect().top-el('configuracoes').getBoundingClientRect().top)<1,
            pergunta:estado?.pergunta?.id,largura:innerWidth,altura:innerHeight,
            empresa:selecionado('empresa'),tipo:selecionado('tipo'),
            pastaBase:el('pasta-base').textContent,pastaBloqueada:el('pasta').disabled,
            camposBloqueados:el('notas').matches(':disabled'),
            configurando:estado?.configurando,configuracaoStatus:el('configuracao-status').textContent,
            abrirAoLado:el('abrir-pasta').getBoundingClientRect().left>=el('escolher-pasta').getBoundingClientRect().right&&Math.abs(el('abrir-pasta').getBoundingClientRect().top-el('escolher-pasta').getBoundingClientRect().top)<1,
            resultadosAoLado:document.querySelector('.resultados').getBoundingClientRect().left>document.querySelector('.parametros').getBoundingClientRect().right,
            parametrosAntesNotas:document.querySelector('.parametros').getBoundingClientRect().bottom<=document.querySelector('.documentos').getBoundingClientRect().top,
            acaoAbaixoNotas:el('iniciar').getBoundingClientRect().top>=el('notas').getBoundingClientRect().bottom,
            acaoADireita:Math.abs(el('iniciar').getBoundingClientRect().right-el('notas').getBoundingClientRect().right)<1,
            rodapeAposConteudo:document.querySelector('.rodape').getBoundingClientRect().top>=document.querySelector('main').getBoundingClientRect().bottom,
            rodapeNoFim:Math.abs(document.querySelector('.rodape').getBoundingClientRect().bottom-innerHeight)<1,
            acaoVisivel:el('iniciar').getBoundingClientRect().top>=0&&el('iniciar').getBoundingClientRect().bottom<=innerHeight,
            excesso:document.documentElement.scrollWidth>innerWidth,
            ativo:estado?.ativo,confirmacaoPendente,inicioBloqueado:el('iniciar').disabled,
            conexao:window.ensaioConexao,
            areasClique:window.ensaioAreasClique,
            primeiraLinhaVisivel:el('linhas').firstElementChild?.getBoundingClientRect().bottom<=innerHeight,
            paginaRola:document.documentElement.scrollHeight>innerHeight,
            resultadosRolam:document.querySelector('.rolagem-resultados').scrollHeight>document.querySelector('.rolagem-resultados').clientHeight,
            fimResultadosVisivel:el('linhas').lastElementChild?.getBoundingClientRect().bottom<=document.querySelector('.rolagem-resultados').getBoundingClientRect().bottom+1,
            tituloVisivel:el('titulo-resultados').getBoundingClientRect().top>=0,
            apelidoMaiusculo:getComputedStyle(el('nome')).textTransform==='uppercase',
            rolagensInternas:[...document.querySelectorAll('main *')].filter(n=>
              ['auto','scroll'].includes(getComputedStyle(n).overflowY)&&n.scrollHeight>n.clientHeight).length})""")
          if dados is None and (janela.events.closed.is_set() or estados[0].encerrando):
            return  # O renderer já pode ter sido liberado no fechamento cooperativo.
          dados['carregamentos'] = len(cargas)
          dados['aberturasPasta'] = list(aberturas_pasta)
          dados['hwnd'] = janela.native.Handle.ToInt64()
          dados['janela'] = {'x': janela.x, 'y': janela.y, 'largura': janela.width, 'altura': janela.height}
          dados['estado_janela'] = str(janela.native.WindowState)
          import ctypes
          from ctypes import wintypes
          from System import Action
          from System.Windows.Forms import Screen
          user = ctypes.WinDLL('user32', use_last_error=True)
          user.GetDpiForWindow.argtypes = [wintypes.HWND]
          user.GetDpiForWindow.restype = wintypes.UINT
          user.GetWindowDpiAwarenessContext.argtypes = [wintypes.HWND]
          user.GetWindowDpiAwarenessContext.restype = ctypes.c_void_p
          user.AreDpiAwarenessContextsEqual.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
          user.AreDpiAwarenessContextsEqual.restype = wintypes.BOOL
          dados['dpi'] = user.GetDpiForWindow(dados['hwnd'])
          dados['perMonitorV2'] = bool(user.AreDpiAwarenessContextsEqual(
            user.GetWindowDpiAwarenessContext(dados['hwnd']), -4))
          def observar_dpi():
            dados['dpiWinForms'] = janela.native.DeviceDpi
            dados['pixelsJanela'] = {'largura': janela.native.Width, 'altura': janela.native.Height}
            dados['zoomWebView'] = janela.native.webview.ZoomFactor
            dados['monitor'] = Screen.FromControl(janela.native).DeviceName
            dados['monitores'] = [s.DeviceName for s in Screen.AllScreens]
          janela.native.Invoke(Action(observar_dpi))
          dados['webDpi'] = janela.evaluate_js('({dpr:devicePixelRatio,largura:innerWidth,altura:innerHeight})')
          dados['janelaFixa'] = str(janela.native.FormBorderStyle) == 'FixedSingle' and not janela.native.MaximizeBox
          dados['status'] = janela.evaluate_js("el('status').textContent")
          dados['comando'] = ultimo
          temp = pasta / 'sonda.tmp'
          temp.write_text(json.dumps(dados), encoding='utf-8')
          temp.replace(pasta / 'sonda.json')
        except PermissionError:
          # O leitor pode manter o snapshot aberto durante sua substituição.
          # A publicação é repetida sem repetir o comando, identificado por ultimo.
          time.sleep(.05)
          continue
        except Exception as erro:
          (pasta / 'sonda-erro.txt').write_text(str(erro), encoding='utf-8')
          return
        time.sleep(.25)

    Thread(target=sonda, daemon=True).start()
    return janela

  webview.create_window = observar
  cofre.main = lambda publicacao: cofre.executar_painel(publicacao)
  sys.argv = ['cofre.py']
  return cofre.iniciar()


if __name__ == '__main__':
  raise SystemExit(main())
