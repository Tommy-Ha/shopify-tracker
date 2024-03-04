from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker
from sqlalchemy import MetaData
from sqlalchemy import Label
from sqlalchemy import Engine, create_engine
from sqlalchemy import select, table, column
from sqlalchemy import text

from sqlalchemy.dialects.sqlite import insert as sqlite_upsert

import pathlib


LocalSession = sessionmaker()


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


def insert_one(session: Session, value: dict, instance) -> None:
    with session:
        values_to_insert = instance(**value)

        session.add(values_to_insert)
        session.commit()


def insert_many(
    session: Session, values: list[dict], instance
) -> None:
    with session:
        values_to_insert = [instance(**item) for item in values]

        session.add_all(values_to_insert)
        session.commit()


def upsert_one(
    session: Session, value: dict, instance
) -> None:
    with session:
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
    session: Session, values: list[dict], instance
) -> None:
    with session:
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
    session: Session,
    table_name: str,
    colnames: list[str],
    aliases: list[str] | None = None,
) -> list[dict]:
    with session:
        if aliases is None:
            aliases = colnames

        cols: list[Label] = [
            column(col).label(alias)
            for col, alias in zip(colnames, aliases)
        ]

        stmt = select(*cols).select_from(table(table_name))
        results = session.execute(stmt)

    return [item._asdict() for item in results]


def execute_select_statement(
    session: Session, statement: str
) -> list[dict]:
    with session:
        results = session.execute(text(statement))

        return [r._asdict() for r in results]


def execute_sql_file(session: Session, file_path: str) -> None:
    sql_fp = pathlib.Path(file_path)
    stmt = sql_fp.read_text(encoding="utf-8")

    with session:
        session.execute(text(stmt))
        session.commit()


def main() -> None:
    return


if __name__ == "__main__":
    main()
