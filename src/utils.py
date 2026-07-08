import ctypes
from pathlib import Path
import sys
from time import sleep

from unidecode import unidecode

from src.config import Config
from src.enums import TipoDocumento, Empresa

FORBIDDEN_CHARS = r'\/*?:"><|'


def pause() -> None:
  try:
    input('\nPressione Enter para fechar...')
  except (EOFError, KeyboardInterrupt):
    pass


def encerrar_programa(texto: str | None) -> None:
  if not texto:
    print('\nNenhum valor informado...')
    pause()
    sys.exit(0)


def obter_caminho_json(filename = 'emitentes_conhecidos.json') -> Path:
  if hasattr(sys, 'frozen'):
    diretorio_execucao = Path(sys.executable).parent
  else:
    diretorio_execucao = Path(__file__).parent.parent

  return diretorio_execucao / filename


def salvar_arquivos(
  xml: bytes,
  pdf: bytes,
  emitente: str,
  nota: str,
  empresa: Empresa,
  mes: int,
  ano: str,
  tipo: TipoDocumento,
  caminho_pasta: str,
) -> None:
  nome_limpo = f'{emitente} {nota}'
  base_path = Path(caminho_pasta)

  if not base_path.exists():
    raise RuntimeError('CAMINHO_DOCUMENTO_ENTRADA não configurado.')

  tipo_prefix = 'NF-e' if tipo == TipoDocumento.NFE else 'CT-e'
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
  return value.upper().strip() if value else ""


def handle_error(
  err: Exception,
  msg: str = "",
  sleep_time: int = 1
) -> None:
  context = msg or 'Erro inesperado'

  print(f"{context}: {err}", file=sys.stderr)

  if sleep_time > 0:
    sleep(sleep_time)


def extract_digits(text: str) -> str:
  return "".join(c for c in text if c.isdigit())


def clean_name(text: str) -> str:
  remocao = str.maketrans('', '', FORBIDDEN_CHARS)
  nome_limpo = unidecode(text).translate(remocao)
  return " ".join(nome_limpo.split()).strip('.')

