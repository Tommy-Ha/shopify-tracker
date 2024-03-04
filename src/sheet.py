from __future__ import annotations

import pathlib
import argparse
import dataclasses
import json
import time

from typing import Sequence

import pandas
import gspread
from gspread.worksheet import Worksheet
from gspread.spreadsheet import Spreadsheet
from gspread.exceptions import WorksheetNotFound
from gspread.utils import rowcol_to_a1

from src import logger
from src import inventory
from src import tracker
from src.config import settings
from src.db import utils


logger.init_logger()
custom_logger = logger.get_logger("sheet")


def init_spreadsheet(
    config: SpreadSheetConfig
) -> Spreadsheet:
    client = gspread.service_account(
        filename=pathlib.Path("creds/google-sheet-api.json").absolute(),
    )

    wb = client.open_by_key(key=config.key_id)
    custom_logger.info(msg=f"gspread: {config.key_id} initialized")

    return wb


@dataclasses.dataclass
class SheetDimension:
    columns: int = 26
    rows: int = 1000
    start_column: int = 1
    start_row: int = 1

    @property
    def range(self) -> str:
        start_cell = rowcol_to_a1(
            row=self.start_row,
            col=self.start_column
        )
        end_cell = rowcol_to_a1(
            row=(
                self.rows
                if self.start_row == 1
                else self.start_row+self.rows
            ),
            col=(
                self.columns
                if self.start_column == 1
                else self.start_column+self.columns
            )
        )

        _range = start_cell + ":" + end_cell

        return str(_range)


@dataclasses.dataclass
class SheetConfig:
    name: str
    position: int
    dimension: SheetDimension = SheetDimension()

    @property
    def sqlite_uri(self) -> str:
        return f"sqlite:///{settings.SQLITE_DB_ROOT}/{self.name}.db"


@dataclasses.dataclass
class SpreadSheetConfig:
    key_id: str
    tracker_urls: list[str]

    def _get_worksheet_configs(
        self, tracker_urls: list[str]
    ) -> list[SheetConfig]:
        sheet_configs = []
        for i, url in enumerate(tracker_urls, start=1):
            name = tracker.get_url_base_name(url)
            sheet_configs.append(
                SheetConfig(name=name, position=i)
            )
        return sheet_configs

    @property
    def sheets(self) -> list[SheetConfig]:
        return self._get_worksheet_configs(
            tracker_urls=self.tracker_urls
        )


def get_spreadsheet_configs() -> list[SpreadSheetConfig]:
    sheet_json_configs = pathlib.Path(
        settings.SHEETS_CONFIG_FILEPATH
    )
    with sheet_json_configs.open(mode="r", encoding="utf-8") as fp:
        base_config = json.load(fp=fp)

        return [
            SpreadSheetConfig(
                key_id=s["key_id"],
                tracker_urls=s["tracker_urls"]
            )
            for s in base_config["spreadsheets"]
        ]


class SheetWriter:
    def __init__(
        self,
        data: pandas.DataFrame,
        wb: Spreadsheet,
        sheet_config: SheetConfig
    ) -> None:
        self.data = data
        self.columns = self.data.columns
        self.config = sheet_config
        self.wb = wb
        self.sheet = self.get_sheet()

    def get_sheet(self) -> Worksheet:
        try:
            ws = self.wb.worksheet(self.config.name)
            return ws

        except WorksheetNotFound:
            ws = self.wb.add_worksheet(
                title=self.config.name,
                rows=self.config.dimension.rows,
                cols=self.config.dimension.columns,
            )
            return ws

    def format_banner(self) -> None:
        logo_range = SheetDimension(
            rows=2,
            columns=0,
            start_column=3
        )
        self.sheet.update_acell(
            label="C1",
            value=self.config.name.upper()
        )
        self.sheet.merge_cells(
            name=logo_range.range,
            merge_type="MERGE_COLUMNS"
        )
        self.sheet.format(
            ranges=logo_range.range,
            format={
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
                "textFormat": {
                  "foregroundColor": {
                    "red": 0,
                    "green": 0,
                    "blue": 0
                  },
                  "fontSize": 20,
                  "bold": True
                }
            }
        )
        self.sheet.hide_columns(
            start=0,
            end=2
        )
        self.sheet.update(
            values=[
                [
                    "First Updated:",
                    self.data["first_updated"].min()
                ],
                [
                    "Last Updated:",
                    self.data["last_updated"].max()
                ]
            ],
            range_name="D1:E2"
        )

    def format(self) -> None:
        self.config.dimension.columns = len(self.data.columns)
        self.config.dimension.rows = len(self.data)
        self.config.dimension.start_row = 3

        self.sheet.set_basic_filter(
            name=self.config.dimension.range
        )
        self.sheet.freeze(rows=3)
        self.sheet.hide_gridlines()

    def write(self) -> None:
        self.sheet.clear()

        self.format()
        self.format_banner()

        self.sheet.update(
            values=(
                [self.data.columns.tolist()]
                + self.data.values.tolist()
            ),
            raw=True,
            range_name=self.config.dimension.range
        )

        custom_logger.info(
            msg=f"done populating {self.config.name} with {len(self.data)} rows"
        )


def run_all_sheets(configs: list[SpreadSheetConfig]) -> None:
    for config in configs:
        wb = init_spreadsheet(config)

        for sheet_config in config.sheets:
            try:
                engine = utils.get_engine(
                    url=sheet_config.sqlite_uri
                )

                data = inventory.compute_inventory(engine)

                writer = SheetWriter(
                    data=data,
                    wb=wb,
                    sheet_config=sheet_config
                )
                writer.write()
                time.sleep(6)

            except Exception as e:
                print(e)
                pass


def run_sheets(config: SpreadSheetConfig) -> None:
    wb = init_spreadsheet(config)

    for sheet_config in config.sheets:
        try:
            engine = utils.get_engine(
                url=sheet_config.sqlite_uri
            )

            data = inventory.compute_inventory(engine)

            writer = SheetWriter(
                data=data,
                wb=wb,
                sheet_config=sheet_config
            )
            writer.write()

        except Exception as e:
            print(e)
            pass


def main(argv: Sequence[str] | None = None) -> int:
    aparser = argparse.ArgumentParser()
    aparser.add_argument(
        "--list-spreadsheets", "--list",
        action="store_true"
    )
    aparser.add_argument(
        "--run-all-sheets", "--run-all",
        action="store_true"
    )
    aparser.add_argument(
        "--run-sheet-id", "--run-id",
        action="store",
        type=int
    )

    args = aparser.parse_args(argv)
    configs = get_spreadsheet_configs()

    if args.list_spreadsheets:
        for i, config in enumerate(configs, start=1):
            print(f"id: {i} | sheet: {config.key_id}")

            for j, s in enumerate(config.tracker_urls):
                print(j, s)

    if args.run_all_sheets:
        run_all_sheets(configs)

    if args.run_sheet_id:
        run_sheets(
            config=configs[args.run_sheet_id-1]
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
