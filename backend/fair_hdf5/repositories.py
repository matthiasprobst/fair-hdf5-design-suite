"""Storage contracts shared by application services and blueprint parsing."""

from typing import Any, Protocol


class CatalogRepository(Protocol):
    def catalog(self) -> dict[str, dict[str, Any]]: ...
    def get(self, identifier: str, revision: int | None = None) -> dict[str, Any]: ...
    def publish(
        self, snapshot: dict[str, Any], expected_revision: int | None = None
    ) -> dict[str, Any]: ...
