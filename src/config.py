from os import environ


def load_env(variable: str, default: str = "") -> str:
  value = environ.get(variable, default)
  if not value and not default:
    raise ValueError(f"Environment variable '{variable}' missing.")
  return value


class Config:
  SENHA_COFRE: str
  CAMINHO_DOCUMENTO_ENTRADA: str


URL_BASE = 'https://painel.cofrenfe.com.br'
CONTENT_TYPE = 'application/x-www-form-urlencoded; charset=UTF-8'
ACCEPT = 'application/json, text/javascript, */*; q=0.01'
REQUESTED_WITH = 'XMLHttpRequest'

CNPJ = {
  'MATRIZ': '09.034.052/0001-53',
  'FILIAL': '09.034.052/0002-34'
}

COLUNAS = {
  'nfe': 'recebimento_quando,emitente_nome,nfe_data,nro_nota,vlr_total,tipo,',
  'cte': 'recebimento_quando,emitente_nome,destinatario_nome,nfe_data,nro_nota,vlr_total,tipo,tipo'
}

MONTHS = [
  None,
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

