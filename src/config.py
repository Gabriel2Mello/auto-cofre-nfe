from os import environ
from typing import Dict, List
from src.enums import TipoDocumento, Empresa


def load_env(variable: str, default: str = "") -> str:
  value = environ.get(variable, default)
  if not value and not default:
    raise ValueError(f"Environment variable '{variable}' missing.")
  return value


class Config:
  URL_BASE: str = 'https://painel.cofrenfe.com.br'
  CONTENT_TYPE: str = 'application/x-www-form-urlencoded; charset=UTF-8'
  ACCEPT: str = 'application/json, text/javascript, */*; q=0.01'
  REQUESTED_WITH: str = 'XMLHttpRequest'
  TROCAR_LOGIN_URL: str = 'trocarLogin?vid='

  TAMANHO_CHAVE: int = 22
  TAMANHO_CNPJ: int = 14
  CHECK_FLAG: int = 10
  FLAG_CLIENTE: str = '98'
  FLAG_CONTA: str = '98'

  COLUNAS: Dict[TipoDocumento, str] = {
    TipoDocumento.NFE: 'recebimento_quando,emitente_nome,nfe_data,nro_nota,vlr_total,tipo,',
    TipoDocumento.CTE: 'recebimento_quando,emitente_nome,destinatario_nome,nfe_data,nro_nota,vlr_total,tipo,tipo'
  }

  MONTHS: List[str] = [
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

  def __init__(self) -> None:
    self.senha_cofre: str = load_env('SENHA_COFRE')
    self.caminho_documento_entrada: str = load_env('CAMINHO_DOCUMENTO_ENTRADA')
    self.cnpj: Dict[Empresa, str] = {
      Empresa.MATRIZ: load_env('CNPJ_MATRIZ'),
      Empresa.FILIAL: load_env('CNPJ_FILIAL'),
    }

