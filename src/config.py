from os import environ
import sys


def carregar_env(chave):
  valor = environ.get(chave)
  if not valor:
    print(f"Variável de ambiente '{chave}' não configurada.")
    input('Pressione Enter para fechar...')
    sys.exit(1)
  return valor

SENHA_COFRE = carregar_env('SENHA_COFRE')
CAMINHO_DOCUMENTO_ENTRADA = carregar_env('CAMINHO_DOCUMENTO_ENTRADA')

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

