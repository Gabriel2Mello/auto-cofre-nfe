from datetime import datetime
from typing import List, Tuple, TypeVar

from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import radiolist_dialog

from src.config import Config
from src.utils import encerrar_programa
from src.parsers import resolve_emitente, DocumentoFiscal

T = TypeVar('T')


def exibir_dialogo(titulo: str, texto: str, valores: List[Tuple[T, str]]) -> T:
  escolha = radiolist_dialog(title=titulo, text=texto, values=valores).run()
  encerrar_programa(escolha)
  return escolha


def selecionar_mes() -> int:
  meses = [(i, Config.MONTHS[i]) for i in range(1, 13)]
  return exibir_dialogo('Escolha o mês:', '', meses)


def escolher_mes(titulo: str, texto: str) -> int:
  mes_atual = datetime.today().month
  valores = [
    (mes_atual, f'ATUAL ({Config.MONTHS[mes_atual]})'),
    ('outro', 'OUTRO')
  ]

  mes = exibir_dialogo(titulo, texto, valores)
  if mes == 'outro':
    mes = selecionar_mes()

  return int(mes)


def input_dados() -> tuple[list[str], str, int, int, str]:
  tipo_input = prompt('Tipo 1(NFe) 2(CTe): ').strip()
  tipo = 'cte' if tipo_input == '2' else 'nfe'

  notas_input = prompt('Nota: ').strip()
  notas = [n.strip() for n in notas_input.split(',') if n.strip()]
  encerrar_programa(notas)

  modo_input = prompt('Modo 1(Normal) 2(Manual): ').strip()
  modo = 'MANUAL' if modo_input == '2' else 'NORMAL'

  if modo == 'NORMAL':
    empresa_input = prompt('Empresa 1(Matriz) 2(Filial): ').strip()
    empresa = 'MATRIZ' if empresa_input == '1' else 'FILIAL'

    mes_atual = datetime.today().month
    mes_nota = mes_pasta = mes_atual
  else:
    valores = [('MATRIZ', 'MATRIZ'), ('FILIAL', 'FILIAL')]
    empresa = exibir_dialogo(
      'Empresa',
      'Empresa:',
      valores
    )
    mes_nota = escolher_mes(
      'Mês da Nota',
      'Mês da Nota:'
    )
    mes_pasta = escolher_mes(
      'Pasta Destino',
      'Pasta Destino:'
    )

  return notas, empresa, mes_nota, mes_pasta, tipo


def escolher_emitente(linhas_validas: list) -> DocumentoFiscal:
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

