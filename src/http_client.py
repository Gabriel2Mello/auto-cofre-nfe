from typing import Any
from requests import Session, Response

class TimeoutSession(Session):
  def __init__(self, default_timeout: float = 10) -> None:
    super().__init__()
    self.default_timeout = default_timeout


  def request(
    self,
    method: str | bytes,
    url: str | bytes,
    *args: Any,
    **kwargs: Any
  ) -> Response:
    kwargs.setdefault('timeout', self.default_timeout)
    return super().request(method, url, *args, **kwargs)

