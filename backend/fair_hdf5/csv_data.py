"""Bounded CSV parsing and checked conversions shared by preview and export."""

import csv
import io
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import h5py
import numpy as np

from .data_nodes import validate_source
from .errors import DesignError, UploadTooLarge


@dataclass
class CsvTable:
    columns: list[str]
    rows: list[list[str]]
    row_numbers: list[int]
    decimal_separator: str

    @property
    def cells(self):
        return len(self.columns) * (len(self.rows) + 1)

    def preview(self):
        suggestions = []
        for index in range(len(self.columns)):
            dtype = "int64"
            for row in self.rows:
                try:
                    value = number(row[index], self.decimal_separator)
                    if value != value.to_integral_value() or not -(2**63) <= value < 2**63:
                        dtype = "float64"
                    if not np.isfinite(float(value)):
                        raise ValueError
                except (ValueError, OverflowError):
                    dtype = "string"
                    break
            suggestions.append(dtype if self.rows else "string")
        return {
            "columns": self.columns,
            "row_count": len(self.rows),
            "suggested_dtypes": suggestions,
            "rows": self.rows[:50],
        }


def number(raw, decimal_separator):
    raw = raw.strip()
    point = re.escape(decimal_separator)
    if not re.fullmatch(
        rf"[+-]?(?:[0-9]+(?:{point}[0-9]*)?|{point}[0-9]+)(?:[eE][+-]?[0-9]+)?", raw
    ):
        raise ValueError("expected a finite number")
    try:
        result = Decimal(raw.replace(decimal_separator, "."))
        if not result.is_finite():
            raise ValueError("expected a finite number")
        return result
    except InvalidOperation as exc:
        raise ValueError("expected a finite number") from exc


def parse_csv(content, config, settings, source="CSV", cell_limit=None):
    options = validate_source(config)
    if len(content) > settings.max_upload_bytes:
        raise UploadTooLarge("CSV uploads exceed the configured byte limit.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DesignError(f"{source}: expected UTF-8 CSV text.") from exc
    if "\x00" in text:
        raise DesignError(f"{source}: NUL characters are not supported.")
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=options["delimiter"], strict=True)
    columns, rows, row_numbers = None, [], []
    budget = settings.max_dataset_elements if cell_limit is None else cell_limit
    previous_line = 0
    try:
        for row in reader:
            line = previous_line + 1
            previous_line = reader.line_num
            if not row:
                continue
            if columns is None:
                columns = (
                    row if options["has_header"] else [f"Column {i + 1}" for i in range(len(row))]
                )
                if len(columns) > budget:
                    raise UploadTooLarge(f"{source}: CSV cell limit exceeded.")
                if options["has_header"]:
                    continue
            if len(row) != len(columns):
                raise DesignError(
                    f"{source}: row {line} has {len(row)} cells; expected {len(columns)}."
                )
            if len(rows) >= settings.max_dimension_size or (len(rows) + 2) * len(columns) > budget:
                raise UploadTooLarge(f"{source}: CSV row or cell limit exceeded.")
            rows.append(row)
            row_numbers.append(line)
    except csv.Error as exc:
        raise DesignError(f"{source}: invalid CSV near row {reader.line_num}: {exc}.") from exc
    if columns is None:
        raise DesignError(f"{source}: the CSV file is empty.")
    return CsvTable(columns, rows, row_numbers, options["decimal_separator"])


def convert_column(table, index, dtype, source, path):
    if index >= len(table.columns):
        raise DesignError(f"{source}: column {index + 1} does not exist for {path}.")
    values = []
    target = h5py.string_dtype("utf-8") if dtype == "string" else np.dtype(dtype)
    for row_number, row in zip(table.row_numbers, table.rows, strict=True):
        raw = row[index]
        try:
            if dtype == "string":
                value = raw
            else:
                parsed = number(raw, table.decimal_separator)
                if target.kind in "iu":
                    limits = np.iinfo(target)
                    if (
                        parsed != parsed.to_integral_value()
                        or not limits.min <= parsed <= limits.max
                    ):
                        raise ValueError("expected an integer within the target datatype range")
                    value = int(parsed)
                else:
                    value = float(parsed)
                    if not np.isfinite(value) or abs(value) > float(np.finfo(target).max):
                        raise ValueError("number exceeds the target datatype range")
            values.append(value)
        except (ValueError, OverflowError) as exc:
            raise DesignError(
                f"{source}: row {row_number}, column {index + 1} ({table.columns[index]!r}), "
                f"target {path}: {exc}."
            ) from exc
    return np.asarray(values, dtype=target)
