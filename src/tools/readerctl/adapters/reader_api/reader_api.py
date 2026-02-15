import time

import requests
from buvis.pybase.adapters import console
from readerctl.adapters.response import AdapterResponse

BASE_URL = "https://readwise.io/api"


class ReaderAPIAdapter:
    @classmethod
    def check_token(cls, token: str) -> AdapterResponse:
        res = requests.get(
            url=f"{BASE_URL}/v2/auth/",
            headers={"Authorization": f"Token {token}"},
            timeout=30,
        )

        if res.status_code == 204:
            return AdapterResponse(message="Token is valid")
        else:
            return AdapterResponse(code=res.status_code, message=res.text)

    def __init__(self, token: str) -> None:
        self.token = token

    def add_url(self, url: str) -> AdapterResponse:
        reader_url = url

        res = requests.post(
            url=f"{BASE_URL}/v3/save/",
            headers={"Authorization": f"Token {self.token}"},
            json={"url": url},
            timeout=30,
        )

        if res.status_code == 429:  # this endpoint is rate limited
            time_to_wait = res.headers.get("Retry-After", 60)
            try:
                time_to_wait = int(time_to_wait)
            except ValueError:
                time_to_wait = 60
            with console.status("Going too fast, have to wait"):
                time.sleep(time_to_wait)

            return self.add_url(url)

        elif res.status_code in [200, 201]:
            json = res.json()
            reader_url = json["url"]

            return AdapterResponse(message=f"{url} added to Reader as {reader_url}")
        else:
            json = res.json()

            return AdapterResponse(code=res.status_code, message=json["url"][0])
