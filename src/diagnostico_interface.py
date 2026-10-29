"""Falhas de início observadas no navegador, sem mensagens ou dados fiscais."""
from src.diagnostico_abertura import registrar


def registrar_inicio(dados):
  tipos = {'Error': RuntimeError, 'TypeError': TypeError, 'SyntaxError': SyntaxError,
           'AbortError': InterruptedError, 'TimeoutError': TimeoutError}
  if set(dados) != {'tipo', 'status'} or not isinstance(dados['tipo'], str) or dados['tipo'] not in tipos:
    raise ValueError('Diagnóstico de início inválido.')
  status = dados['status']
  if status is not None and (type(status) is not int or not 100 <= status <= 599):
    raise ValueError('Código HTTP inválido.')
  # Etapa controlada conserva a origem JS e o HTTP sem aceitar texto livre.
  etapa = 'inicio_' + dados['tipo'] + ('_http_' + str(status) if status is not None else '_sem_resposta')
  caminho = registrar(tipos[dados['tipo']](), etapa)
  if caminho is None:
    raise OSError('Diagnóstico local indisponível.')
  return caminho
