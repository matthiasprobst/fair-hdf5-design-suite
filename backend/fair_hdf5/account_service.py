"""Local authentication and account administration behind stable user identities."""

import hashlib
import re
import secrets
import sqlite3
import time
from uuid import uuid4

from pwdlib import PasswordHash

from .access import Principal, fail
from .database import Database

passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash(secrets.token_urlsafe(32))


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def public_user(row):
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "is_admin": bool(row["is_admin"]),
        "active": bool(row["active"]),
        "must_change_password": bool(row["must_change"]),
    }


def current_user(connection, principal: Principal, *, allow_password_change=False):
    row = connection.execute(
        "SELECT u.*, COALESCE(c.must_change, 0) AS must_change FROM users u LEFT JOIN local_credentials c ON c.user_id=u.id "
        "JOIN sessions s ON s.user_id=u.id WHERE u.id=? AND s.id=? AND s.expires_at>? AND u.active=1",
        (principal.user_id, principal.session_id, time.time()),
    ).fetchone()
    if row is None:
        fail(401, "authentication_required", "Please sign in again.")
    if row["must_change"] and not allow_password_change:
        fail(403, "password_change_required", "Change your temporary password first.")
    return row


class AccountService:
    def __init__(self, database: Database, session_seconds: int, password_min_length: int):
        self.database = database
        self.session_seconds = session_seconds
        self.password_min_length = password_min_length

    def session_data(self, user, csrf: str):
        return {
            "user": public_user(user) if user else None,
            "csrf_token": csrf,
            "password_policy": {"min_length": self.password_min_length, "max_length": 128},
        }

    def session(self, token: str | None):
        with self.database.transaction() as connection:
            session = connection.execute(
                "SELECT * FROM sessions WHERE id=? AND expires_at>?",
                (digest(token or ""), time.time()),
            ).fetchone()
            if session:
                user = connection.execute(
                    "SELECT u.*, c.must_change FROM users u JOIN local_credentials c ON c.user_id=u.id "
                    "WHERE u.id=? AND u.active=1",
                    (session["user_id"],),
                ).fetchone()
                if session["user_id"] is None or user:
                    return token, self.session_data(user, session["csrf_token"])
        return self.new_session(None)

    def new_session(
        self, user_id: str | None, previous: str | None = None, expected_hash: str | None = None
    ):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with self.database.transaction(write=True) as connection:
            if user_id is not None:
                account = connection.execute(
                    "SELECT u.active, c.password_hash FROM users u JOIN local_credentials c ON c.user_id=u.id WHERE u.id=?",
                    (user_id,),
                ).fetchone()
                if (
                    not account
                    or not account["active"]
                    or (
                        expected_hash is not None
                        and not secrets.compare_digest(account["password_hash"], expected_hash)
                    )
                ):
                    fail(401, "invalid_credentials", "The account changed. Sign in again.")
            connection.execute("DELETE FROM sessions WHERE expires_at<=?", (time.time(),))
            if previous:
                connection.execute("DELETE FROM sessions WHERE id=?", (digest(previous),))
            connection.execute(
                "INSERT INTO sessions VALUES (?,?,?,?)",
                (digest(token), user_id, csrf, time.time() + self.session_seconds),
            )
            user = connection.execute(
                "SELECT u.*, c.must_change FROM users u JOIN local_credentials c ON c.user_id=u.id WHERE u.id=?",
                (user_id,),
            ).fetchone()
        return token, self.session_data(user, csrf)

    def principal(self, token: str | None, *, allow_password_change: bool = True) -> Principal:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT user_id FROM sessions WHERE id=? AND expires_at>?",
                (digest(token or ""), time.time()),
            ).fetchone()
            if row is None or row["user_id"] is None:
                fail(401, "authentication_required", "Please sign in.")
            principal = Principal(row["user_id"], digest(token or ""))
            current_user(connection, principal, allow_password_change=allow_password_change)
            return principal

    def check_csrf(self, token: str | None, csrf: str | None):
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT csrf_token FROM sessions WHERE id=? AND expires_at>?",
                (digest(token or ""), time.time()),
            ).fetchone()
            if not row or not csrf or not secrets.compare_digest(row["csrf_token"], csrf):
                fail(403, "csrf_failed", "Your session changed. Reload and try again.")

    def login(self, username: str, password: str, address: str, previous: str | None):
        username = username.strip().lower()
        now = time.time()
        with self.database.transaction(write=True) as connection:
            connection.execute("DELETE FROM login_attempts WHERE attempted_at<?", (now - 300,))
            attempts = connection.execute(
                "SELECT COUNT(*) FROM login_attempts WHERE address=? AND (username=? OR username='*')",
                (address, username),
            ).fetchone()[0]
            total = connection.execute(
                "SELECT COUNT(*) FROM login_attempts WHERE address=?", (address,)
            ).fetchone()[0]
            if attempts >= 10 or total >= 100:
                fail(
                    429,
                    "login_rate_limited",
                    "Too many sign-in attempts. Try again in five minutes.",
                )
            connection.execute(
                "INSERT INTO login_attempts VALUES (?,?,?)", (username, address, now)
            )
            row = connection.execute(
                "SELECT u.*, c.password_hash FROM users u JOIN local_credentials c ON c.user_id=u.id WHERE username=?",
                (username,),
            ).fetchone()
        valid = passwords.verify(password, row["password_hash"] if row else DUMMY_HASH)
        if not valid or not row or not row["active"]:
            fail(401, "invalid_credentials", "Invalid username or password.")
        with self.database.transaction(write=True) as connection:
            connection.execute(
                "DELETE FROM login_attempts WHERE username=? AND address=?", (username, address)
            )
        return self.new_session(row["id"], previous, row["password_hash"])

    def logout(self, principal: Principal):
        with self.database.transaction(write=True) as connection:
            connection.execute("DELETE FROM sessions WHERE id=?", (principal.session_id,))

    def validate_password(self, password: str):
        if not self.password_min_length <= len(password) <= 128:
            fail(
                422,
                "invalid_password",
                f"Use a password of {self.password_min_length} to 128 characters.",
            )

    def temporary_password(self) -> str:
        return secrets.token_urlsafe(96)[: max(27, self.password_min_length)]

    def create_user(
        self,
        username: str,
        display_name: str,
        password: str,
        *,
        is_admin=False,
        principal: Principal | None = None,
        bootstrap=False,
    ):
        username = username.strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,63}", username):
            fail(
                422,
                "invalid_username",
                "Use 3 to 64 letters, digits, dots, underscores or hyphens.",
            )
        if not display_name.strip() or len(display_name) > 120:
            fail(422, "invalid_display_name", "Enter a name of 1 to 120 characters.")
        self.validate_password(password)
        password_hash = passwords.hash(password)
        user_id = str(uuid4())
        with self.database.transaction(write=True) as connection:
            if bootstrap:
                if connection.execute(
                    "SELECT 1 FROM users WHERE is_admin=1 AND active=1"
                ).fetchone():
                    fail(
                        409,
                        "admin_exists",
                        "An administrator already exists. Use the administration page.",
                    )
            else:
                self.require_admin(connection, principal)
            try:
                connection.execute(
                    "INSERT INTO users VALUES (?,?,?,?,?,?)",
                    (user_id, username, display_name.strip(), int(is_admin), 1, time.time()),
                )
            except sqlite3.IntegrityError:
                fail(409, "username_taken", "That username is already in use.")
            connection.execute(
                "INSERT INTO local_credentials VALUES (?,?,?)",
                (user_id, password_hash, 0 if bootstrap else 1),
            )
        return user_id

    @staticmethod
    def require_admin(connection, principal):
        if principal is None or not current_user(connection, principal)["is_admin"]:
            fail(403, "admin_required", "Administrator access is required.")

    def list_users(self, principal):
        with self.database.transaction() as connection:
            self.require_admin(connection, principal)
            return [
                public_user(row)
                for row in connection.execute(
                    "SELECT u.*, c.must_change FROM users u JOIN local_credentials c ON c.user_id=u.id ORDER BY username"
                )
            ]

    def set_active(self, principal, user_id, active):
        with self.database.transaction(write=True) as connection:
            self.require_admin(connection, principal)
            row = connection.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            if not row:
                fail(404, "user_not_found", "Account not found.")
            if (
                not active
                and row["is_admin"]
                and connection.execute(
                    "SELECT COUNT(*) FROM users WHERE active=1 AND is_admin=1"
                ).fetchone()[0]
                <= 1
            ):
                fail(409, "last_admin", "The last active administrator cannot be deactivated.")
            connection.execute("UPDATE users SET active=? WHERE id=?", (int(active), user_id))
            if not active:
                connection.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))

    def reset_password(self, principal, user_id):
        temporary = self.temporary_password()
        encoded = passwords.hash(temporary)
        with self.database.transaction(write=True) as connection:
            self.require_admin(connection, principal)
            if user_id == principal.user_id:
                fail(409, "use_password_change", "Change your own password from Your account.")
            if not connection.execute("SELECT 1 FROM users WHERE id=?", (user_id,)).fetchone():
                fail(404, "user_not_found", "Account not found.")
            connection.execute(
                "UPDATE local_credentials SET password_hash=?, must_change=1 WHERE user_id=?",
                (encoded, user_id),
            )
            connection.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        return temporary

    def change_password(self, principal, old_password, new_password):
        self.validate_password(new_password)
        with self.database.transaction() as connection:
            current_user(connection, principal, allow_password_change=True)
            encoded = connection.execute(
                "SELECT password_hash FROM local_credentials WHERE user_id=?", (principal.user_id,)
            ).fetchone()[0]
        if not passwords.verify(old_password, encoded):
            fail(422, "invalid_password", "The current password is incorrect.")
        if old_password == new_password:
            fail(422, "invalid_password", "Choose a password different from your current password.")
        replacement = passwords.hash(new_password)
        with self.database.transaction(write=True) as connection:
            current_user(connection, principal, allow_password_change=True)
            connection.execute(
                "UPDATE local_credentials SET password_hash=?, must_change=0 WHERE user_id=? AND password_hash=?",
                (replacement, principal.user_id, encoded),
            )
            if connection.execute("SELECT changes()").fetchone()[0] != 1:
                fail(409, "password_changed", "Your password changed. Sign in again.")
            connection.execute("DELETE FROM sessions WHERE user_id=?", (principal.user_id,))
        return self.new_session(principal.user_id)
