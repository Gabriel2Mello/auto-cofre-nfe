from datetime import datetime

from src.utils import encerrar_programa
from src.parsers import resolve_emitente, DocumentoFiscal
from src.enums import TipoDocumento, Empresa, ModoData


def escolher_mes_ano(descricao: str, tentativas: int = 5) -> tuple[int, int]:
  for _ in range(tentativas):
    try:
      data_input = input(descricao).strip()
      data = datetime.strptime(data_input, '%m/%Y')
      return data.month, data.year
    except ValueError:
      print('Formato MM/AAAA.')

  encerrar_programa(None)
  return 1, 1


def input_dados() -> tuple[list[str], Empresa, int, int, int, int, TipoDocumento]:
  tipo_input = input('Tipo 1(NFe) 2(CTe): ').strip()
  tipo = TipoDocumento.CTE if tipo_input == '2' else TipoDocumento.NFE

  notas_input = input('Nota: ').strip()
  notas = [n.strip() for n in notas_input.split(',') if n.strip()]
  encerrar_programa(notas[0] if notas else None)

  empresa_input = input('Empresa 1(Matriz) 2(Filial): ').strip()
  empresa = Empresa.MATRIZ if empresa_input == '1' else Empresa.FILIAL

  modo_input = input('Data 1(Atual) 2(Manual): ').strip()
  modo = ModoData.MANUAL if modo_input == '2' else ModoData.ATUAL

  if modo == ModoData.ATUAL:
    data_atual = datetime.today()

    mes_nota = mes_pasta = data_atual.month
    ano_nota = ano_pasta = data_atual.year
  else:
    mes_nota,  ano_nota  = escolher_mes_ano('Data da Nota (ex: 12/2001): ')
    mes_pasta, ano_pasta = escolher_mes_ano('Pasta (ex: 01/2002): ')

  return notas, empresa, mes_nota, mes_pasta, ano_nota, ano_pasta, tipo


def escolher_emitente(linhas_validas: list[DocumentoFiscal]) -> DocumentoFiscal:
  print('\nMAIS DE UM EMITENTE ENCONTRADO:')

  for idx, linha in enumerate(linhas_validas, start=1):
    nome_emitente = resolve_emitente(linha.emitente_html)

    print(f"({idx}) {nome_emitente}")

  while True:
    try:
      escolha_input = input('Escolha: ').strip()
      encerrar_programa(escolha_input)

      opcao = int(escolha_input)
      if 1 <= opcao <= len(linhas_validas):
        return linhas_validas[opcao - 1]

      print(f"Digite um número entre 1 e {len(linhas_validas)}")

    except ValueError:
      print('Valor inválido')

