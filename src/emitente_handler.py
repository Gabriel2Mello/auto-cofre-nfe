from pathlib import Path
import json

from src.utils import obter_caminho_json


class EmitenteHandler:
  def __init__(self) -> None:
    self.caminho_json = obter_caminho_json()
    self.emitentes_conhecidos = self._carregar_emitentes()


  def _carregar_emitentes(self) -> dict:
    if self.caminho_json.exists():
      try:
        with open(self.caminho_json, 'r', encoding='utf-8') as f:
          return json.load(f)
      except json.JSONDecodeError:
        return {}
    return {}


  def get_nome(self, emitente: str) -> str:
    nome_emitente = self.emitentes_conhecidos.get(emitente.upper().strip())
    if nome_emitente:
      return nome_emitente

    print(f"Emitente não reconhecido: {emitente}")

    try:
      emitente_identificado = input('Digite o nome: ').upper().strip() or emitente
      self._salvar(emitente, emitente_identificado)
    except(EOFError, KeyboardInterrupt):
      return emitente

    return emitente_identificado


  def _salvar(self, emitente: str, nome_identificado: str) -> None:
    self.emitentes_conhecidos[emitente.upper().strip()] = nome_identificado.upper().strip()
    self._persist()


  def _persist(self) -> None:
    temp_path = self.caminho_json.with_suffix('.tmp')

    try:
      with open(temp_path, 'w', encoding='utf-8') as f:
        json.dump(self.emitentes_conhecidos, f, indent=4, ensure_ascii=False)

      temp_path.replace(self.caminho_json)

    except Exception as e:
      print(f"Erro ao salvar emitentes_conhecidos.json: {e}")
    finally:
      if temp_path.exists():
        temp_path.unlink()

