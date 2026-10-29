"""Prévia manual com dados sintéticos; nunca acessa o Cofre nem salva arquivos."""

from src.controlador_web import EstadoInterface
from src.interface_web import criar_servidor
from src.parsers import LinhaNFe


def simular(pedido, estado):
  for indice, nota in enumerate(pedido.notas):
    estado.verificar_parada()
    estado.atualizar_nota(indice, 'Processando', 'Prévia com dados sintéticos.')
    estado.selecionar_emitente([
      LinhaNFe('', 'FORNECEDOR DEMONSTRAÇÃO A', '01/10/2026', nota, '100,00'),
      LinhaNFe('', 'FORNECEDOR DEMONSTRAÇÃO B', '02/10/2026', nota, '200,00'),
    ], nota=nota)
    nome = estado.solicitar_nome('FORNECEDOR DEMONSTRAÇÃO')
    estado.atualizar_nota(indice, 'Concluído', f'SIMULAÇÃO · {nome} · nenhum arquivo salvo ou portal acessado.')


if __name__ == '__main__':
  estado = EstadoInterface(simular)
  estado.informar('Prévia com dados sintéticos. Nenhuma integração será executada.')
  servidor = criar_servidor(estado)
  print(f'http://127.0.0.1:{servidor.server_port}', flush=True)
  try:
    servidor.serve_forever()
  finally:
    servidor.server_close()
    if estado.worker:
      estado.worker.join()
