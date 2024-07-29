from __future__ import annotations

import argparse
import asyncio
import random
import concurrent.futures
import time

import httpx
import tenacity

from typing import Sequence
from src import logger
from src import parsers
from src import tracker

from src.db import models
from src.db import utils
from src.config import settings
import time
import math

TRACKER_CONFIGS = tracker.load_tracker_configs()


def async_sleep_random(
    fixed: int = 4,
    min: int = 0,
    max: int = 3
) -> int:
    delay = random.randint(a=min, b=max)
    return fixed + delay




def get_hash(e:str):
    u = -559038737
    r = 1103547991

    for n in range(len(e)):
        t = ord(e[n])
        u = (u ^ t) * 2654435761 & 0xFFFFFFFF
        r = (r ^ t) * 1597334677 & 0xFFFFFFFF

    u = ((u ^ (u >> 16)) * 2246822507 & 0xFFFFFFFF) ^ ((r ^ (r >> 13)) * 3266489909 & 0xFFFFFFFF)
    r = ((r ^ (r >> 16)) * 2246822507 & 0xFFFFFFFF) ^ ((u ^ (u >> 13)) * 3266489909 & 0xFFFFFFFF)

    return (4294967296 * (2097151 & r)) + (u & 0xFFFFFFFF)    


class TrackerRunner:
    def __init__(
        self,
        tracker_config: tracker.TrackerConfig
    ) -> None:
        self.client = httpx.AsyncClient()

        self.config = tracker_config
        self.llogger = logger.get_logger("tracker")
        self.engine = utils.get_engine(self.config.sqlite_uri)
        
        utils.LocalSession.configure(bind=self.engine)
        self.session = utils.LocalSession

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(
            max_attempt_number=settings.MAX_RETRIES
        ),
        wait=(
            tenacity.wait_fixed(settings.RETRY_SLEEP_DELAY)
            + tenacity.wait_random_exponential(
                multiplier=10,
                max=120
            )
        ),
    )
    async def async_request(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        **kwargs
    ) -> httpx.Response | None:

        try:
            response = await client.request(
                method=method, url=url, **kwargs
            )
            response = response.raise_for_status()

            if response is None:
                self.llogger.warning(
                    msg=f"http request: emptry response {url}"
                )
            else:
                params = {
                    k: v
                    for k, v in kwargs.items()
                    if k != "headers"
                }
                self.llogger.info(
                    msg=f"http request ({response.status_code}): "
                        f"{method} {url} {params}"
                )
                return response

        except httpx.HTTPStatusError as e:
            self.llogger.warning(
                msg=f"http request ({e.response.status_code}): "
                    f"{method} {url}",
                extra={"url": url, "status_code": e.response.status_code}
            )
            if e.response.status_code == 404:
                return e.response

            elif e.response.status_code == 301:
                return e.response

            elif e.response.status_code == 430:
                await asyncio.sleep(120)
                raise tenacity.TryAgain

            else:
                raise tenacity.TryAgain

        except httpx.ReadTimeout as e:
            self.llogger.error(msg=f"failed with timeout: {url}")
            raise tenacity.TryAgain

        except httpx.RemoteProtocolError:
            self.llogger.error(msg=f"server not response: {url}")
            raise tenacity.TryAgain
        except Exception:
            self.llogger.error(msg=f"server not response: {url}")

    async def proces_one(
        self, product: dict, sem: asyncio.Semaphore
    ) -> None:
        async with sem:
            url = ""
            if "JSON" in self.config.parser:
                url = product["url"] + ".json" 
            elif "HTML" in self.config.parser:
                if "HTMLEasyStockParser" == self.config.parser:
                    q = product["handle"]
                    t=str(int(time.time()*1000))
                    s='dM1xupB07XNx'
                    hash_prod = get_hash(q+t+s)
                    
                    url = self.config.base_url+"/apps/easystock/?q={}&sign={}&timeh={}".format(q,hash_prod,t)
                else:
                    url = product["url"]
            

            if sem.locked():
                delay = async_sleep_random(
                    fixed=40,
                    min=1,
                    max=10
                )
                await asyncio.sleep(delay)

            await asyncio.sleep(0.5)
            response = await self.async_request(
                client=self.client,
                method="GET",
                url=url,
                headers=settings.SHARED_HEADERS
            )

            if response is not None:
                if (
                    response.status_code != 200
                    and response.status_code != 430
                ):
                    value = {
                        "id": product["id"],
                        "status_code": response.status_code
                    }
                    utils.update_one(
                        session=self.session(),
                        value=value,
                        instance=models.ShopifyProduct
                    )

                elif response.status_code == 200:
                    custom_parser = self.config.parser_class()
                    values = custom_parser.parse(markup=response.text)

                    utils.upsert_many(
                        session=self.session(),
                        values=values,
                        instance=models.ShopifyInventory
                    )

    def _has_no_products(self, data: dict) -> bool:
        if len(data["products"]) == 0:
            return True
        else:
            return False

    async def process_many(self) -> None:
        page_number = 1

        while True:
            params = {
                "json": "true",
                "limit": 250,
                "page": page_number
            }

            delay = async_sleep_random(
                fixed=settings.ASYNC_SLEEP_DELAY
            )
            await asyncio.sleep(delay)

            response = await self.async_request(
                client=self.client,
                method="GET",
                url=self.config.products_json_url,
                params=params
            )

            if response is None:
                break

            if self._has_no_products(response.json()):
                break

            pparser = parsers.ShopifyProductsParser(
                response=response.json()
            )
            pparser.parse_products(base_url=self.config.base_url)

            utils.upsert_many(
                session=self.session(),
                values=pparser.products,
                instance=models.ShopifyProduct
            )

            utils.upsert_many(
                session=self.session(),
                values=pparser.variants,
                instance=models.ShopifyVariant
            )

            page_number += 1

    def get_todos(self) -> list[dict]:
        stmt = """
            SELECT id, url, handle
            FROM product
            WHERE status_code IN (200, 430);
        """
        todos = utils.execute_select_statement(
            session=self.session(),
            statement=stmt
        )

        return todos

    async def __call__(self) -> None:
        utils.init_database(
            engine=self.engine, metadata=models.ShopifyBase.metadata
        )

        await self.process_many()

        sem = asyncio.Semaphore(value=settings.MAX_ASYNC_WORKER)
        tasks = [
            asyncio.create_task(
                self.proces_one(product=product, sem=sem)
            )
            for product in self.get_todos()
        ]

        try:
            await asyncio.gather(*tasks)

        except tenacity.RetryError:
            pass

        finally:
            for task in tasks:
                task.cancel()

            await self.client.aclose()


def run_in_subprocess(
    config: tracker.TrackerConfig
) -> None:
    runner = TrackerRunner(tracker_config=config)
    asyncio.run(runner())


async def run_subprocesses() -> None:
    loop = asyncio.get_running_loop()

    with concurrent.futures.ProcessPoolExecutor(
        max_workers=2,
        initializer=logger.init_logger
    ) as executer:
        tasks = [
            loop.run_in_executor(
                executer,
                run_in_subprocess,
                config,
            )
            for config in TRACKER_CONFIGS
            if config.name in ["albinoandpreto", "ryderwear"]
        ]

        await asyncio.gather(*tasks)


async def run_all_trackers(
    configs: list[tracker.TrackerConfig]
) -> None:
    for config in configs:
        runner = TrackerRunner(
            tracker_config=config
        )

        await runner()
        await asyncio.sleep(10)


async def run_tracker_by_id(id: int) -> None:
    config = TRACKER_CONFIGS[id]
    runner = TrackerRunner(
        tracker_config=config
    )
    await runner()


def main(argv: Sequence[str] | None = None) -> int:
    aparser = argparse.ArgumentParser()
    aparser.add_argument(
        "--list-trackers", "--list", "-l",
        action="store_true",
        help="list all pre-configured trackers"
    )
    aparser.add_argument(
        "--run-all",
        action="store_true",
        help="run all trackers in configured order"
    )
    aparser.add_argument(
        "--run-from",
        action="store",
        type=int,
        help="run from <tracker_id> upto the last tracker in the list"
    )
    aparser.add_argument(
        "--run",
        action="store",
        type=int,
        help="run tracker by id. use `--list-trackers` for a list of available trackers"
    )
    aparser.add_argument(
        "--test", "-t",
        action="store",
        type=str,
        help="run tracker(s) with a test SQLITE_DB_ROOT"
    )

    args = aparser.parse_args(argv)
    if args.list_trackers:
        for i, config in enumerate(TRACKER_CONFIGS):
            print(f"| id: {i} | name: {config.name} | {config} |")

    if args.test is not None:
        print(f"updated {settings.SQLITE_DB_ROOT} -> {args.test}")
        settings.SQLITE_DB_ROOT = args.test

    if args.run_all:
        logger.init_logger()
        asyncio.run(run_all_trackers(TRACKER_CONFIGS))

    if args.run_from:
        logger.init_logger()
        configs = TRACKER_CONFIGS[args.run_from:]
        asyncio.run(run_all_trackers(configs))

    if args.run:
        start = time.monotonic()

        logger.init_logger()
        asyncio.run(run_tracker_by_id(args.run))

        print(f"done in {time.monotonic() - start} second(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
