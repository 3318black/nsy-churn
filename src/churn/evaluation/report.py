"""Evaluation report, always stating the data source.

A figure travels. Copied into a README, a slide or an interview answer, it loses
the context it was produced in. **Every artefact written here therefore carries
the source in its first line**, and a figure obtained on simulated data carries
the explicit statement that no performance holds there. Decision D2 rests on
this, and a report that omits it is how a synthetic figure ends up quoted as a
real one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from churn.evaluation.protocol import EvaluationResult, summarise

__all__ = ["source_banner", "write_evaluation_report"]


def source_banner(source_label: str, is_synthetic: bool) -> str:
    """Return the statement every artefact opens with."""
    if is_synthetic:
        return f"SIMULATED DATA ({source_label}). No performance figure holds here."
    return f"Source: {source_label}"


def _format(value: object) -> str:
    """Return a measure rendered for a Markdown table."""
    if isinstance(value, float):
        return "n/a" if pd.isna(value) else f"{value:.4f}"
    return str(value)


def _markdown_table(frame: pd.DataFrame) -> str:
    """Return a frame as a Markdown table, without extra dependency."""
    header = "| " + " | ".join(frame.columns) + " |"
    rule = "| " + " | ".join("---" for _ in frame.columns) + " |"
    rows = [
        "| " + " | ".join(_format(value) for value in row) + " |"
        for row in frame.itertuples(index=False)
    ]
    return "\n".join([header, rule, *rows])


def write_evaluation_report(
    result: EvaluationResult,
    directory: Path,
    source_label: str,
    is_synthetic: bool,
    frequency: str,
) -> list[Path]:
    """Write the summary, the detailed measures and the precision curve.

    Args:
        result: the gathered measures.
        directory: destination directory, created when missing.
        source_label: label of the data source.
        is_synthetic: whether the data is simulated.
        frequency: scoring period frequency, stated in the summary.

    Returns:
        The paths of the written artefacts.
    """
    directory.mkdir(parents=True, exist_ok=True)
    banner = source_banner(source_label, is_synthetic)
    summary = summarise(result)
    written: list[Path] = []

    folds_path = directory / "evaluation_folds.csv"
    with folds_path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(f"# {banner}\n")
        result.folds.to_csv(handle, index=False)
    written.append(folds_path)

    lines = [
        f"> {banner}",
        "",
        "# Evaluation of the rankings",
        "",
        f"Produced on {datetime.now(UTC):%Y-%m-%d %H:%M} UTC.",
        "",
        f"Precision@K with K = {result.k} per scoring period ({frequency}), averaged "
        "over the periods of each fold, then over the folds. Recall at K is pooled. "
        "ROC-AUC is given for information and drives no decision.",
        "",
        _markdown_table(summary) if not summary.empty else "No fold could be evaluated.",
        "",
    ]
    summary_path = directory / "evaluation_summary.md"
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    written.append(summary_path)

    # The same measures as data files, so that the interface of lot 7 displays
    # them without recomputing a single mean. Decision D21.
    summary_csv_path = directory / "evaluation_summary.csv"
    with summary_csv_path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(f"# {banner}\n")
        summary.to_csv(handle, index=False)
    written.append(summary_csv_path)

    periods_csv_path = directory / "evaluation_precision_per_period.csv"
    with periods_csv_path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(f"# {banner}\n")
        periods = result.periods
        if not periods.empty:
            periods = periods.assign(
                period_start=periods["period"].dt.start_time.dt.date.astype(str)
            ).loc[:, ["fold", "scorer", "period_start", "precision"]]
        periods.to_csv(handle, index=False)
    written.append(periods_csv_path)

    if not result.periods.empty:
        figure, axes = plt.subplots(figsize=(11, 4.5))
        for scorer, frame in result.periods.groupby("scorer", sort=False):
            ordered = frame.sort_values("period")
            # The start of each period as a real date, so matplotlib spaces and
            # labels the axis itself instead of stacking a hundred week strings.
            starts = ordered["period"].dt.start_time
            axes.plot(starts, ordered["precision"], marker=".", label=scorer)
        axes.set_title(f"Precision@{result.k} per scoring period\n{banner}")
        axes.set_ylabel(f"precision of the top {result.k}")
        axes.grid(visible=True, alpha=0.3)
        axes.legend()
        figure.autofmt_xdate()
        figure.tight_layout()
        curve_path = directory / "evaluation_precision_per_period.png"
        figure.savefig(curve_path, dpi=110)
        plt.close(figure)
        written.append(curve_path)

    return written
