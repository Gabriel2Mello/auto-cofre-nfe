# Windows x64 onedir. Nenhum catálogo, credencial ou registro operacional no pacote.
from pathlib import Path
import json
import os

raiz = Path(SPECPATH)
metadados = Path(os.environ.get('NUNES_COFRE_BUILD', str(raiz / '.local/cofre-versao.json')))
if not metadados.is_file():
    raise ValueError('Informe NUNES_COFRE_BUILD com versão e commit do build.')
a = Analysis([str(raiz / 'cofre.py')], pathex=[str(raiz)],
             datas=[(str(metadados), '.'), (str(raiz / 'src/cofre.html'), 'src'),
                    (str(raiz / 'src/cofre.css'), 'src'),
                    (str(raiz / 'src/cofre.js'), 'src'),
                    (str(raiz / 'src/nunes-tema.js'), 'src'),
                    (str(raiz / 'desktop-winforms.config'), '.'),
                    (str(raiz / 'icons'), 'icons')],
             hiddenimports=['webview.platforms.edgechromium', 'webview.platforms.winforms',
                            'win32com.propsys.propsys', 'win32com.propsys.pscon', 'win32com.shell.shell'],
             excludes=['PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'cefpython3'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Cofre NFe',
          console=False, icon=str(raiz / 'icons/icone.ico'), uac_admin=False)
coll = COLLECT(exe, a.binaries, a.datas, name='Cofre NFe')
