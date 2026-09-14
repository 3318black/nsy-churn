"""Read only interface of nsy-churn, lot 7.

    uv run streamlit run app/streamlit_app.py

Three screens display what the pipeline produced: the Monday list, the sheet of
one account, and the performance of the model against the baselines. A banner
states the data source on every screen. The application trains no model, scores
no account and recomputes no measure: everything is read from the files written
by ``churn.pipeline.run_scoring`` and ``scripts/train_model.py``, and every
parameter comes from ``config/config.yaml``. Decisions D15 and D21.

The ``NSY_CHURN_ROOT`` environment variable points the application at another
project root, which is how the tests run it on temporary files.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from churn.config import AppConfig, FeatureSource, load_config
from churn.data.schemas import EVENT_FAMILIES, STATE_EVENT_TYPES
from churn.interface.readers import (
    LoadedExport,
    account_contributions,
    account_history,
    evaluation_periods,
    evaluation_summary,
    export_dates,
    load_export,
    report_banner,
    weekly_activity,
)
from churn.pipeline.schemas import CONTRIBUTIONS_SUFFIX, EXPORT_FILE_PREFIX, FACTOR_COLUMNS

LIST_SCREEN = "Liste du lundi"
ACCOUNT_SCREEN = "Fiche d'un compte"
PERFORMANCE_SCREEN = "Performance du modèle"
SCREENS = (LIST_SCREEN, ACCOUNT_SCREEN, PERFORMANCE_SCREEN)

#: Display names of the rankings of the evaluation report.
SCORER_LABELS = {
    "random": "Hasard",
    "revenue": "Tri par revenu",
    "logistic_finance": "Régression logistique, paiements seuls",
    "logistic": "Régression logistique",
    "xgboost_finance": "XGBoost, paiements seuls",
    "xgboost": "XGBoost",
}

#: Display names of the event types of the journal.
EVENT_LABELS = {
    "connexion": "Jours d'usage",
    "usage_module_cle": "Temps d'usage",
    "taux_completion": "Taux de complétion",
    "desactivation_module": "Désactivation de fonctionnalité",
    "ticket_support_ouvert": "Ticket support ouvert",
    "ticket_support_resolu": "Ticket support résolu",
    "facture_emise": "Facture émise",
    "facture_payee": "Facture payée",
    "echec_prelevement": "Écart de paiement",
    "annulation_abonnement": "Annulation d'abonnement",
    "desactivation_renouvellement": "Renouvellement automatique désactivé",
    "revenu_mensuel": "Revenu mensuel en vigueur",
    "contact_commercial": "Contact commercial",
}

#: Rankings shown on the performance chart when the report holds them.
DEFAULT_CHART_SCORERS = ("revenue", "logistic", "xgboost")


def _project_root() -> Path | None:
    """Return the project root the tests point at, or ``None`` for the real one."""
    value = os.environ.get("NSY_CHURN_ROOT")
    if not value:
        # Streamlit Community Cloud stores it as a secret. Whether root level
        # secrets also become environment variables is not documented, so the
        # secret is read directly. Locally, without any secrets file, it is absent.
        try:
            value = str(st.secrets.get("NSY_CHURN_ROOT", "")) or None
        except Exception:
            value = None
    if not value:
        return None
    # A relative root, such as the ``demo`` of the online deployment, is resolved
    # against the repository rather than the directory the server was started in.
    root = Path(value)
    return root if root.is_absolute() else Path(__file__).resolve().parents[1] / root


def _modified(path: Path) -> int:
    """Return the modification time of a file, zero when absent, to key the cache."""
    return path.stat().st_mtime_ns if path.exists() else 0


def _french(value: float, decimals: int) -> str:
    """Format a number for a French reader, with a decimal comma."""
    return f"{value:.{decimals}f}".replace(".", ",")


@st.cache_data(show_spinner=False)
def _cached_export(directory: str, day: str, modified: int) -> LoadedExport:
    """Read an export once per version of its files."""
    del modified
    return load_export(Path(directory), date.fromisoformat(day))


def _banner(label: str, is_synthetic: bool, capacity: int) -> None:
    """State the data source, on every screen."""
    if is_synthetic:
        st.warning(
            f"Données simulées : {label}. Aucun chiffre affiché ici ne vaut performance, "
            "ces données servent uniquement à tester la chaîne."
        )
    else:
        st.info(
            f"Source : {label}. Capacité de {capacity} appels par semaine, "
            "hypothèse de démonstration fixée dans la configuration."
        )


def _no_export(source: str, notice: str) -> None:
    """Explain why the export is missing, or how to produce it."""
    if notice.strip():
        st.info(notice)
        return
    st.info(
        "Aucun export disponible pour cette source. Pour le produire : "
        f"`uv run python -m churn.pipeline.run_scoring --source {source}`"
    )


def _show_list(export: LoadedExport | None, source: str, export_dir: Path) -> None:
    """Screen 1: the prioritised list of the week."""
    if export is None:
        return
    identity = export.identity
    rows = export.rows
    head = rows.loc[rows["is_top_k"].astype(bool)] if not rows.empty else rows

    columns = st.columns(4)
    columns[0].metric("Date de scoring", identity.date_scoring.strftime("%d/%m/%Y"))
    columns[1].metric("Comptes scorés", f"{identity.row_count:,}".replace(",", " "))
    columns[2].metric("Appels de la semaine", len(head))
    columns[3].metric("Modèle", identity.model_version)
    st.caption(f"Identifiant du lot : {identity.batch_run_id}")

    if rows.empty:
        st.info("Cet export ne contient aucun compte éligible à la date de scoring.")
        return

    filters = st.columns([1, 1, 1])
    only_head = filters[0].toggle(f"Seulement les {len(head)} appels de la semaine", value=True)
    deciles = filters[1].multiselect("Déciles de risque", list(range(1, 11)))
    search = filters[2].text_input("Rechercher un compte")
    show_score = st.checkbox("Afficher le score technique, réservé au diagnostic")

    view = head if only_head else rows
    if deciles:
        view = view.loc[view["decile_risque"].isin(deciles)]
    if search.strip():
        view = view.loc[view["client_id"].str.contains(search.strip(), regex=False)]
    shown = ["rang_priorite", "decile_risque", "client_id", "mrr", *FACTOR_COLUMNS]
    if show_score:
        shown.append("score_brut_technique")

    st.dataframe(
        view.loc[:, shown],
        hide_index=True,
        column_config={
            "rang_priorite": st.column_config.NumberColumn("Rang"),
            "decile_risque": st.column_config.NumberColumn("Décile"),
            "client_id": st.column_config.TextColumn("Compte"),
            "mrr": st.column_config.NumberColumn("Revenu mensuel", format="%.2f"),
            "facteur_risque_1": st.column_config.TextColumn("Motif 1"),
            "facteur_risque_2": st.column_config.TextColumn("Motif 2"),
            "facteur_risque_3": st.column_config.TextColumn("Motif 3"),
            "score_brut_technique": st.column_config.NumberColumn("Score technique", format="%.4f"),
        },
    )
    st.caption(
        "Cliquez sur un en-tête pour trier. Le score technique n'est pas une probabilité : "
        "lisez le rang et le décile. Un revenu à zéro signifie un revenu inconnu."
    )

    csv_path = export_dir / f"{EXPORT_FILE_PREFIX}{identity.date_scoring.isoformat()}.csv"
    if csv_path.is_file():
        st.download_button(
            "Télécharger la liste pour Excel",
            data=csv_path.read_bytes(),
            file_name=csv_path.name,
            mime="text/csv",
        )


def _contribution_chart(contributions: pd.DataFrame, motifs: list[str], threshold: float | None):
    """Return the bar chart of the contributions of one account."""
    shown = set(motifs)
    statuses = [
        "Motif affiché"
        if label in shown
        else ("Actionnable, non retenu" if actionable else "Structurel, jamais affiché")
        for label, actionable in zip(
            contributions["libelle"], contributions["actionnable"], strict=True
        )
    ]
    data = contributions.assign(statut=statuses)
    chart = (
        alt.Chart(data)
        .mark_bar()
        .encode(
            x=alt.X("contribution:Q", title="Contribution au score"),
            y=alt.Y("libelle:N", sort="-x", title=None),
            color=alt.Color("statut:N", title=None),
            tooltip=["libelle", alt.Tooltip("contribution:Q", format=".3f"), "statut"],
        )
    )
    if threshold is None:
        return chart
    rule = (
        alt.Chart(pd.DataFrame({"seuil": [threshold]}))
        .mark_rule(strokeDash=[4, 4])
        .encode(x="seuil:Q")
    )
    return chart + rule


def _show_history(config: AppConfig, source: str, client_id: str, export: LoadedExport) -> None:
    """The events of the account strictly before the scoring date."""
    before = pd.Timestamp(export.identity.date_scoring.isoformat(), tz="UTC")
    history = account_history(config.paths.processed / source / "events.parquet", client_id, before)
    if history.empty:
        st.info("Aucun historique disponible pour ce compte avec cette source.")
        return

    usage_types = [
        member.value
        for member, family in EVENT_FAMILIES.items()
        if family is FeatureSource.PRODUCT and member not in STATE_EVENT_TYPES
    ]
    present = [kind for kind in usage_types if kind in set(history["event_type"])]
    if present:
        kind = st.selectbox(
            "Indicateur d'usage", present, format_func=lambda k: EVENT_LABELS.get(k, k)
        )
        activity = weekly_activity(history, [kind])
        st.bar_chart(activity, x="semaine", y="nombre", x_label="Semaine", y_label="Jours")

    finance_types = {
        member.value for member, family in EVENT_FAMILIES.items() if family is FeatureSource.FINANCE
    }
    finance = history.loc[history["event_type"].isin(finance_types)]
    if not finance.empty:
        st.markdown("**Derniers événements de paiement**")
        latest = finance.sort_values("event_ts", ascending=False, kind="stable").head(15)
        st.dataframe(
            latest.assign(
                date=latest["event_ts"].dt.strftime("%d/%m/%Y"),
                evenement=latest["event_type"].map(lambda k: EVENT_LABELS.get(k, k)),
            ).loc[:, ["date", "evenement", "event_value"]],
            hide_index=True,
            column_config={
                "date": st.column_config.TextColumn("Date"),
                "evenement": st.column_config.TextColumn("Événement"),
                "event_value": st.column_config.NumberColumn("Valeur", format="%.2f"),
            },
        )


def _show_account(export: LoadedExport | None, config: AppConfig, source: str) -> None:
    """Screen 2: the sheet of one account."""
    if export is None:
        return
    rows = export.rows
    if rows.empty:
        st.info("Cet export ne contient aucun compte éligible à la date de scoring.")
        return

    ranks = dict(zip(rows["client_id"], rows["rang_priorite"], strict=True))
    client_id = st.selectbox(
        "Compte", rows["client_id"].tolist(), format_func=lambda c: f"Rang {ranks[c]} · {c}"
    )
    row = rows.loc[rows["client_id"] == client_id].iloc[0]

    columns = st.columns(4)
    columns[0].metric("Rang", int(row["rang_priorite"]))
    columns[1].metric("Décile de risque", int(row["decile_risque"]))
    revenue = float(row["mrr"])
    columns[2].metric("Revenu mensuel", _french(revenue, 2) if revenue > 0 else "Inconnu")
    columns[3].metric("Appelé cette semaine", "Oui" if bool(row["is_top_k"]) else "Non")

    st.subheader("Motifs affichés")
    motifs = [str(row[column]) for column in FACTOR_COLUMNS if row[column]]
    if motifs:
        st.markdown("\n".join(f"{position}. {motif}" for position, motif in enumerate(motifs, 1)))
    else:
        st.write(
            "Aucun motif significatif : la case reste vide plutôt que d'afficher un motif inventé."
        )

    st.subheader("Contribution de chaque facteur")
    contributions = account_contributions(export, client_id)
    threshold = export.identity.significance_threshold
    if contributions.empty:
        st.info(
            "Cet export ne contient pas les contributions. Relancez le scoring pour les produire."
        )
    else:
        st.altair_chart(_contribution_chart(contributions, motifs, threshold), width="stretch")
        seuil = f", {threshold:.3f}" if threshold is not None else ""
        st.caption(
            "Une contribution positive pousse le risque vers le haut. Seules les contributions "
            f"actionnables au-dessus du seuil de signification{seuil}, en pointillés, "
            "deviennent des motifs."
        )

    st.subheader("Historique avant la date de scoring")
    _show_history(config, source, client_id, export)


def _show_performance(config: AppConfig, source: str) -> None:
    """Screen 3: the Precision@K of the model against the baselines."""
    directory = config.paths.reports / source / "models"
    summary = evaluation_summary(directory)
    if summary.empty:
        st.info(
            "Aucun rapport d'évaluation pour cette source. Pour le produire : "
            f"`uv run python scripts/train_model.py --source {source}`"
        )
        return

    capacity = config.business.weekly_capacity_k
    banner = report_banner(directory)
    if banner:
        st.caption(f"Rapport : {banner}")

    table = summary.assign(
        classement=summary["scorer"].map(lambda name: SCORER_LABELS.get(name, name)),
        departs=summary["precision_at_k"] * capacity,
    )
    best = table.loc[table["precision_at_k"].idxmax()]
    columns = st.columns(3)
    columns[0].metric("Meilleur classement", str(best["classement"]))
    columns[1].metric(f"Départs trouvés sur {capacity} appels", f"{best['departs']:.0f}")
    if "lift_vs_revenue" in table.columns:
        columns[2].metric(
            "Gain contre le tri par revenu", f"{_french(best['lift_vs_revenue'], 1)} fois plus"
        )

    shown = ["classement", "precision_at_k", "precision_at_k_std", "recall_at_k", "roc_auc"]
    if "lift_vs_revenue" in table.columns:
        shown.append("lift_vs_revenue")
    shown.append("departs")
    st.dataframe(
        table.loc[:, shown],
        hide_index=True,
        column_config={
            "classement": st.column_config.TextColumn("Classement"),
            "precision_at_k": st.column_config.NumberColumn(f"Precision@{capacity}", format="%.3f"),
            "precision_at_k_std": st.column_config.NumberColumn("Écart type", format="%.3f"),
            "recall_at_k": st.column_config.NumberColumn("Rappel", format="%.3f"),
            "roc_auc": st.column_config.NumberColumn("ROC-AUC", format="%.3f"),
            "lift_vs_revenue": st.column_config.NumberColumn(
                "Lift contre le revenu", format="%.2f"
            ),
            "departs": st.column_config.NumberColumn(
                f"Départs sur {capacity} appels", format="%.1f"
            ),
        },
    )

    periods = evaluation_periods(directory)
    if periods.empty:
        return
    periods = periods.assign(
        classement=periods["scorer"].map(lambda name: SCORER_LABELS.get(name, name))
    )
    available = list(dict.fromkeys(periods["classement"]))
    defaults = [
        SCORER_LABELS[name] for name in DEFAULT_CHART_SCORERS if SCORER_LABELS[name] in available
    ]
    selected = st.multiselect("Classements affichés", available, default=defaults or available)
    chart = (
        alt.Chart(periods.loc[periods["classement"].isin(selected)])
        .mark_line(point=True)
        .encode(
            x=alt.X("period_start:T", title="Semaine de scoring"),
            y=alt.Y("precision:Q", title=f"Précision des {capacity} premiers"),
            color=alt.Color("classement:N", title=None),
            tooltip=["classement", "period_start:T", alt.Tooltip("precision:Q", format=".3f")],
        )
    )
    st.altair_chart(chart, width="stretch")
    st.caption(
        f"Précision des {capacity} premiers de chaque semaine, sur les périodes de test de "
        f"{periods['fold'].nunique()} plis chronologiques. Chaque classement n'est jugé que sur "
        "des semaines qu'il n'a jamais vues pendant son apprentissage."
    )


def main() -> None:
    """Render the selected screen, under the source banner."""
    st.set_page_config(page_title="nsy-churn", layout="wide")
    config = load_config(project_root=_project_root())
    profiles = config.sources.as_mapping()
    names = list(profiles)

    st.sidebar.title("nsy-churn")
    source = st.sidebar.selectbox(
        "Source des données",
        names,
        index=names.index(config.active_source),
        format_func=lambda name: profiles[name].label,
    )
    screen = st.sidebar.radio("Écran", SCREENS)

    export_dir = config.paths.exports / source
    dates = export_dates(export_dir)
    export: LoadedExport | None = None
    if dates:
        day = st.sidebar.selectbox(
            "Date de scoring", dates, format_func=lambda d: d.strftime("%d/%m/%Y")
        )
        stem = f"{EXPORT_FILE_PREFIX}{day.isoformat()}"
        version = _modified(export_dir / f"{stem}.parquet") + _modified(
            export_dir / f"{stem}{CONTRIBUTIONS_SUFFIX}.parquet"
        )
        export = _cached_export(str(export_dir), day.isoformat(), version)

    profile = profiles[source]
    label = export.identity.source_label if export else profile.label
    is_synthetic = export.identity.is_synthetic if export else profile.is_synthetic
    _banner(label, is_synthetic, config.business.weekly_capacity_k)

    st.title(screen)
    if export is None and screen != PERFORMANCE_SCREEN:
        _no_export(source, config.interface.missing_export_notice)
    elif screen == LIST_SCREEN:
        _show_list(export, source, export_dir)
    elif screen == ACCOUNT_SCREEN:
        _show_account(export, config, source)
    else:
        _show_performance(config, source)


main()
