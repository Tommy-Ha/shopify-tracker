from __future__ import annotations

import argparse
import asyncio
from typing import Sequence

import httpx

from src import tracker
from src import sheet
from src import inventory
from src import parser
from src.config import settings
from src.db import utils


TRACKER_CONFIGS = parser.load_tracker_configs()


async def run_all_trackers(
    skip_products: bool = False,
) -> None:
    sem = asyncio.Semaphore(value=settings.MAX_ASYNC_WORKER)
    client = httpx.AsyncClient()

    for cfg in TRACKER_CONFIGS:
        tracker_runner = tracker.TrackerRunner(
            sem=sem,
            client=client,
            tracker_config=cfg
        )

        await tracker_runner.run(skip_products)
        await asyncio.sleep(10)


async def run_tracker(
    name: list[str] | None = None
) -> None:
    sem = asyncio.Semaphore(value=settings.MAX_ASYNC_WORKER)
    client = httpx.AsyncClient()

    if name is None:
        await run_all_trackers()

    else:
        cfgs = []
        for n in name:
            cfg = parser.get_config_by_name(TRACKER_CONFIGS, n)
            assert cfg is not None, f"tracker {name=} not found"

            cfgs.append(cfg)

        for cfg in cfgs:
            tracker_runner = tracker.TrackerRunner(
                sem=sem,
                client=client,
                tracker_config=cfg
            )
            await tracker_runner.run()


async def run_sheets() -> None:
    sheet_configs = parser.load_sheet_configs()
    wb = sheet.init_google_sheets()

    for tcfg, scfg in zip(TRACKER_CONFIGS, sheet_configs):
        engine = utils.get_engine(url=tcfg.sqlite_uri)
        data = inventory.compute_inventory(engine)

        sheet_writer = sheet.SheetWriter(
            data=data,
            wb=wb,
            sheet_config=scfg
        )

        sheet_writer.write()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run-all-trackers", "--run-all", "-rat",
        action="store_true",
        help="run all trackers"
    )

    parser.add_argument(
        "--run-tracker", "--run",
        action="append"
    )

    parser.add_argument(
        "--run-trackers-inventory", "-rti",
        action="store_true",
        help="run trackers without re-extracting products.json pages"
    )

    parser.add_argument(
        "--list-trackers", "--list", "-l",
        action="store_true",
        help="list all pre-configured trackers"
    )

    parser.add_argument(
        "--run-sheets", "-rs",
        action="store_true",
        help="calculate inventory and populate to google sheets"
    )

    args = parser.parse_args(argv)

    if (args.run_all_trackers
        and args.run_trackers_inventory):
        asyncio.run(run_all_trackers(skip_products=True))

    elif (args.run_all_trackers
        and not args.run_trackers_inventory):
        asyncio.run(run_all_trackers(skip_products=False))

    if args.list_trackers:
        for cfg in TRACKER_CONFIGS:
            print(f"{cfg.name} | {cfg}")

    if args.run_tracker:
        asyncio.run(run_tracker(name=args.run_tracker))

    if args.run_sheets:
        asyncio.run(run_sheets())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
