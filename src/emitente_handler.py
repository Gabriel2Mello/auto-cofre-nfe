import json
from collections.abc import Callable
from pathlib import Path
from os import fsync
from tempfile import NamedTemporaryFile

from src.utils import (
  obter_caminho_json,
  upper_strip,
  clean_name,
)


def _validar_catalogo(conteudo: object) -> dict[str, str]:
  if not isinstance(conteudo, dict) or any(
      not isinstance(chave, str) or not chave.strip()
      or not isinstance(nome, str) or not nome.strip()
      for chave, nome in conteudo.items()):
    raise ValueError('Catálogo de emitentes inválido: use um objeto JSON com emitentes e nomes não vazios, ambos em texto. O arquivo não foi alterado.')
  return conteudo


class EmitenteHandler:
  def __init__(self) -> None:
    self.caminho_json = obter_caminho_json()
    self.emitentes_conhecidos = self._carregar_emitentes()
    self._dirty = False

  def _carregar_emitentes(self) -> dict[str, str]:
    try:
      with self.caminho_json.open('r', encoding='utf-8') as arquivo:
        conteudo = json.load(arquivo)
    except FileNotFoundError:
      return {}
    except (json.JSONDecodeError, UnicodeError) as erro:
      raise ValueError('Catálogo de emitentes inválido: confira o JSON e a codificação UTF-8. O arquivo não foi alterado.') from erro
    return _validar_catalogo(conteudo)

  def get_nome(self, emitente: str, solicitar_nome: Callable[[str], str] | None = None) -> str:
    key = upper_strip(emitente)
    if not key:
      return ""

    nome_emitente = self.emitentes_conhecidos.get(key)
    if nome_emitente:
      return nome_emitente

    print(f"Emitente não reconhecido: {emitente}")
    try:
      resposta = solicitar_nome(emitente) if solicitar_nome else input('Digite o nome: ')
      emitente_identificado = upper_strip(resposta) or key
      nome_final = clean_name(emitente_identificado)

      self.emitentes_conhecidos[key] = nome_final
      self._dirty = True
    except(EOFError, KeyboardInterrupt):
      return clean_name(emitente)

    return nome_final

  def close(self) -> None:
    if not self._dirty:
      return

    conteudo = json.dumps(_validar_catalogo(self.emitentes_conhecidos), indent=4, ensure_ascii=False)
    temporario: Path | None = None
    try:
      self.caminho_json.parent.mkdir(parents=True, exist_ok=True)
      # O mesmo diretório permite substituir sem apagar o catálogo anterior.
      with NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.caminho_json.parent,
                             prefix=f'.{self.caminho_json.stem}-', suffix='.tmp', delete=False) as arquivo:
        temporario = Path(arquivo.name)
        arquivo.write(conteudo)
        arquivo.flush()
        fsync(arquivo.fileno())

      # No Windows, o temporário precisa estar fechado antes da substituição.
      temporario.replace(self.caminho_json)
      self._dirty = False
    except OSError as erro:
      detalhe = (f' Temporário mantido para conferência: {temporario.name}; pode estar incompleto.'
                 if temporario is not None else '')
      raise RuntimeError('Não foi possível atualizar o catálogo de emitentes. '
                         'O catálogo anterior não foi removido.' + detalhe) from erro
