"""Validated startup configuration. Settings are owned by each application instance."""

import tempfile
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Local and container installs keep backend/fair_hdf5 inside the repository.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FAIR_HDF5_",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    host: str = Field(default="127.0.0.1", min_length=1)
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["critical", "error", "warning", "info", "debug", "trace"] = "info"
    serve_frontend: bool = True
    frontend_dist: Path = PROJECT_ROOT / "frontend" / "dist"
    data_dir: Path = PROJECT_ROOT / "data"
    temp_dir: Path = Field(default_factory=lambda: Path(tempfile.gettempdir()))
    shacl_engine: Literal["pyshacl", "subset"] = "pyshacl"
    max_upload_bytes: int = Field(default=30_000_000, gt=0)
    profile_fetch_timeout: float = Field(default=10, gt=0)
    profile_max_redirects: int = Field(default=5, ge=0)
    profile_max_depth: int = Field(default=8, ge=0)
    profile_max_documents: int = Field(default=16, gt=0)
    profile_max_document_bytes: int = Field(default=1_000_000, gt=0)
    profile_max_total_bytes: int = Field(default=8_000_000, gt=0)
    max_nodes: int = Field(default=250, gt=0)
    max_edges: int = Field(default=1000, gt=0)
    max_metadata_length: int = Field(default=3000, gt=0)
    max_dataset_dimensions: int = Field(default=5, ge=1, le=32)
    max_dimension_size: int = Field(default=50_000, gt=0)
    max_dataset_elements: int = Field(default=2_000_000, gt=0)
    max_report_issues: int = Field(default=250, gt=0)
    max_blueprint_bytes: int = Field(default=32 * 1024 * 1024, gt=0)
    session_seconds: int = Field(default=12 * 60 * 60, ge=60)
    password_min_length: int = Field(default=15, ge=3, le=128)
    edit_lock_seconds: int = Field(default=120, ge=60)
    cookie_secure: bool = False
    public_url: str | None = None

    @field_validator("public_url", mode="before")
    @classmethod
    def validate_public_url(cls, value):
        if value in (None, ""):
            return None
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Public URL must be an HTTP(S) origin without a path or credentials.")
        return value.rstrip("/")

    @field_validator("frontend_dist", "temp_dir", "data_dir", mode="before")
    @classmethod
    def resolve_path(cls, value):
        path = Path(value).expanduser()
        return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()

    @model_validator(mode="after")
    def validate_temp_directory(self):
        if not self.temp_dir.is_dir():
            raise ValueError(f"Temporary directory does not exist: {self.temp_dir}")
        return self

    def check_storage(self) -> None:
        """Probe actual permissions once at startup; never log configuration contents."""
        try:
            with tempfile.TemporaryFile(dir=self.temp_dir):
                pass
        except OSError as exc:
            raise RuntimeError(f"Temporary directory is not writable: {self.temp_dir}") from exc

    def capabilities(self) -> dict[str, int | str]:
        return {
            "max_nodes": self.max_nodes,
            "max_edges": self.max_edges,
            "max_upload_bytes": self.max_upload_bytes,
            "shacl_engine": self.shacl_engine,
            "max_dimension_size": self.max_dimension_size,
            "max_dataset_elements": self.max_dataset_elements,
        }
