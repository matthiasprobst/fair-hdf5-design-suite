"""Authentication-neutral identity and errors for project use cases."""

from dataclasses import dataclass


class ApplicationError(Exception):
    def __init__(self, status: int, code: str, detail: str):
        super().__init__(detail)
        self.status = status
        self.code = code


@dataclass(frozen=True)
class Principal:
    user_id: str
    session_id: str


def fail(status: int, code: str, detail: str):
    raise ApplicationError(status, code, detail)
