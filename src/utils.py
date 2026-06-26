import ctypes
from datetime import datetime
from typing import Any
from pathlib import Path
import re
import sys

from src.config import (
  Config,
  MONTHS
)


def encerrar_programa(value: Any) -> None:
  if not value:
    sys.exit(0)


def obter_caminho_json() -> Path:
  if hasattr(sys, 'frozen'):
    diretorio_execucao = Path(sys.executable).parent
  else:
    diretorio_execucao = Path(__file__).parent.parent

  return diretorio_execucao / 'emitentes_conhecidos.json'


def salvar_arquivos(
  xml: bytes,
  pdf: bytes,
  nome_emitente: str,
  numero_nota: str,
  empresa: str,
  mes: int,
  tipo: str
) -> None:
  hoje = datetime.today()
  ano_pasta = hoje.year - 1 if (hoje.month == 1 and mes == 12) else hoje.year
  ano = str(ano_pasta)

  nome_arquivo = f'{nome_emitente} {numero_nota}'
  nome_limpo = re.sub(r'[\\/*?:"<>|]', '', nome_arquivo)

  base_path = Path(Config.CAMINHO_DOCUMENTO_ENTRADA)
  if not base_path.exists():
    raise RuntimeError('CAMINHO_DOCUMENTO_ENTRADA não configurado.')

  tipo_caminho = 'NF-e' if tipo == 'nfe' else 'CT-e'
 
  path_pdf = base_path / f'PDF {tipo_caminho}' / ano / empresa / MONTHS[mes]
  path_xml = base_path / f'XML - {tipo_caminho}' / ano / empresa / MONTHS[mes]

  if not path_pdf.exists():
    raise RuntimeError('Caminho da pasta PDF não existe')

  if not path_xml.exists():
    raise RuntimeError('Caminho da pasta XML não existe')

  (path_pdf / f'{nome_limpo}.pdf').write_bytes(pdf)
  (path_xml / f'{nome_limpo}.xml').write_bytes(xml)


def set_app_id() -> None:
  try:
    my_app_id = 'g2mello.autocofre.versao1'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(my_app_id)
  except Exception:
    pass

def upper_strip(value: str | None) -> str | None:
  if not value:
    return

  return value.upper().strip()

