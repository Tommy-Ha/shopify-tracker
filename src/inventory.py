from __future__ import annotations

import pandas

from sqlalchemy import Engine

from src.config import settings
from src.db import utils


def combine_inventory_data(engine: Engine) -> pandas.DataFrame:
    combined_inventory = utils.execute_select_statement(
        engine=engine,
        statement=settings.COMBINED_INVENTORY_STMT
    )

    return pandas.DataFrame(data=combined_inventory)


def calculate_item_sold_by_variants(
    group: pandas.DataFrame
) -> pandas.DataFrame:
    item_sold = 0
    values = group["inventory_quantity"].to_list()

    for i, v in enumerate(values):
        previous_v_id = 0 if i-1 <= 0 else i-1
        changes = v - values[previous_v_id]

        if changes < 0:
            item_sold = item_sold - changes
        else:
            continue

    last_updated = group["updated_at"].tail(1)
    df = pandas.DataFrame(
        data={
            "last_updated": last_updated,
            "item_sold": item_sold,
        }
    )

    return df


def compute_inventory(
    engine: Engine
) -> pandas.DataFrame:

    inventory_data = combine_inventory_data(engine)

    def get_head(
        group: pandas.DataFrame, n: int=1
    ) -> pandas.DataFrame:
        return group.head(n)

    updated_inventory = (
        inventory_data
        .groupby("variant_id")[inventory_data.columns]
        .apply(calculate_item_sold_by_variants, include_groups=False)
        .reset_index(level=0, drop=False)
        .fillna(0)
    )

    initial_inventory = (
        inventory_data
        .groupby("variant_id", as_index=False)[inventory_data.columns]
        .apply(get_head)
        .drop(axis=1, labels=["id"])
        .reset_index(drop=True)
        .rename(
            axis=1,
            mapper={
                "updated_at": "first_updated",
                "inventory_quantity": "initial_amount"
            }
        )
    )

    df = (
        pandas.merge(
            left=initial_inventory,
            right=updated_inventory,
            how="left",
            on="variant_id",
        )
        .sort_values(
            by=["item_sold", "initial_amount"],
            ascending=False
        )
    )

    cols = [
        "first_updated",
        "last_updated",
        "product_title",
        "product_url",
        "variant_title",
        "initial_amount",
        "item_sold"
    ]

    return df.loc[:, cols]


def main() -> None:

    engine = utils.get_engine(
        url="sqlite:///data/sqlite/budgysmuggler.db"
    )

    df = compute_inventory(engine)
    print(df)


if __name__ == "__main__":
    main()
