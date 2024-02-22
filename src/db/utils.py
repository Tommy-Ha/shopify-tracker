from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import MetaData
from sqlalchemy import Engine, create_engine
from sqlalchemy import select, table, column
from sqlalchemy import text

from sqlalchemy.dialects.sqlite import insert as sqlite_upsert

import pathlib


def init_database(
    engine: Engine, metadata: MetaData
) -> None:
    metadata.create_all(engine)


def get_engine(url: str, **kwargs: object) -> Engine:
    engine = create_engine(
        url=url,
        use_insertmanyvalues=False,
        **kwargs
    )
    return engine


def insert_one(engine: Engine, value: dict, instance) -> None:
    with Session(engine) as session:
        values_to_insert = instance(**value)

        session.add(values_to_insert)
        session.commit()


def insert_many(
    engine: Engine, values: list[dict], instance
) -> None:
    with Session(engine) as session:
        values_to_insert = [instance(**item) for item in values]

        session.add_all(values_to_insert)
        session.commit()


def upsert_one(
    engine: Engine, value: dict, instance
) -> None:
    with Session(engine) as session:
        primary_keys = instance.__table__.primary_key.columns.keys()
        columns = [
            c
            for c in instance.__table__.columns.keys()
            if c not in primary_keys
        ]

        stmt = sqlite_upsert(instance).values(value)
        stmt = stmt.on_conflict_do_update(
            index_elements=primary_keys,
            set_={
                c: getattr(stmt.excluded, c)
                for c in columns
            }
        )

        session.execute(stmt)
        session.commit()


def upsert_many(
    engine: Engine, values: list[dict], instance
) -> None:
    with Session(engine) as session:
        primary_keys = instance.__table__.primary_key.columns.keys()
        columns = [
            c
            for c in instance.__table__.columns.keys()
            if c not in primary_keys
        ]

        stmt = sqlite_upsert(instance)
        stmt = stmt.on_conflict_do_update(
            index_elements=primary_keys,
            set_={
                c: getattr(stmt.excluded, c)
                for c in columns
            }
        )

        session.execute(statement=stmt, params=values)
        session.commit()


def select_by_column_names(
    engine: Engine,
    table_name: str,
    colnames: list[str],
    aliases: list[str] | None = None,
) -> list[dict]:
    with Session(engine) as session:
        if aliases is None:
            aliases = colnames

        cols = [
            column(col).label(alias)
            for col, alias in zip(colnames, aliases)
        ]

        stmt = select(*cols).select_from(table(table_name))
        results = session.execute(stmt)

    return [item._asdict() for item in results]


def execute_select_statement(engine: Engine, statement: str) -> list[dict]:
    with Session(engine) as session:
        results = session.execute(text(statement))

        return [r._asdict() for r in results]


def execute_sql_file(engine: Engine, file_path: str) -> None:
    sql_fp = pathlib.Path(file_path)
    stmt = sql_fp.read_text(encoding="utf-8")

    with Session(engine) as session:
        session.execute(text(stmt))
        session.commit()


def main() -> None:
    return


if __name__ == "__main__":
    main()
