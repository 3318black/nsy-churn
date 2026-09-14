"""Contract of one exported row, section 4 of the data contract.

The export is what a salesperson opens on Monday and what the interface of lot 7
reads. Its columns, their order and their rules are declared once, here, and
every batch is checked against them before any file is written. A breach raises:
a malformed export discovered in a spreadsheet is discovered too late.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Final
from uuid import UUID

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

__all__ = ["EXPORT_COLUMNS", "FACTOR_COLUMNS", "ExportRow", "validate_export"]

#: Number of risk deciles.
_DECILES = 10


class ExportRow(BaseModel):
    """One exported row. Field order is the column order of every file."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    batch_run_id: UUID
    date_scoring: date
    client_id: Annotated[str, Field(min_length=1)]
    rang_priorite: Annotated[int, Field(ge=1)]
    decile_risque: Annotated[int, Field(ge=1, le=_DECILES)]
    is_top_k: bool
    mrr: Annotated[float, Field(ge=0.0)]
    facteur_risque_1: str
    facteur_risque_2: str
    facteur_risque_3: str
    score_brut_technique: float
    model_version: Annotated[str, Field(min_length=1)]


#: Columns of the export, in contract order.
EXPORT_COLUMNS: Final[tuple[str, ...]] = tuple(ExportRow.model_fields)

#: The risk factor columns.
FACTOR_COLUMNS: Final[tuple[str, ...]] = tuple(
    column for column in EXPORT_COLUMNS if column.startswith("facteur_risque_")
)

_ROWS: TypeAdapter[list[ExportRow]] = TypeAdapter(list[ExportRow])


def validate_export(rows: pd.DataFrame, max_label_length: int) -> None:
    """Check a batch against the output contract.

    Args:
        rows: the exported rows.
        max_label_length: longest label a factor may carry, from the configuration.

    Raises:
        ValueError: naming the breach, when the columns, a value, a label length
            or the sequence of ranks does not conform.
    """
    if tuple(rows.columns) != EXPORT_COLUMNS:
        message = f"export columns {list(rows.columns)} differ from the contract {EXPORT_COLUMNS}"
        raise ValueError(message)
    try:
        _ROWS.validate_python(rows.to_dict(orient="records"))
    except ValidationError as error:
        message = f"exported rows breach the contract: {error}"
        raise ValueError(message) from error
    if rows.empty:
        return

    for column in FACTOR_COLUMNS:
        longest = int(rows[column].str.len().max())
        if longest > max_label_length:
            message = f"{column} holds a label of {longest} characters, over {max_label_length}"
            raise ValueError(message)
    expected = np.arange(1, len(rows) + 1)
    if not np.array_equal(rows["rang_priorite"].to_numpy(), expected):
        message = "rang_priorite must run from 1 to the number of rows, in file order"
        raise ValueError(message)
