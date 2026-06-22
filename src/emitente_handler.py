from pathlib import Path
import json

from src.utils import obter_caminho_json


class EmitenteHandler:
  def __init__(self):
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


  def get_nome(self, emitente: str) -> str | None:
    return self.emitentes_conhecidos.get(emitente.upper().strip())


  def salvar(self, emitente: str, nome_identificado: str) -> None:
    self.emitentes_conhecidos[emitente.upper().strip()] = nome_identificado.upper().strip()
    self._persist()


  def _persist(self):
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

