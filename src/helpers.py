from typing import Union
from time import sleep


def _base_error_handler(
  err: Union[str, Exception],
  msg: str,
  default_msg: str,
  sleep_time: int
) -> None:
  base_message = msg or default_msg

  print(f'{base_message}: {err}')

  if sleep_time > 0:
    sleep(sleep_time)


def handle_timeout(
  err: Union[str, Exception],
  msg: str = "",
  sleep_time: int = 1
) -> None:
  _base_error_handler(
    err,
    msg,
    'Site demorou a responder',
    sleep_time
  )


def handle_http_error(
  err: Union[str, Exception],
  msg: str = "",
  sleep_time: int = 1
) -> None:
  _base_error_handler(
    err,
    msg,
    'Erro HTTP',
    sleep_time
  )


def handle_request_error(
  err: Union[str, Exception],
  msg: str = "",
  sleep_time: int = 1
) -> None:
  _base_error_handler(
    err,
    msg,
    'Erro desconhecido no site',
    sleep_time
  )


def handle_exception(
  err: Union[str, Exception],
  msg: str = "",
  sleep_time: int = 1
) -> None:
  _base_error_handler(
    err,
    msg,
    'Erro inesperado',
    sleep_time
  )


def handle_key_error(
  err: Union[str, Exception],
  msg: str = "",
  sleep_time: int = 1
) -> None:
  _base_error_handler(
    err,
    msg,
    'Valor faltando',
    sleep_time
  )


def handle_value_error(
  err: Union[str, Exception],
  msg: str = "",
  sleep_time: int = 1
) -> None:
  _base_error_handler(
    err,
    msg,
    'Valor inadequado',
    sleep_time
  )

