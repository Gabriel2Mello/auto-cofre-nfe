from cloudscraper import CloudScraper
from src.config import Config

def login(session: CloudScraper) -> str:
  """Realiza a autenticação no site e retorna o HTML da página inicial."""
  session.headers.update({
    'Origin': Config.URL_BASE,
    'Content-Type': Config.CONTENT_TYPE,
    'Connection': 'keep-alive'
  })

  payload = {
    's': 'nfe',
    'cpf': Config.CNPJ.get('MATRIZ'),
    'senha': Config.SENHA_COFRE
  }

  response = session.post(
    url=f'{Config.URL_BASE}/login/enviar',
    data=payload,
    headers={'Referer': f'{Config.URL_BASE}/login'},
    allow_redirects=True,
  )
  response.raise_for_status()

  return response.text

