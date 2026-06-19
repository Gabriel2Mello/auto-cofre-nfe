from typing import Any
from cloudscraper import CloudScraper
from requests import Response

class TimeoutScraper(CloudScraper):
  def __init__(
    self,
    default_timeout: float = 10,
    *args: Any,
    **kwargs: Any
  ) -> None:
    super().__init__(
      browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
      },
      *args,
      **kwargs
    )
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

