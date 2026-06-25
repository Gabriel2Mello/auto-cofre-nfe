from datetime import datetime
from typing import Any

from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import radiolist_dialog

from src.config import MONTHS
from src.utils import encerrar_programa
from src.parsers import resolve_emitente


def selecionar_mes() -> int:
  meses = [(i, MONTHS[i]) for i in range(1, 13)]

  mes = radiolist_dialog(
    title='Escolha o mês:',
    values=meses
  ).run()

  encerrar_programa(mes)
  return mes


def escolher_mes(titulo: str, texto: str) -> int:
  mes_atual = datetime.today().month

  mes = radiolist_dialog(
    title=titulo,
    text=texto,
    values=[
      (mes_atual, f'ATUAL ({MONTHS[mes_atual]})'),
      ('outro', 'OUTRO')
    ]
  ).run()

  encerrar_programa(mes)

  if mes == 'outro':
    mes = selecionar_mes()

  return int(mes)


def input_dados() -> tuple[list[str], str, int, int, str]:
  #tipo_input = prompt('Tipo 1(NFe) 2(CTe): ').strip()
  #tipo = 'cte' if tipo_input == '2' else 'nfe'
  tipo = 'nfe'

  notas_input = prompt('Nota: ').strip()
  notas = [n.strip() for n in notas_input.split(',') if n.strip()]
  encerrar_programa(notas)

  #modo_input = prompt('Modo 1(Normal) 2(Manual): ').strip()
  #modo = 'MANUAL' if modo_input == '2' else 'NORMAL'
  modo = 'NORMAL'

  empresa = None
  mes_nota = None
  mes_pasta = None

  if modo == 'NORMAL':
    empresa_input = prompt('Empresa 1(Matriz) 2(Filial): ').strip()
    empresa = 'MATRIZ' if empresa_input == '1' else 'FILIAL'

    mes_atual = datetime.today().month
    mes_nota = mes_atual
    mes_pasta = mes_atual
  else:
    empresa = radiolist_dialog(
      title='Empresa',
      text='Empresa de faturamento:',
      values=[
        ('MATRIZ', 'MATRIZ'),
        ('FILIAL', 'FILIAL')
      ]
    ).run()
    encerrar_programa(empresa)

    mes_nota = escolher_mes(
      'Mês da Nota',
      'Selecione o mês de faturamento da nota:'
    )
    mes_pasta = escolher_mes(
      'Pasta Destino',
      'Pasta destino:'
    )

  return notas, empresa, mes_nota, mes_pasta, tipo


def escolher_emitente(linhas_validas: list) -> str:
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

