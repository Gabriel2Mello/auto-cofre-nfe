from src.config import (
  CONTENT_TYPE,
  USER_AGENT,
  URL_BASE,
  CNPJ_MATRIZ,
  SENHA_COFRE,
)

def login(session):
  """Realiza a autenticação no site e retorna o HTML da página inicial."""
  session.headers.update({
    'User-Agent': USER_AGENT,
    'Origin': URL_BASE,
    'Content-Type': CONTENT_TYPE,
    'Connection': 'keep-alive'
  })

  payload = {
    's': 'nfe',
    'cpf': CNPJ_MATRIZ,
    'senha': SENHA_COFRE
  }

  response = session.post(
    url=f'{URL_BASE}/login/enviar',
    data=payload,
    headers={'Referer': f'{URL_BASE}/login'},
    allow_redirects=True,
    timeout=10
  )
  response.raise_for_status()

  return response.text

