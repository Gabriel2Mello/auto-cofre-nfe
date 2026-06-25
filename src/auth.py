from cloudscraper import CloudScraper
from src.config import (
  CONTENT_TYPE,
  CNPJ,
  URL_BASE,
  SENHA_COFRE,
)

def login(session: CloudScraper) -> str:
  """Realiza a autenticação no site e retorna o HTML da página inicial."""
  session.headers.update({
    'Origin': URL_BASE,
    'Content-Type': CONTENT_TYPE,
    'Connection': 'keep-alive'
  })

  payload = {
    's': 'nfe',
    'cpf': CNPJ['MATRIZ'],
    'senha': SENHA_COFRE
  }

  response = session.post(
    url=f'{URL_BASE}/login/enviar',
    data=payload,
    headers={'Referer': f'{URL_BASE}/login'},
    allow_redirects=True,
  )
  response.raise_for_status()

  return response.text

