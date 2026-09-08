"""Diagnostic report on the training set.

Seaborn serves the analysis and the diagnosis, never the business restitution,
which receives a workable table. That is decision D10.

Two things are looked for here, and neither is decoration.

A feature that separates too well
    A distribution split cleanly in two by the target usually means a leak, not a
    discovery. It is the visual counterpart of the sentinel.
A feature that separates not at all
    Identical distributions across both classes signal a column that costs
    compute and carries nothing.

**Every figure states its data source.** A number obtained on simulated data is
labelled as such, wherever it travels. Decision D2 rests on that flag, and a
report that omits it is how a synthetic figure ends up quoted as a real one.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from churn.features.build import TrainingSet

__all__ = ["FEATURES_PER_FIGURE", "write_distribution_report"]

#: Features drawn per figure, so each panel stays readable.
FEATURES_PER_FIGURE = 12


def _source_banner(source_label: str, is_synthetic: bool) -> str:
    """Return the banner every figure carries."""
    if is_synthetic:
        return f"SIMULATED DATA, {source_label}. No performance figure holds here."
    return f"Source: {source_label}"


def _most_discriminating(training: TrainingSet, limit: int) -> list[str]:
    """Return the features whose distributions differ most across classes.

    Ranking by standardised mean difference rather than by correlation, so a
    feature can surface even when its relation to the target is not linear.
    """
    numeric = training.features.select_dtypes("number")
    positive = numeric.loc[training.target == 1]
    negative = numeric.loc[training.target == 0]
    if positive.empty or negative.empty:
        return list(numeric.columns[:limit])

    spread = numeric.std().replace(0.0, pd.NA)
    separation = ((positive.mean() - negative.mean()).abs() / spread).dropna()
    return list(separation.sort_values(ascending=False).head(limit).index)


def write_distribution_report(
    training: TrainingSet,
    directory: Path,
    source_label: str,
    is_synthetic: bool,
) -> list[Path]:
    """Write the distribution figures of the training set.

    Args:
        training: the grid, its target and its features.
        directory: destination directory, created when missing.
        source_label: label of the data source, shown on every figure.
        is_synthetic: whether the data is simulated.

    Returns:
        The paths of the written figures.
    """
    directory.mkdir(parents=True, exist_ok=True)
    banner = _source_banner(source_label, is_synthetic)
    written: list[Path] = []

    if training.grid.empty:
        return written

    # Positive rate over time. A drift here changes what a model is asked to
    # learn, and no aggregate metric would show it.
    # The timezone is dropped explicitly before the period conversion, which
    # would otherwise warn about losing it. The observation dates are UTC, so
    # nothing meaningful is lost.
    months = training.grid["T0"].dt.tz_localize(None).dt.to_period("M")
    by_period = training.grid.groupby(months)["y"].agg(["mean", "size"])
    figure, axes = plt.subplots(figsize=(11, 4))
    axes.plot(by_period.index.astype(str), by_period["mean"], marker="o")
    axes.set_title(f"Positive rate per month\n{banner}")
    axes.set_ylabel("share of terminations")
    axes.tick_params(axis="x", rotation=70)
    axes.grid(visible=True, alpha=0.3)
    figure.tight_layout()
    path = directory / "target_rate_over_time.png"
    figure.savefig(path, dpi=110)
    plt.close(figure)
    written.append(path)

    # Distributions of the most separating features, per class. A feature that
    # splits the two classes cleanly is a leak suspect before it is a discovery.
    selected = _most_discriminating(training, FEATURES_PER_FIGURE)
    if selected:
        rows = (len(selected) + 3) // 4
        figure, axes = plt.subplots(rows, 4, figsize=(16, 3.2 * rows))
        for panel, name in zip(axes.ravel(), selected, strict=False):
            frame = pd.DataFrame(
                {
                    "value": training.features[name],
                    "class": training.target.map({0: "kept", 1: "lost"}),
                }
            )
            sns.boxplot(data=frame, x="class", y="value", ax=panel, showfliers=False)
            panel.set_title(name, fontsize=9)
            panel.set_xlabel("")
            panel.set_ylabel("")
        for panel in axes.ravel()[len(selected) :]:
            panel.set_visible(False)
        figure.suptitle(f"Most separating features, per class\n{banner}", y=1.0)
        figure.tight_layout()
        path = directory / "feature_distributions.png"
        figure.savefig(path, dpi=110)
        plt.close(figure)
        written.append(path)

    return written
