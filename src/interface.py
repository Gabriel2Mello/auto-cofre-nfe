from datetime import datetime

from prompt_toolkit.shortcuts import radiolist_dialog
from prompt_toolkit import prompt

from src.config import (MONTHS)
from src.utils import encerrar_programa


def selecionar_mes():
    meses = [(i, MONTHS[i]) for i in range(1,13)]

    mes = radiolist_dialog(
        title='Escolha o mês:',
        values=meses
    ).run()

    encerrar_programa(mes)
    return mes


def escolher_mes(titulo, texto):
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

    return mes


def input_dados():
    tipo_input = prompt('Tipo 1(NFe) 2(CTe): ').strip()
    tipo = 'NFE' if tipo_input == '1' else 'CTE'

    notas_input = prompt('Nota: ').strip()
    notas = [n.strip() for n in notas_input.split(',') if n.strip()]

    modo_input = prompt('Modo 1(Normal) 2(Manual): ').strip()
    modo = 'NORMAL' if modo_input == '1' else 'MANUAL'

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

