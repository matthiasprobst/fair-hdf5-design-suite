"""SQLite lifecycle and transactions; application policy stays in services."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Database:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "projects.sqlite3"
        with self.transaction() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version > 1:
            raise RuntimeError("This database requires a newer application version.")
        if version == 0:
            schema = (Path(__file__).parent / "migrations" / "001_projects.sql").read_text(
                encoding="utf-8"
            )
            with self.transaction() as connection:
                connection.executescript(
                    "BEGIN IMMEDIATE;\n" + schema + "\nPRAGMA user_version=1;\nCOMMIT;"
                )

    @contextmanager
    def transaction(self, *, write: bool = False):
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()
