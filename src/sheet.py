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
        filename=pathlib.Path("src/config/creds.json").absolute(),
    )

    wb = client.open_by_key(key=config.key_id)
    custom_logger.info(msg=f"gspread: {config.key_id} initialized")

    return wb


@dataclasses.dataclass
class SheetDimension:
    columns: int = 26
    rows: int = 100000
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

    def write(self) -> None:
        self.sheet.clear()

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


class PivotTableCreatetor:
    def __init__(self, first_update,last_update, wb: Spreadsheet, sheet_config: SheetConfig) -> None:
        self.first_update = first_update
        self.last_update = last_update
        self.wb = wb
        self.sheet_config = sheet_config

    def get_sheet(self, name=None):
        try:
            if name:
                return self.wb.worksheet(name)
            return self.wb.worksheet(self.sheet_config.name)
        except Exception:
            return None

    def create_new_sheet(self):
        new_sheet_name = "p_" + self.sheet_config.name
        if not self.get_sheet(new_sheet_name):
            body = {
                "requests": [{"addSheet": {"properties": {"title": new_sheet_name}}}]
            }
            response = self.wb.batch_update(body=body)
            return response["replies"][0]["addSheet"]["properties"]["sheetId"]
        return self.wb.worksheet(new_sheet_name).id

    def write(self):

        sheet_id = self.create_new_sheet()
        source_sheet_id = self.get_sheet().id
        if sheet_id:
            body = {
                "requests": [
                    {
                        "updateCells": {
                            "rows": [
                                {
                                    "values": [
                                        {
                                            "pivotTable": {
                                                "source": {
                                                    "sheetId": source_sheet_id,
                                                    "startRowIndex": 0,
                                                    "startColumnIndex": 0,
                                                    "endRowIndex": 1000,
                                                    "endColumnIndex": 7,
                                                },
                                                "rows": [
                                                    {
                                                        "sourceColumnOffset": 0,
                                                        "showTotals": True,
                                                        "sortOrder": "DESCENDING",
                                                        "valueBucket": {},
                                                    },
                                                    {
                                                        "sourceColumnOffset": 1,
                                                        "showTotals": True,
                                                        "sortOrder": "DESCENDING",
                                                        "valueBucket": {},
                                                    },
                                                    {
                                                        "sourceColumnOffset": 3,
                                                        "showTotals": False,
                                                        "sortOrder": "DESCENDING",
                                                        "valueBucket": {},
                                                    },
                                                    {
                                                        "sourceColumnOffset": 4,
                                                        "showTotals": False,
                                                        "sortOrder": "DESCENDING",
                                                        "valueBucket": {},
                                                    },
                                                ],
                                                "values": [
                                                    {
                                                        "summarizeFunction": "SUM",
                                                        "sourceColumnOffset": 5,
                                                    },
                                                    {
                                                        "summarizeFunction": "SUM",
                                                        "sourceColumnOffset": 6,
                                                    },
                                                ],
                                                "valueLayout": "HORIZONTAL",
                                            }
                                        }
                                    ]
                                }
                            ],
                            "start": {
                                "sheetId": sheet_id,
                                "rowIndex": 3,
                                "columnIndex": 0,
                            },
                            "fields": "pivotTable",
                        }
                    },
                    {
                        "updateCells": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": 0,
                                "startColumnIndex": 0,
                                "endRowIndex": 1,
                                "endColumnIndex": 1,
                            },
                            "rows": [
                                {
                                    "values": [
                                        {"userEnteredValue": {"stringValue": self.sheet_config.name}}                                       
                                    ]
                                }
                            ],
                            "fields": "userEnteredValue",
                        }
                    },
                    {
                        "repeatCell": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": 0,
                                "startColumnIndex": 0,
                                "endRowIndex": 1,
                                "endColumnIndex": 1,
                            },
                            "cell": {
                                "userEnteredFormat": {
                                    "textFormat": {
                                        "fontSize": 24 
                                    }
                                }
                            },
                            "fields": "userEnteredFormat.textFormat.fontSize",
                        }
                    },
                ]
            }
            self.wb.batch_update(body=body)
            self.format_banner()
            self.wb.worksheet(self.sheet_config.name).hide()        

    def format_banner(self):
        self.wb.values_update(
            range="p_" + self.sheet_config.name + "!D1:E3",
            params={"valueInputOption": "USER_ENTERED"},
            body={"values": [["Fist update", self.first_update],
                             ["Last update", self.last_update],
                             ["Sheet Updated", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())]                             
                             ]},
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
                pivot_table = PivotTableCreatetor(
                    first_update=data["first_updated"].min(),
                    last_update=data["last_updated"].max(),
                    sheet_config=sheet_config,
                    wb=wb
                )
                pivot_table.write()

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
