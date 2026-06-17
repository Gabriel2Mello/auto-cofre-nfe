from os import environ

CNPJ_MATRIZ = environ['CNPJ_MATRIZ']
SENHA_COFRE = environ['SENHA_COFRE']
CAMINHO_DOCUMENTO_ENTRADA = environ['CAMINHO_DOCUMENTO_ENTRADA']


USER_AGENT = (
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
  'AppleWebKit/537.36 (KHTML, like Gecko) '
  'Chrome/145.0.0.0 Safari/537.36'
)

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

