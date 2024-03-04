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
from typing import Protocol
from typing import runtime_checkable
from typing import Any

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
        response: dict[str, Any],
    ):
        self.response = response
        self.products: list[dict] = []
        self.variants: list[dict] = []

    def parse_products(self, base_url: str) -> None:
        product_items = self.response["products"]
        assert len(product_items) > 0

        for p in product_items:
            product = filter_dict_items(
                item=p, includes=_REQUIRED_PRODUCT_COLUMNS
            )

            handle = product.get("handle")
            if handle is not None:
                product_config = Product(
                    base_url=base_url,
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
                item=v, includes=_REQUIRED_VARIANT_COLUMNS
            )
            self.variants.append(variant)


class JSONParser:
    def parse(self, markup: str | bytes) -> list[dict]:
        variant_details = json.loads(markup)["product"]["variants"]
        inventory = []

        for v in variant_details:
            amount = filter_dict_items(
                item=v, includes=_REQUIRED_INVENTORY_COLUMNS
            )
            amount["variant_id"] = amount["id"]
            amount.pop("id")

            inventory.append(amount)

        return inventory


# custom parser
@runtime_checkable
class HTMLParser(Protocol):
    def parse(self, markup: str | bytes) -> list[dict]:
        ...


class HTMLSwymParser(HTMLParser):
    def filter(self, soup: bs4.BeautifulSoup) -> list[str]:
        s = soup.select(selector="script#swym-snippet")[0]
        raw_variants = []

        for i in str(s).split(";"):
            if "SwymProductVariants[" in i:
                raw_variants.append(i)

        return raw_variants

    def parse(self, markup: str | bytes) -> list[dict]:
        soup = bs4.BeautifulSoup(
            markup=markup, features="html.parser"
        )
        inventory = []

        for v in self.filter(soup):
            p = v.replace("\n", "").strip().split(",")

            variant_id = 0
            inventory_quantity = 0

            for i in p:
                if "stk" in i:
                    q = i.strip().rstrip(",").lstrip("stk: ")
                    inventory_quantity = int(q)

                if "SwymProductVariants" in i:
                    t = re.search(
                        pattern=r"(?<=\[).+?(?=\])",
                        string=str(i)
                    )
                    
                    assert t is not None
                    s, e = t.span()
                    variant_id = int(i[s:e])

            inventory.append(
                {
                    "variant_id": variant_id,
                    "inventory_quantity": inventory_quantity
                }
            )

        return inventory


class HTMLGloboParser(HTMLParser):
    def filter(self, soup: bs4.BeautifulSoup) -> list[str]:
        selector = "script[type='text/javascript'][hs-ignore]"
        script = soup.select(selector)[0]
        raw_variants = []

        for i in str(script.text).split(";"):
            if ("GloboPreorderParams.product.variants" in i
                and "inventory_policy" not in i
                and "metafields" not in i
            ):
                raw_variants.append(i)

        return raw_variants

    def parse(self, markup: str | bytes) -> list[dict]:
        inventory = []
        soup = bs4.BeautifulSoup(
            markup=markup, features="html.parser"
        )
        vs = self.filter(soup)
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
    def filter(self, soup: bs4.BeautifulSoup) -> list[str]:
        raw_variants = []

        scripts = soup.find_all(name="script")
        ss = [
            s
            for s in scripts
            if "Spurit.CountdownTimer.snippet.productId" in s.text
        ]
        script = ss[-1]

        for i in str(script.text).split(";"):
            if "variantStock[" in i:
                raw_variants.append(i)

        return raw_variants

    def parse(self, markup: str | bytes) -> list[dict]:
        soup = bs4.BeautifulSoup(
            markup=markup, features="html.parser"
        )

        inventory = []
        for v in self.filter(soup):
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


class HTMLBISParser(HTMLParser):
    def filter(self, soup: bs4.BeautifulSoup) -> list[str]:
        script, = soup.select("script#back-in-stock-helper")
        f = []

        for line in str(script.text).split(";"):
            if "_BISConfig.product.variants[" in line:
                f.append(line.strip())
        return f

    def _parse_variant_ids(
        self, soup: bs4.BeautifulSoup
    ) -> list[int | str]:
        variant_ids = []
        script, = soup.select("script#em_product_variants")
        variants = json.loads(s=script.text)
        
        for v in variants:
            variant_ids.append(v["id"])
            
        return variant_ids

    def parse(self, markup: str | bytes) -> list[dict]:
        soup = bs4.BeautifulSoup(
            markup=markup, features="html.parser"
        )
        variant_ids = self._parse_variant_ids(soup)
        vs = self.filter(soup)

        inventory = []

        for v, i in zip(variant_ids, vs):
            inventory.append(
                {
                    "variant_id": v,
                    "inventory_quantity": i.split(" = ")[-1]
                }
            )
        return inventory


class HTMLSasoParser(HTMLParser):
    def parse(self, markup: str | bytes) -> list[dict]:
        soup = bs4.BeautifulSoup(
            markup=markup, features="html.parser"
        )
        raw_variants, = soup.select("div.product div[data-product-form]")

        inventory: list[dict] = []

        try:
            data = json.loads(raw_variants.attrs["data-product"])
            
            for v in data["variants"]:
                inventory.append(
                    {
                        "variant_id": v["id"],
                        "inventory_quantity": v["inventory_quantity"]
                    }
                )

        except json.JSONDecodeError:
            inventory.append(
                {"variant_id": 0, "inventory_quantity": 0}
            )

        return inventory


class HTMLGeneralParser(HTMLParser):
    def filter(self, soup: bs4.BeautifulSoup) -> str:
        script, = soup.select("script#product-data")
        return script.text

    def parse(self, markup: str | bytes) -> list[dict]:
        soup = bs4.BeautifulSoup(
            markup=markup, features="html.parser"
        )
        inventory: list[dict] = []

        try:
            raw_variants = json.loads(s=self.filter(soup))

            for v in raw_variants["product"]["variants"]:
                inventory.append(
                    {
                        "variant_id": v["id"],
                        "inventory_quantity": v["inventory_quantity"]
                    }
                )

        except json.JSONDecodeError:
            inventory.append(
                {"variant_id": 0, "inventory_quantity": 0}
            )

        return inventory


class HTMLOptParser(HTMLParser):
    def filter(self, soup: bs4.BeautifulSoup) -> str:
        scripts = soup.select("script")
        ss = []

        for s in scripts:
            if "var PRODUCT_JSON = fucntion() {" in s.text:
                ss = s.text.split("\n")
            else:
                continue

        raw_variants = ""
        for line in ss:
            if ("p_json = {" in line and "var p_json" not in line):
                raw_variants = line.strip().split(" = ")[-1]
            else:
                continue

        return raw_variants

    def parse(self, markup: str | bytes) -> list[dict]:
        soup = bs4.BeautifulSoup(
            markup=markup, features="html.parser"
        )
        inventory = []

        try:
            raw_variants = json.loads(s=self.filter(soup))
            for v in raw_variants["variants"]:
                inventory.append(
                    {
                        "variant_id": v.attrs["value"],
                        "inventory_quantity": v.attrs["data-inventory-quantity"]
                    }
                )

        except json.JSONDecodeError:
            inventory.append(
                {"variant_id": 0, "inventory_quantity": 0}
            )

        return inventory


class HTMLProdParser(HTMLParser):
    def filter(self, soup: bs4.BeautifulSoup) -> str:
        script, = soup.select("script#ProductJson-product-template")
        return script.text

    def parse(self, markup: str | bytes) -> list[dict]:
        soup = bs4.BeautifulSoup(
            markup=markup, features="html.parser"
        )
        inventory: list[dict] = []

        try:
            raw_variants = json.loads(s=self.filter(soup))

            for v in raw_variants["variants"]:
                inventory.append(
                    {
                        "variant_id": v["id"],
                        "inventory_quantity": v["inventory_quantity"]
                    }
                )

        except json.JSONDecodeError:
            inventory.append(
                {"variant_id": 0, "inventory_quantity": 0}
            )

        except ValueError:
            inventory.append(
                {"variant_id": 0, "inventory_quantity": 0}
            )

        return inventory


class HTMLCamoParser(HTMLParser):
    def filter(
        self, soup: bs4.BeautifulSoup
    ) -> tuple[list, list]:
        script, = soup.select(
            selector="script[class='camouflage-script']:not([src])"
        )

        raw_variants = ""
        variants = []
        inventory = []

        for line in script.text.split(";"):
            if "const camouflage_product" in line and "hide_oos_variant_qty" not in line:
                raw_variants = line.split(" = ")[-1]

            elif "camouflage_product.hide_oos_variant_qty = [" in line:
                array_string = line.split("\n")[-1].split(" = ")[-1]
                for i in array_string[1:-1].split(","):
                    inventory.append(i)

        vs = json.loads(raw_variants)
        for v in vs["variants"]:
            variants.append({"variant_id": v["id"]})

        return variants, inventory

    def parse(self, markup: str | bytes) -> list[dict]:
        soup = bs4.BeautifulSoup(markup=markup, features="html.parser")
        inventory: list[dict] = []

        try:
            variants, inventory_array = self.filter(soup)
            for v, i in zip(variants, inventory_array):
                v.update({"inventory_quantity": i})
                inventory.append(v)

        except json.JSONDecodeError:
            inventory.append(
                {"variant_id": 0, "inventory_quantity": 0}
            )
        except ValueError:
            inventory.append(
                {"variant_id": 0, "inventory_quantity": 0}
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
