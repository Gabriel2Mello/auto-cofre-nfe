"""Recursos empacotados são imutáveis; dados nunca ficam em _MEIPASS."""
import os
from pathlib import Path
import sys
import json


def pasta_dados() -> Path:
  override = os.environ.get('NUNES_COFRE_DADOS')
  if override:
    return Path(override).resolve()
  if getattr(sys, 'frozen', False):
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local/share'))) / 'Nunes' / 'Cofre'
  return Path(__file__).resolve().parents[1]


def pasta_preferencias() -> Path:
  if os.environ.get('NUNES_COFRE_DADOS'):
    return pasta_dados()
  return Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local/share'))) / 'Nunes' / 'Cofre'


def recursos() -> Path:
  return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))


def documentos_entrada() -> str:
  """Preferência da interface; CAMINHO_DOCUMENTO_ENTRADA é o fallback legado."""
  arquivo = pasta_preferencias() / 'desktop-configuracao.json'
  try:
    if arquivo.stat().st_size > 131072:
      raise ValueError('Configuração muito grande.')
    dados = json.loads(arquivo.read_text(encoding='utf-8'))
    caminho = dados.get('pasta_documentos') if isinstance(dados, dict) else None
    if not isinstance(dados, dict) or dados.get('formato') != 1 or not isinstance(caminho, str) or not caminho or not Path(caminho).is_absolute():
      raise ValueError('Configuração inválida.')
    return caminho
  except FileNotFoundError:
    return os.environ.get('CAMINHO_DOCUMENTO_ENTRADA', '')
  except (OSError, ValueError, TypeError) as erro:
    raise ValueError('Não foi possível ler a pasta configurada. Escolha novamente em Configurações.') from erro


def salvar_documentos_entrada(caminho: str) -> str:
  from integracao_hub import gravar_registro
  pasta = Path(caminho)
  if not pasta.is_absolute() or not pasta.is_dir():
    raise ValueError('Selecione uma pasta existente e acessível para DOCUMENTOS DE ENTRADA.')
  pasta = pasta.resolve()
  preferencias = pasta_preferencias()
  preferencias.mkdir(parents=True, exist_ok=True)
  gravar_registro(preferencias / 'desktop-configuracao.json',
                 {'formato': 1, 'pasta_documentos': str(pasta)})
  return str(pasta)


def vinculo_central() -> Path | None:
  # Fonte conserva .local/central.json; override explícito mantém precedência.
  if getattr(sys, 'frozen', False) and not os.environ.get('NUNES_CENTRAL_CONFIG'):
    caminho = pasta_dados() / 'central.json'
    if caminho.is_file():
      return caminho
  return None
