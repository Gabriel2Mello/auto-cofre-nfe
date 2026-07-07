from datetime import datetime
from typing import List, Tuple, TypeVar

from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import radiolist_dialog

from src.config import Config
from src.utils import encerrar_programa
from src.parsers import resolve_emitente, DocumentoFiscal
from src.enums import TipoDocumento, Empresa

T = TypeVar('T')


def escolher_mes_ano(descricao: str) -> tuple[int, int]:
  while True:
    try:
      data_input = prompt(descricao).strip()
      encerrar_programa(data_input)

      data_validada = datetime.strptime(data_input, '%m/%Y')
      return data_validada.month, data_validada.year

    except ValueError:
      print('Formato MM/AAAA.')


def input_dados() -> tuple[list[str], Empresa, int, int, int, int, TipoDocumento]:
  tipo_input = prompt('Tipo 1(NFe) 2(CTe): ').strip()
  tipo = TipoDocumento.CTE if tipo_input == '2' else TipoDocumento.NFE

  notas_input = prompt('Nota: ').strip()
  notas = [n.strip() for n in notas_input.split(',') if n.strip()]
  encerrar_programa(notas[0] if notas else None)

  modo_input = prompt('Modo 1(Normal) 2(Manual): ').strip()
  modo = 'MANUAL' if modo_input == '2' else 'NORMAL'

  empresa_input = prompt('Empresa 1(Matriz) 2(Filial): ').strip()
  empresa = Empresa.MATRIZ if empresa_input == '1' else Empresa.FILIAL

  if modo == 'NORMAL':
    data_atual = datetime.today()

    mes_nota = mes_pasta = data_atual.month
    ano_nota = ano_pasta = data_atual.year
  else:
    mes_nota, ano_nota = escolher_mes_ano('Data da Nota (ex: 12/2001): ')
    mes_pasta, ano_pasta = escolher_mes_ano('Data da Pasta (ex: 01/2002): ')

  return notas, empresa, mes_nota, mes_pasta, ano_nota, ano_pasta, tipo


def escolher_emitente(linhas_validas: list[DocumentoFiscal]) -> DocumentoFiscal:
  print('\nMAIS DE UM EMITENTE ENCONTRADO:')

  for idx, linha in enumerate(linhas_validas, start=1):
    nome_emitente = resolve_emitente(linha.emitente_html)

    print(f"({idx}) {nome_emitente}")

  while True:
    try:
      escolha_input = prompt('Escolha: ').strip()
      encerrar_programa(escolha_input)

      opcao = int(escolha_input)
      if 1 <= opcao <= len(linhas_validas):
        return linhas_validas[opcao - 1]

      print(f"Digite um número entre 1 e {len(linhas_validas)}")

    except ValueError:
      print('Valor inválido')

