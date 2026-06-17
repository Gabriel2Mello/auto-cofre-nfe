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


  def get_or_create(self, emitente: str) -> str:
    emitente = emitente.upper().strip()

    if emitente in self.emitentes_conhecidos:
      return self.emitentes_conhecidos[emitente]

    print(f'\nEmitente não reconhecido: {emitente}')
    emitente_identificado = input('Digite o nome: ').upper().strip()

    if not emitente_identificado:
      emitente_identificado = emitente

    self.emitentes_conhecidos[emitente] = emitente_identificado

    self._persist()

    return emitente_identificado


  def _persist(self):
    with open(self.caminho_json, 'w', encoding='utf-8') as f:
      json.dump(self.emitentes_conhecidos, f, indent=4, ensure_ascii=False)

