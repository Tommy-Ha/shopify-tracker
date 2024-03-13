from __future__ import annotations

import pathlib
import subprocess


def dump_sqlite() -> None:
    dump_root = pathlib.Path("data/migrate")
    dump_root.mkdir(parents=True, exist_ok=True)

    dbr = pathlib.Path("data/sync")
    for fp in pathlib.Path(dbr).glob("*.db"):
        args = [
            "sqlite3",
            fp,
            f".once {dump_root}/{fp.name}.sql",
            ".dump"
        ]
        subprocess.run(args)
    return


def read_sqlite(sql_root: str) -> None:
    output_root = pathlib.Path("data/sqlite")
    output_root.mkdir(parents=True, exist_ok=True)

    for fp in pathlib.Path(sql_root).glob("*.sql"):
        print(fp.stem)
        args = [
            "sqlite3",
            f"{output_root}/{fp.stem}",
            f".read {fp.resolve()}"
        ]
        subprocess.run(args)
    return


def main() -> int:
    read_sqlite("data/sql")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
