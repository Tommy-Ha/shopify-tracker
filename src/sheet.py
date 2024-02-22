from __future__ import annotations

import pathlib

import pandas
import gspread
from gspread.worksheet import Worksheet
from gspread.spreadsheet import Spreadsheet
from gspread.exceptions import WorksheetNotFound

from src import logger
from src import inventory
from src import parser
from src.config import settings
from src.db import utils

def init_google_sheets() -> Spreadsheet:
    client = gspread.service_account(
        filename=pathlib.Path("creds.json").absolute(),
    )

    wb = client.open_by_key(key=settings.SHEET_KEY_ID)
    logger.get_logger("general").info(msg="spreadsheet initialized")

    return wb


class SheetWriter:
    def __init__(
        self,
        data: pandas.DataFrame,
        wb: Spreadsheet,
        sheet_config: parser.SheetConfig
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
                rows=self.config.height,
                cols=self.config.width,
            )
            return ws

    def format(self) -> None:
        self.config = self.config._replace(
            width=len(self.data.columns),
            height=len(self.data)+1
        )
        self.sheet.set_basic_filter(name=self.config.ranges)
        self.sheet.columns_auto_resize(
            start_column_index=0,
            end_column_index=len(self.columns)
        )
        self.sheet.freeze(cols=3)

    def write(self) -> None:

        # def hyperlink(row: pandas.Series) -> str:
        #     return f'=HYPERLINK("{row.iloc[0]}", "link")'

        # self.data["product_url"] = self.data.loc[:, ["product_url", "product_title"]].apply(
        #     func=hyperlink, axis=1, raw=False
        # )

        self.sheet.update(
            values=(
                [self.data.columns.tolist()]
                + self.data.values.tolist()
            ),
            raw=True
        )

        self.format()
        logger.get_logger("general").info(
            msg=f"done populating {self.config.name} with {len(self.data)}"
        )


def main() -> None:
    configs = loader.load_sheet_configs()
    wb = init_google_sheets()

    engine = utils.get_engine(url="sqlite:///data/sqlite/budgysmuggler.db")

    df = inventory.compute_inventory(engine)
    writer = SheetWriter(
        data=df,
        wb=wb,
        sheet_config=configs[1]
    )
    writer.write()

    return


if __name__ == "__main__":
    main()
