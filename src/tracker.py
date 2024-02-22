from __future__ import annotations

import asyncio
import random

import httpx
import tenacity

from sqlalchemy import Engine

from src import headers
from src import logger
from src import parser
from src.db import models
from src.db import utils
from src.config import settings

logger.init_logger()

HEADERS_HANDLER = headers.HeadersHandler()


def custom_retry_callback(retry_state: tenacity.RetryCallState) -> None:
    if retry_state.attempt_number < settings.MAX_RETRIES:
        logger.get_logger("tenacity").info(
            msg=f"retrying: {retry_state.attempt_number} time(s)"
        )
    else:
        logger.get_logger("tenacity").warning(
            msg=f"reached retries limit: {retry_state.attempt_number} time(s)"
        )


def async_sleep_random(
    fixed: int = 4,
    min: int = 0,
    max: int = 3
) -> int:
    delay = random.randint(a=min, b=max)
    return fixed + delay


def response_has_no_products(data: dict) -> bool:
    if len(data["products"]) == 0:
        return True
    else:
        return False


@tenacity.retry(
    stop=tenacity.stop_after_attempt(
        max_attempt_number=settings.MAX_RETRIES
    ),
    wait=(
        tenacity.wait_fixed(settings.RETRY_SLEEP_DELAY)
        + tenacity.wait_random_exponential(
            multiplier=0.5,
            max=60
        )
    ),
    after=custom_retry_callback
)
async def async_request(
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
            logger.get_logger("general").warning(
                msg=f"emptry response {url}"
            )
        
        return response

    except httpx.HTTPStatusError as e:
        logger.get_logger("httpx").warning(
            msg=f"failed with status: {e.response.status_code} {url}"
        )
        if e.response.status_code == 404:
            pass

        elif e.response.status_code == 430:
            await asyncio.sleep(settings.ASYNC_SLEEP_DELAY)
            pass

        else:
            raise tenacity.TryAgain

    except httpx.ReadTimeout:
        logger.get_logger("httpx").error(msg=f"failed with timeout: {url}")
        raise tenacity.TryAgain

    except httpx.RemoteProtocolError:
        logger.get_logger("httpx").error(msg=f"server not response: {url}")
        raise tenacity.TryAgain

    except httpx.UnsupportedProtocol:
        logger.get_logger("httpx").error(msg=f"unsupported protocol: {url}")
        raise tenacity.TryAgain


class TrackerRunner:
    def __init__(
        self,
        client: httpx.AsyncClient,
        sem: asyncio.Semaphore,
        tracker_config: parser.TrackerConfig
    ) -> None:
        self.client = client
        self.sem = sem
        self.config = tracker_config

    async def proces_one(
        self,
        product: dict,
        engine: Engine
    ) -> None:
        async with self.sem:
            url = ""

            if "JSON" in self.config.parser:
                url = product["url"] + ".json" 
            elif "HTML" in self.config.parser:
                url = product["url"]

            custom_headers = HEADERS_HANDLER.get_headers(
                url=url
            )

            response = await async_request(
                client=self.client,
                method="GET",
                url=url,
                headers=custom_headers
            )
            assert response is not None

            values = []

            custom_parser = self.config.parser_class(
                response=response
            )
            values = custom_parser.parse()

            utils.upsert_many(
                engine=engine,
                values=values,
                instance=models.ShopifyInventory
            )

            if self.sem.locked():
                sleep_delay = async_sleep_random(
                    fixed=settings.ASYNC_SLEEP_DELAY
                )
                await asyncio.sleep(sleep_delay)

        return

    async def process_many(
        self, engine: Engine
    ) -> None:
        page_number = 1

        while True:
            params = {
                "json": "true",
                "limit": 250,
                "page": page_number
            }

            sleep_delay = async_sleep_random(
                fixed=settings.ASYNC_SLEEP_DELAY
            )
            await asyncio.sleep(sleep_delay)

            response = await async_request(
                client=self.client,
                method="GET",
                url=self.config.products_json_url,
                params=params
            )

            assert response is not None

            if response_has_no_products(response.json()):
                break

            pparser = parser.ShopifyProductsParser(
                response=response.json(),
                tracker_config=self.config
            )
            pparser.parse_products()

            utils.upsert_many(
                engine=engine,
                values=pparser.products,
                instance=models.ShopifyProduct
            )

            utils.upsert_many(
                engine=engine,
                values=pparser.variants,
                instance=models.ShopifyVariant
            )

            page_number += 1

    async def run(
        self, skip_products: bool = False
    ) -> None:
        engine = utils.get_engine(url=self.config.sqlite_uri)

        utils.init_database(
            engine=engine, metadata=models.ShopifyBase.metadata
        )

        if not skip_products:
            await self.process_many(engine)

        product_items = utils.select_by_column_names(
            engine=engine,
            table_name="product",
            colnames=["id", "url"]
        )

        try:
            tasks = [
                asyncio.create_task(
                    self.proces_one(product=p, engine=engine)
                )
                for p in product_items
            ]

            await asyncio.gather(*tasks)

        except tenacity.RetryError:
            pass


async def main() -> None:
    configs = parser.load_tracker_configs()

    SEM = asyncio.Semaphore(value=settings.MAX_ASYNC_WORKER)
    CLIENT = httpx.AsyncClient()

    tracker = TrackerRunner(
        sem=SEM, client=CLIENT, tracker_config=configs[2]
    )

    await tracker.run()


if __name__ == "__main__":
    asyncio.run(main())
