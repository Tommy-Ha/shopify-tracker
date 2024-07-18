from __future__ import annotations

import argparse
import urllib.parse
import pathlib
import json

from typing import Sequence
from typing import NamedTuple

from src import headers
from src import parsers
from src.config import settings
import pathlib
import subprocess


HEADERS_HANDLER = headers.HeadersHandler()


def get_url_base_name(url: str) -> str:
    parsed = urllib.parse.urlparse(url=url)
    netloc_parts = parsed.netloc.split(".")
    exclude_domains = ["www", "au"]

    netloc_parts = [
        n for n in netloc_parts
        if n not in exclude_domains
    ]

    return netloc_parts[0]


def filter_trackers_by_urls(
    required_urls: list[str]
) -> list[TrackerConfig]:
    ts = []
    trackers = load_tracker_configs()

    for t in trackers:
        for u in required_urls:
            name = get_url_base_name(u)
            if t.name == name:
                ts.append(t)
            else:
                continue

    return ts


class TrackerConfig(NamedTuple):
    url: str
    parser: str = "JSONParser"
    sqlite_root: str = settings.SQLITE_DB_ROOT

    @property
    def base_url(self) -> str:
        if self.url.endswith("/"):
            return self.url.rstrip("/")
        else:
            return self.url

    @property
    def products_json_url(self) -> str:
        return self.base_url + "/products.json"

    @property
    def products_url(self) -> str:
        return self.base_url + "/products"

    @property
    def name(self) -> str:
        return get_url_base_name(self.url)

    @property
    def sqlite_uri(self) -> str:
        db_path="data/sqlite/"+self.name+".db"
        if pathlib.Path(db_path).exists() == False:            
            args = [
                "sqlite3",
                f"{self.name}.db",
                ".databases"
            ]
            subprocess.run(args)
            read_sql_agrs=[
                "sqlite3",
                f"{self.sqlite_root}/baseSQL.sql",
                f".read "
            ]
            subprocess.run(read_sql_agrs)
        return f"sqlite:///{self.sqlite_root}/{self.name}.db"

    @property
    def parser_class(
        self
    ) -> type[parsers.HTMLParser | parsers.JSONParser]:
        subclasses = parsers.HTMLParser.__subclasses__()
        for s in subclasses:
            if s.__name__ == self.parser:
                return s
            else:
                continue

        return parsers.JSONParser


def load_tracker_configs() -> list[TrackerConfig]:
    tracker_json_configs = pathlib.Path(
        settings.TRACKERS_CONFIG_FILEPATH
    )

    with tracker_json_configs.open(mode="r", encoding="utf-8") as fp:
        base_config = json.load(fp=fp)

        return [
            TrackerConfig(
                url=tracker["url"],
                parser=tracker["parser"]
            )
            for tracker in base_config["trackers"]
        ]


def get_config_by_name(
    trackers: list[TrackerConfig], name: str
) -> TrackerConfig | None:
    for t in trackers:
        if t.name == name:
            return t
        else:
            continue

    return None


def main(argv: Sequence[str] | None = None) -> int:
    aparser = argparse.ArgumentParser()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
