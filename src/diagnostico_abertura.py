"""Adaptador Cofre do diagnostico_nunes.py; fonte compartilhada no Hub."""
from diagnostico_nunes import detalhes as detalhes_nunes, registrar as registrar_nunes
from src.caminhos import pasta_preferencias, recursos

ARQUIVOS = ('pythonnet/runtime/Python.Runtime.dll', 'clr_loader/ffi/dlls/amd64/ClrLoader.dll',
            'webview/lib/Microsoft.Web.WebView2.Core.dll',
            'webview/lib/Microsoft.Web.WebView2.WinForms.dll', 'src/cofre.html')


def detalhes(erro, etapa):
  return detalhes_nunes(erro, etapa, aplicacao='cofre-nfe', raiz_recursos=recursos(), arquivos=ARQUIVOS)


def registrar(erro, etapa):
  return registrar_nunes(erro, etapa, aplicacao='cofre-nfe', pasta_preferencias=pasta_preferencias(),
                        raiz_recursos=recursos(), arquivos=ARQUIVOS, nome='cofre-diagnostico.txt')
