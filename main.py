import sys
from requests import Session
from time import perf_counter

from src.interface import input_dados
from src.utils import (
        resolver_emitente,
        salvar_arquivos,
)
from src.core import (
    login,
    ver_arquivos,
    extrair_empresas_href,
    trocar_empresa,
    carregar_dados,
    encontrar_linha,
    extrair_dados,
    baixar_arquivos,
    marcar_flag
)


def main():
    notas, empresa, mes_nota, mes_pasta, tipo = input_dados()

    start_time = perf_counter()

    with Session() as session:
        try:
            html_login = login(session)
            empresas_href = extrair_empresas_href(html_login)
            trocar_empresa(session, empresa, empresas_href)
            ver_arquivos(session, tipo)

            for nota in notas:
                print(f'\nProcessando: {nota}')

                try:
                    linhas = carregar_dados(session, nota, tipo)
                    linha = encontrar_linha(
                        linhas,
                        nota,
                        mes_nota,
                        tipo
                    )
                    dados = extrair_dados(linha, tipo)

                    xml, pdf = baixar_arquivos(
                        session,
                        dados['empresa_id'],
                        dados['chave'],
                        tipo
                    )

                    nome_emitente = resolver_emitente(
                        dados['emitente']
                    )
                    salvar_arquivos(
                        xml,
                        pdf,
                        nome_emitente,
                        nota,
                        empresa,
                        mes_pasta,
                        tipo
                    )

                    marcar_flag(session, dados['codigo_arquivo'])

                except Exception as e:
                    print(f'Erro na nota {nota}: {e}')

        except Exception as e:
            print(f'Erro fatal no processo: {e}')
            sys.exit(1)

    elapsed_time = perf_counter() - start_time
    print(f'\nTerminado em: {elapsed_time:0.2f} segundos')
    input('Pressione Enter para fechar...')



if __name__ == "__main__":
    main()
