from enum import StrEnum


class TipoDocumento(StrEnum):
  NFE = 'nfe'
  CTE = 'cte'


class Empresa(StrEnum):
  MATRIZ = 'MATRIZ'
  FILIAL = 'FILIAL'


class ModoData(StrEnum):
  ATUAL  = 'ATUAL'
  MANUAL = 'MANUAL'

