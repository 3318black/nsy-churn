# Stack technique

Versions résolues et vérifiées sur ce poste le 7 septembre 2026, sous Python 3.14.4. La résolution complète compte 94 paquets, dépendances transitives incluses, verrouillées dans `uv.lock`.

Le principe de versionnage est en décision D9 : contraintes minimales dans `pyproject.toml`, versions exactes dans `uv.lock` qui est versionné. Aucune version exacte n'est écrite à la main dans le fichier de projet.

## Vue d'ensemble

```text
                    ┌─────────────────────────────┐
                    │   app/streamlit_app.py      │   lecture seule
                    │   streamlit 1.63            │   lot 7
                    └──────────────┬──────────────┘
                                   │ lit les exports
                    ┌──────────────┴──────────────┐
                    │   data/exports/*.parquet    │
                    │   pyarrow 25.0              │
                    └──────────────┬──────────────┘
                                   │ ecrits par
   ┌───────────────────────────────┴───────────────────────────────┐
   │                        PIPELINE BATCH                          │
   │                                                                │
   │   sources          features         evaluation       models    │
   │   pandas 3.0   ──► pandas 3.0   ──► sklearn 1.9  ──► xgboost   │
   │   pyarrow          numpy 2.5        numpy            3.4       │
   │                                                                │
   │   validation : pydantic 2.13     configuration : pyyaml 6.0    │
   │   diagnostic : seaborn 0.13 sur matplotlib 3.11                │
   └────────────────────────────────────────────────────────────────┘
                                   ▲
                                   │ alimente
             ┌─────────────────────┴─────────────────────┐
             │  KKBox (demonstration)   Synthetique (tests) │
             │  kaggle 2.2, hors pipeline                   │
             └──────────────────────────────────────────────┘
```

## Production

| Brique | Version | Rôle | Pourquoi celle-là |
| :--- | :--- | :--- | :--- |
| **Python** | 3.14.4 | Exécution | 3.12 est le minimum déclaré. Toutes les roues binaires nécessaires existent en 3.14, vérifié par installation réelle. |
| **pandas** | 3.0.5 | Manipulation de données | Conservé après mesure contre polars, décision D13. Attention à la résolution temporelle multiple, voir les pièges ci-dessous. |
| **numpy** | 2.5.3 | Calcul numérique | Socle de toute la chaîne. |
| **scikit-learn** | 1.9.0 | Découpage temporel, lignes de base, métriques | `TimeSeriesSplit` et son paramètre `gap` portent l'embargo de la décision D4. La régression logistique fournit la troisième ligne de base. |
| **xgboost** | 3.4.1 | Modèle et explicabilité | Retenu après mesure, décision D12. Fournit les contributions SHAP nativement par `pred_contribs`, ce qui retire `shap` de la production. |
| **pydantic** | 2.13.5 | Contrats de données et configuration typée | Valide les tables d'entrée, la ligne d'export et le fichier de configuration. Un contrat non respecté échoue au chargement, jamais plus tard. |
| **pyarrow** | 25.0.1 | Lecture et écriture Parquet | Format de sortie de référence, typé et compressé. |
| **pyyaml** | 6.0.3 | Lecture de la configuration | `config.yaml` et `feature_mapping.yaml`. |
| **seaborn** | 0.13.2 | Graphiques d'analyse et de diagnostic | Usage interne uniquement, décision D10. |
| **matplotlib** | 3.11.1 | Socle graphique | Contraint sous 3.13, voir la dette ci-dessous. |
| **streamlit** | 1.63.0 | Interface de restitution | Décision D15. Python pur, déploiement public gratuit. Compatibilité avec pandas 3.0 vérifiée, rendu Altair inclus. |

## Développement seulement

| Brique | Version | Rôle |
| :--- | :--- | :--- |
| **shap** | 0.52.0 | Exploration et comparaison de modèles. Jamais importé par le code de production, décision D12. |
| **kaggle** | 2.2.4 | Téléchargement du jeu KKBox, exécuté une seule fois hors pipeline. |
| **pytest** | 9.1.1 | Tests. `filterwarnings = ["error::FutureWarning"]` transforme les dépréciations en échecs. |
| **ruff** | 0.16.6 | Analyse et formatage. Les règles `DTZ` interdisent les dates sans fuseau, `PD` attrape les anti-patrons pandas. |
| **mypy** | 2.3.1 | Typage, en mode standard jusqu'à l'échéance, décision D16. |

## Ce qui est volontairement absent

| Écarté | Motif |
| :--- | :--- |
| `shap` en production | XGBoost calcule les mêmes valeurs nativement, écart mesuré exactement nul, et évite 138 Mo de `numba` et `llvmlite`. Décision D12. |
| `polars` | Mesuré à 1,6 seconde de gain sur la grille complète. Insuffisant pour une seconde API dans le dépôt. Décision D13. |
| `lightgbm` | Compatible, mais `shap` signale un changement de format de sortie sur ses classifieurs binaires, source d'erreur silencieuse. |
| PostgreSQL, SQLAlchemy | Aucune base de données en version 1. La sortie est un fichier. |
| FastAPI, Uvicorn | Architecture entièrement batch. Aucun serveur HTTP. |
| Airflow, Prefect | Un point d'entrée en ligne de commande suffit au périmètre. |
| PyTorch, TensorFlow | Le problème est tabulaire. Le gradient boosting y reste l'état de l'art. |
| Tout modèle de langage | La traduction des facteurs de risque est un dictionnaire statique, déterministe et testable. |

## Pièges connus de cette stack

**Résolution temporelle sous pandas 3.0.** `pd.date_range` produit du `datetime64[us]`, une construction par `to_timedelta` peut produire du `[ns]`, et `merge_asof` refuse de mélanger les deux. La résolution est normalisée à l'ingestion, paramètre `features.datetime_resolution`.

**`merge_asof` réindexe.** Un `sort_index()` ne restaure pas l'ordre d'origine. Il faut conserver une colonne d'index explicite.

**`merge_asof` et horodatages dupliqués.** La fonction ne garantit pas de retenir la dernière ligne d'un groupe partageant le même horodatage. L'agrégation préalable par `(client_id, event_ts)` est obligatoire. Cette seule omission produisait 10,5 % de lignes fausses lors de la mesure du 2026-09-07.

**Dette matplotlib.** `seaborn 0.13.2` appelle le paramètre `vert`, déprécié en matplotlib 3.11 et supprimé en 3.13. D'où la contrainte `matplotlib<3.13`, à lever à la prochaine version de seaborn.

**Contributions XGBoost.** Le tableau retourné par `pred_contribs=True` comporte une colonne de plus que le nombre de variables. La dernière est le biais et doit être écartée du classement des facteurs.

## Commandes

```bash
uv sync                          # installe production et developpement depuis uv.lock
uv sync --no-dev                 # production seule
uv run pytest -q                 # tests
uv run ruff check src tests      # analyse
uv run mypy src                  # typage
uv run streamlit run app/streamlit_app.py   # interface, a partir du lot 7
```
