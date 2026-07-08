from cloudscraper import CloudScraper
from src.config import Config

def login(session: CloudScraper, senha: str, cnpj: str) -> str:
  """Realiza a autenticação no site e retorna o HTML da página inicial."""
  session.headers.update({
    'Origin': Config.URL_BASE,
    'Content-Type': Config.CONTENT_TYPE,
    'Connection': 'keep-alive'
  })

  payload = {
    's': 'nfe',
    'cpf': cnpj,
    'senha': senha
  }

  response = session.post(
    url=f'{Config.URL_BASE}/login/enviar',
    data=payload,
    headers={'Referer': f'{Config.URL_BASE}/login'},
    allow_redirects=True,
  )
  response.raise_for_status()

  return response.text

