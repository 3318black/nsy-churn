"""Download, decompress and sample the KKBox extracts, in one command.

Run once. It turns the raw competition archives into the two contract tables,
written as Parquet under ``paths.processed``, ready for the rest of the pipeline.

    uv run python scripts/download_kkbox.py --sample-size 50000

Every step is idempotent: an archive already on disk is not fetched again, and a
file already decompressed is not extracted again. Interrupting the script and
restarting it costs only what was left to do.

**The listening logs are optional and off by default.** They weigh 7.8 GB
compressed and 32 GB decompressed, for roughly half an hour of download. They
only feed the product features of lot 3, so the socle can be built without them.
Pass ``--with-logs`` when they are wanted.

Prerequisites, detailed in ``docs/dataset-kkbox.md`` section 7: a Kaggle account,
the competition rules accepted, and a token in ``~/.kaggle/access_token``. The
rules acceptance is the usual cause of failure, a valid token not being enough.
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import time
from pathlib import Path

import py7zr

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from churn.config import load_config
from churn.data.kkbox import KkboxRawPaths, build_dataset, sample_account_ids
from churn.data.sources import write_dataset
from churn.data.target import LabelWindow
from churn.data.validate import validate_dataset

logger = logging.getLogger("download_kkbox")

#: Slug of the competition on Kaggle.
COMPETITION = "kkbox-churn-prediction-challenge"

#: Archives forming the socle: target, reference and both transaction files.
#: They cover the label and every financial feature, so lots 2 and 4 to 6 run
#: without the logs. Roughly 1 GB.
SOCLE_ARCHIVES = (
    "train_v2.csv.7z",
    "members_v3.csv.7z",
    "transactions.csv.7z",
    "transactions_v2.csv.7z",
)

#: Listening logs, which add the product features. Roughly 7.8 GB compressed.
LOG_ARCHIVES = ("user_logs_v2.csv.7z", "user_logs.csv.7z")

#: Months the terminations are derived over. The transactions span January 2015
#: to March 2017, and a labelling window needs the month before its expiries.
LABELLED_MONTHS = tuple(
    LabelWindow.for_month(year, month)
    for year, month in (
        *((2015, month) for month in range(2, 13)),
        *((2016, month) for month in range(1, 13)),
        *((2017, month) for month in (1, 2, 3)),
    )
)


def download_archive(name: str, destination: Path) -> Path:
    """Fetch one archive from Kaggle, unless it is already there.

    Args:
        name: file name on the competition page, extension included.
        destination: directory the archive lands in.

    Returns:
        Path of the archive.

    Raises:
        RuntimeError: when the Kaggle client fails, most often because the
            competition rules have not been accepted.
    """
    target = destination / name
    if target.exists():
        logger.info("archive already present", extra={"archive": name})
        return target

    destination.mkdir(parents=True, exist_ok=True)
    logger.info("downloading", extra={"archive": name})
    started = time.monotonic()
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "kaggle",
            "competitions",
            "download",
            "-c",
            COMPETITION,
            "-f",
            name,
            "-p",
            str(destination),
            "-q",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 or not target.exists():
        message = (
            f"could not download '{name}'. Check that the competition rules are "
            f"accepted on kaggle.com/c/{COMPETITION}/rules, which a valid token "
            f"does not replace. Client output: {completed.stderr.strip()}"
        )
        raise RuntimeError(message)
    size_mb = target.stat().st_size / 1e6
    logger.info(
        "downloaded",
        extra={
            "archive": name,
            "megabytes": round(size_mb),
            "seconds": round(time.monotonic() - started),
        },
    )
    return target


def decompress(archive: Path, destination: Path) -> None:
    """Extract one archive, unless its content is already on disk.

    The archives do not share one internal layout: the ``_v2`` ones carry a
    ``data/churn_comp_refresh/`` prefix and the others do not. Nothing is
    flattened here, the adapter resolves paths by search instead, so the layout
    of the competition stays visible rather than reshaped by hand.

    Args:
        archive: the ``.7z`` file.
        destination: directory the content lands in.
    """
    expected = archive.name.removesuffix(".7z")
    if any(destination.rglob(expected)):
        logger.info("already decompressed", extra={"archive": archive.name})
        return

    logger.info("decompressing", extra={"archive": archive.name})
    started = time.monotonic()
    with py7zr.SevenZipFile(archive, "r") as opened:
        opened.extractall(path=destination)
    logger.info(
        "decompressed",
        extra={"archive": archive.name, "seconds": round(time.monotonic() - started)},
    )


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=None,
        help="accounts to draw, defaults to sources.kkbox.sample_accounts",
    )
    parser.add_argument(
        "--with-logs",
        action="store_true",
        help="also fetch the listening logs, 7.8 GB compressed and 32 GB decompressed",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="use the archives already on disk, fetch nothing",
    )
    parser.add_argument("--seed", type=int, default=None, help="seed of the draw")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the whole preparation and report what was produced."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    arguments = parse_arguments(argv)

    config = load_config()
    profile = config.sources.kkbox
    raw = config.paths.raw
    sample_size = arguments.sample_size or profile.sample_accounts
    seed = arguments.seed or config.project.random_seed

    archives = list(SOCLE_ARCHIVES) + (list(LOG_ARCHIVES) if arguments.with_logs else [])
    for name in archives:
        archive = raw / name if arguments.skip_download else download_archive(name, raw)
        if not archive.exists():
            logger.error("archive missing and download skipped", extra={"archive": name})
            return 1
        decompress(archive, raw)

    paths = KkboxRawPaths.discover(raw)
    logger.info("drawing the account sample", extra={"size": sample_size, "seed": seed})
    account_ids = sample_account_ids(
        [paths.transactions_history, paths.transactions_recent],
        sample_size=sample_size,
        seed=seed,
        chunk_size=profile.chunk_size,
    )

    dataset = build_dataset(
        paths,
        account_ids,
        list(LABELLED_MONTHS),
        chunk_size=profile.chunk_size,
        resolution=config.features.datetime_resolution,
    )

    report = validate_dataset(dataset, resolution=config.features.datetime_resolution)
    if not report.is_valid:
        logger.error("the projected dataset breaches the contract\n%s", report.render())
        return 1

    destination = config.paths.processed / config.active_source
    written = write_dataset(dataset, destination)
    terminated = int(dataset.accounts["date_resiliation"].notna().sum())
    logger.info(
        "dataset written",
        extra={
            "accounts": len(dataset.accounts),
            "terminated": terminated,
            "events": len(dataset.events),
            "directory": str(destination),
        },
    )
    for name, path in written.items():
        print(f"{name:>9} : {path} ({path.stat().st_size / 1e6:.1f} Mo)")
    print(f"{'comptes':>9} : {len(dataset.accounts):,} dont {terminated:,} resilies")
    print(f"{'evenements':>9} : {len(dataset.events):,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
