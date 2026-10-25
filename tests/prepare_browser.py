"""Provision accounts only in an explicitly isolated browser-test data directory."""

import os
from pathlib import Path

from fair_hdf5.application import create_app
from fair_hdf5.settings import Settings


def main():
    directory = Path(os.environ["FAIR_HDF5_DATA_DIR"]).resolve()
    if "fair-browser" not in directory.name and "fair-project-qa" not in directory.name:
        raise SystemExit("Use an isolated directory named fair-browser-* or fair-project-qa*.")
    password = os.environ["FAIR_TEST_PASSWORD"]
    app = create_app(Settings(_env_file=None, data_dir=directory))
    accounts = app.state.account_service
    username = os.environ.get("FAIR_TEST_ADMIN", "qaadmin")
    with accounts.database.transaction() as connection:
        existing = connection.execute(
            "SELECT id FROM users WHERE username=?", (username,)
        ).fetchone()
    if existing:
        return
    identifier = accounts.create_user(
        username, "QA Researcher", password, is_admin=True, bootstrap=True
    )
    token, _ = accounts.new_session(identifier)
    principal = accounts.principal(token)
    for member in ("qaeditor", "qaviewer"):
        user_id = accounts.create_user(member, member, password, principal=principal)
        with accounts.database.transaction(write=True) as connection:
            connection.execute(
                "UPDATE local_credentials SET must_change=0 WHERE user_id=?", (user_id,)
            )
    accounts.logout(principal)
    print("Browser-test accounts prepared.")


if __name__ == "__main__":
    main()
