import ctypes
from datetime import datetime
from typing import Any, Union
from pathlib import Path
import sys
from time import sleep

from unidecode import unidecode

from src.config import Config


def pause() -> None:
  try:
    input('\nPressione Enter para fechar...')
  except (EOFError, KeyboardInterrupt):
    pass


def encerrar_programa(value: Any) -> None:
  if not value:
    print('\nNenhum valor informado...')
    pause()
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
  ano_pasta = ano_referencia(mes)
  ano = str(ano_pasta)

  nome_limpo = f'{nome_emitente} {numero_nota}'

  base_path = Path(Config.CAMINHO_DOCUMENTO_ENTRADA)
  if not base_path.exists():
    raise RuntimeError('CAMINHO_DOCUMENTO_ENTRADA não configurado.')

  tipo_prefix = 'NF-e' if tipo == 'nfe' else 'CT-e'
 
  path_pdf = base_path / f'PDF {tipo_prefix}' / ano / empresa / Config.MONTHS[mes]
  path_xml = base_path / f'XML - {tipo_prefix}' / ano / empresa / Config.MONTHS[mes]

  path_pdf.mkdir(parents=True, exist_ok=True)
  path_xml.mkdir(parents=True, exist_ok=True)

  (path_pdf / f'{nome_limpo}.pdf').write_bytes(pdf)
  (path_xml / f'{nome_limpo}.xml').write_bytes(xml)


def set_app_id() -> None:
  try:
    my_app_id = 'g2mello.autocofre.versao1'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(my_app_id)
  except Exception:
    pass

def upper_strip(value: str | None) -> str:
  if not value:
    return ""
  return value.upper().strip()


def handle_error(
  err: Union[str, Exception],
  msg: str = "",
  sleep_time: int = 1
) -> None:
  base_message = msg or 'Erro inesperado'
  print(f'{base_message}: {err}')

  if sleep_time > 0:
    sleep(sleep_time)


def ano_referencia(mes_target: int) -> int:
  hoje = datetime.today()
  if (hoje.month == 1 and mes_target == 12):
    return hoje.year - 1

  return hoje.year


def validate_nfe_row(lista: list) -> list:
  if len(lista) < 5:
    raise ValueError('NFe row requires 5+ fields')
  return lista


def validate_cte_row(lista: list) -> list:
  if len(lista) < 6:
    raise ValueError('CTe row requires 6+ fields')
  return lista


def clean_name(text: str) -> str:
  forbidden_chars = r'\/*?:"><|'
  nome_decoded = unidecode(text)
  nome_limpo = "".join(c for c in nome_decoded if c not in forbidden_chars)

  return " ".join(nome_limpo.split()).strip('.')

