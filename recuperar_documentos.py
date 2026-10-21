"""Inspeção e recuperação de arquivos locais; não acessa o Cofre nem as métricas."""

import argparse
import json
from pathlib import Path
from collections.abc import Sequence

from integracao_hub import executar_console
from src.gravacao_documentos import abandonar_preparacao, listar_gravacoes, recuperar_gravacao


def main(argumentos: Sequence[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--pasta', required=True, type=Path, help='Pasta base dos documentos')
  acao = parser.add_mutually_exclusive_group()
  acao.add_argument('--concluir', metavar='ID', help='Conferir e concluir uma gravação preparada')
  acao.add_argument('--abandonar', metavar='ID', help='Liberar nova baixa quando a preparação falhou antes de publicar')
  opcoes = parser.parse_args(argumentos)

  def executar() -> int:
    try:
      if opcoes.concluir:
        nome = recuperar_gravacao(opcoes.pasta, opcoes.concluir)
        print(f'Conjunto local conferido e concluído: {nome}')
        print('Métricas e sinalização do portal não foram executadas. Uma nova baixa normal reaproveita o conjunto válido.')
      elif opcoes.abandonar:
        abandonar_preparacao(opcoes.pasta, opcoes.abandonar)
        print('Preparação abandonada, preservando registro e temporários. Uma nova baixa pode ser iniciada.')
      else:
        print(json.dumps(listar_gravacoes(opcoes.pasta), ensure_ascii=False, indent=2))
      return 0
    except (OSError, ValueError, RuntimeError) as erro:
      print(f'Não foi possível concluir a ação: {erro}')
      return 1

  return executar_console('cofre-nfe', 'Cofre NF-e', executar, sisplan=False)


if __name__ == '__main__':
  raise SystemExit(main())
