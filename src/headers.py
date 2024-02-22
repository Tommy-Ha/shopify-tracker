from __future__ import annotations

import pathlib
import random
import json
import urllib.parse

from src.config import settings


class HeadersHandler:
    def __init__(
            self,
            headers_fp: str = "src/config/user_agents.json"
        ):
        self.headers_fp = pathlib.Path(headers_fp)

        self.headers: dict[str, str] = dict()
    
    def _get_opt_headers(self, url: str) -> dict[str, str]:
        parsed = urllib.parse.urlparse(url=url)
        base_url = parsed._replace(
            path="",
            params="",
            query="",
            fragment=""
        ).geturl()

        opt_headers = {
            "Authority": parsed.netloc,
            "Origin": base_url,
            "Referer": base_url
        }
        return opt_headers

    def _get_random_user_agent(self) -> dict[str, str]:
        with self.headers_fp.open(mode="r", encoding="utf-8") as f:
            user_agents = json.load(fp=f)
            idx = random.randint(
                a=0,
                b=len(user_agents)-1
            )

            return {
                "User-Agent": user_agents[idx]
            }

    def get_headers(
        self,
        url: str,
        additional_headers: dict[str, str] | None = None
    ) -> dict[str, str]:

        user_agent = self._get_random_user_agent()
        opt_headers = self._get_opt_headers(url=url)

        self.headers.update(settings.SHARED_HEADERS)
        self.headers.update(user_agent)
        self.headers.update(opt_headers)

        if additional_headers is not None:
            self.headers.update(additional_headers)

        return self.headers


def main() -> None:
    headers_handler = HeadersHandler()

    url="https://docs.python.org/3/library/urllib.parse.html#module-urllib.parse"

    headers = headers_handler.get_headers(url=url)
    print(headers)
    return


if __name__ == "__main__":
    main()
