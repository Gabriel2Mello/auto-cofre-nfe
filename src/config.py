from os import environ
from typing import ClassVar, Dict, List


def load_env(variable: str, default: str = "") -> str:
  value = environ.get(variable, default)
  if not value and not default:
    raise ValueError(f"Environment variable '{variable}' missing.")
  return value


class Config:
  SENHA_COFRE: str = ""
  CAMINHO_DOCUMENTO_ENTRADA: str = ""

  URL_BASE: ClassVar[str] = 'https://painel.cofrenfe.com.br'
  CONTENT_TYPE: ClassVar[str] = 'application/x-www-form-urlencoded; charset=UTF-8'
  ACCEPT: ClassVar[str] = 'application/json, text/javascript, */*; q=0.01'
  REQUESTED_WITH: ClassVar[str] = 'XMLHttpRequest'

  CNPJ: ClassVar[Dict[str, str]] = {
    'MATRIZ': '09.034.052/0001-53',
    'FILIAL': '09.034.052/0002-34'
  }

  COLUNAS: ClassVar[Dict[str, str]] = {
    'nfe': 'recebimento_quando,emitente_nome,nfe_data,nro_nota,vlr_total,tipo,',
    'cte': 'recebimento_quando,emitente_nome,destinatario_nome,nfe_data,nro_nota,vlr_total,tipo,tipo'
  }

  MONTHS: ClassVar[List[str]] = [
    '',
    'JANEIRO',
    'FEVEREIRO',
    'MARÇO',
    'ABRIL',
    'MAIO',
    'JUNHO',
    'JULHO',
    'AGOSTO',
    'SETEMBRO',
    'OUTUBRO',
    'NOVEMBRO',
    'DEZEMBRO',
  ]

def init_config() -> None:
  Config.SENHA_COFRE = load_env('SENHA_COFRE')
  Config.CAMINHO_DOCUMENTO_ENTRADA = load_env('CAMINHO_DOCUMENTO_ENTRADA')

