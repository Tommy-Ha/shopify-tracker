from __future__ import annotations

import re
import json
import urllib.parse
import string
import math
import sys
import pathlib

import bs4
import httpx

from typing import NamedTuple

from src.config import settings


REQUIRED_PRODUCT_COLUMNS = [
    "id",
    "title",
    "vendor",
    "handle",
    "product_type",
    "variants",
]

REQUIRED_VARIANT_COLUMNS = [
    "id",
    "title",
    "product_id",
]

REQUIRED_INVENTORY_COLUMNS = [
    "id",
    "inventory_quantity"
]


class TrackerConfig(NamedTuple):
    url: str
    parser: str = "JSONParser"

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
        parsed = urllib.parse.urlparse(url=self.base_url)
        netloc_parts = parsed.netloc.split(".")
        exclude_domains = ["www", "au"]

        netloc_parts = [
            n for n in netloc_parts
            if n not in exclude_domains
        ]

        return netloc_parts[0]

    @property
    def sqlite_uri(self) -> str:
        return f"sqlite:///{settings.SQLITE_DB_ROOT}/{self.name}.db"

    @property
    def parser_class(
        self
    ) -> type[HTMLParser]:
        return getattr(
            sys.modules["src.parser"], self.parser
        )


class Product(NamedTuple):
    base_url: str
    handle: str

    @property
    def clean_handle(self) -> str:
        if self.handle.startswith("/"):
            return self.handle.lstrip("/")

        elif self.handle.endswith("/"):
            return self.handle.rstrip("/")

        else:
            return self.handle

    @property
    def url(self) -> str:
        return (
            self.base_url
            + "/products/"
            + self.clean_handle
        )

    @property
    def json_url(self) -> str:
        return self.url + ".json"


class SheetConfig(NamedTuple):
    name: str
    position: int
    width: int = 26
    height: int = 1000
    start_cell: str = "A1"

    @property
    def ranges(self) -> str:
        repeat = math.ceil(self.width/26)
        chars = list(string.ascii_uppercase)

        if repeat == 1:
            last_char = chars[self.width-1]
        
        else:
            hits = 0
            values = []

            for i, c in enumerate(chars * (repeat-1), start=0):
                if i % 26 == 0:
                    hits += 1

                values.append(chars[hits-1] + c)

            last_char = values[self.width-1-26]

        return str(
            self.start_cell
            + ":"
            + str(last_char)
            + str(self.height)
        )


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


def load_sheet_configs() -> list[SheetConfig]:
    tracker_configs = load_tracker_configs()

    return [
        SheetConfig(
            name=tcfg.name,
            position=i
        )
        for i, tcfg in enumerate(tracker_configs)
    ]

def filter_dict_items(
    item: dict, includes: list[str]
) -> dict:
    new_item = {}

    for key, value in item.items():
        if key in includes:
            new_item[key] = value

        else:
            continue

    return new_item


# parser classes
class ShopifyProductsParser:
    def __init__(
        self,
        response: dict[str, dict],
        tracker_config: TrackerConfig
    ):
        self.response = response
        self.config = tracker_config
        self.products = []
        self.variants = []

    def parse_products(self) -> None:
        product_items = self.response["products"]
        assert len(product_items) > 0

        for p in product_items:
            product = filter_dict_items(
                item=p, includes=REQUIRED_PRODUCT_COLUMNS
            )

            handle = product.get("handle")
            if handle is not None:
                product_config = Product(
                    base_url=self.config.base_url,
                    handle=handle
                )
                product.update({"url": product_config.url})

            variants = product.get("variants", [])

            if len(variants) > 0:
                self.parse_variants(variants)

            product.pop("variants")
            self.products.append(product)

    def parse_variants(self, variants: list[dict]) -> None:
        for v in variants:
            variant = filter_dict_items(
                item=v, includes=REQUIRED_VARIANT_COLUMNS
            )
            self.variants.append(variant)


class JSONParser:
    def __init__(
        self,
        response: httpx.Response
    ) -> None:
        self.response = response

    def parse(self) -> list[dict]:
        data = self.response.json()
        variant_details = data["product"]["variants"]
        inventory = []

        for v in variant_details:
            amount = filter_dict_items(
                item=v, includes=REQUIRED_INVENTORY_COLUMNS
            )
            amount["variant_id"] = amount["id"]
            amount.pop("id")

            inventory.append(amount)

        return inventory


# custom parser
class HTMLParser:
    def __init__(
        self,
        response: httpx.Response
    ) -> None:
        self.soup = bs4.BeautifulSoup(
            markup=response.text,
            features="html.parser"
        )

    def parse(self) -> list[dict]:
        ...


class HTMLSwymParser(HTMLParser):
    def __init__(
        self,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)

    def get_script(self, selector: str) -> bs4.PageElement:
            return self.soup.select(selector=selector)[0]

    def filter_script(self) -> list[str]:
        s = self.get_script("script#swym-snippet")
        raw_variants = []

        for i in str(s).split(";"):
            if "SwymProductVariants[" in i:
                raw_variants.append(i)

        return raw_variants

    def parse(self) -> list[dict]:
        inventory = []
        for v in self.filter_script():
            p = v.replace("\n", "").strip().split(",")

            variant_id = 0
            inventory_quantity = 0

            for i in p:
                if "stk" in i:
                    inventory_quantity = str(i).strip().rstrip(",").lstrip("stk: ")

                if "SwymProductVariants" in i:
                    variant_id = str(i)
                    t = re.search(
                        pattern=r"(?<=\[).+?(?=\])",
                        string=variant_id
                    )
                    
                    assert t is not None
                    s, e = t.span()
                    variant_id = variant_id[s:e]

            inventory.append(
                {
                    "variant_id": variant_id,
                    "inventory_quantity": inventory_quantity
                }
            )

        return inventory


class HTMLGloboParser(HTMLParser):
    def __init__(
        self,
        *args,
        **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)

    def get_script(self, selector: str) -> bs4.PageElement:
        return self.soup.select(selector)[0]

    def filter_script(self) -> list[str]:
        selector = "script[type='text/javascript'][hs-ignore]"
        script = self.get_script(selector)
        raw_variants = []

        for i in str(script.text).split(";"):
            if ("GloboPreorderParams.product.variants" in i
                and "inventory_policy" not in i
                and "metafields" not in i
            ):
                raw_variants.append(i)

        return raw_variants

    def parse(self) -> list[dict]:
        inventory = []
        vs = self.filter_script()
        ps = list(zip(vs[:-1], vs[1:]))[::2]

        for v in ps:
            variant_id = json.loads(s=v[0].split(" = ")[-1])["id"]
            inventory_quantity = v[1].split(" = ")[-1]

            inventory.append(
                {
                    "variant_id": variant_id,
                    "inventory_quantity": inventory_quantity
                }
            )

        return inventory


class HTMLSpuritParser(HTMLParser):
    def __init__(
        self,
        *args,
        **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)

    def get_script(self) -> bs4.PageElement:
        scripts = self.soup.find_all(name="script")
        scripts = [
            s
            for s in scripts
            if "Spurit.CountdownTimer.snippet.productId" in s.text
        ]
        return scripts[-1]

    def filter_script(self) -> list[str]:
        raw_variants = []
        script = self.get_script()

        for i in str(script.text).split(";"):
            if "variantStock[" in i:
                raw_variants.append(i)

        return raw_variants

    def parse(self) -> list[dict]:    
        inventory = []
        for v in self.filter_script():
            p = v.replace("\n", "").strip().split(",")
            variant_id = p[0].split(": ")[-1]
            inventory_quantity = p[1].split(": ")[-1]

            inventory.append(
                {
                    "variant_id": variant_id,
                    "inventory_quantity": inventory_quantity
                }
            )

        return inventory


def main() -> None:
    # response = pathlib.Path("data/json/products.json").read_text(encoding="utf-8")
    # response = json.loads(response)
    #
    # parser = ShopifyAllProductsParser(response)
    # p = parser.parse_products()
    # print(p)

    return


if __name__ == "__main__":
    main()
