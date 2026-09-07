# nsy-churn

Moteur de prédiction de résiliation client. À une date donnée, il classe les comptes actifs par risque de résiliation dans les 60 jours et livre, pour chaque compte prioritaire, les trois facteurs qui expliquent son score.

## État du projet

Cadrage terminé le 7 septembre 2026. Implémentation non démarrée.

Le projet ne dispose d'aucune donnée réelle à ce jour. Il démarre sur un jeu synthétique construit d'après un contrat de données figé, de sorte que la bascule vers les données réelles ne demande que le remplacement de l'adaptateur de source. Aucun chiffre de performance obtenu sur ce jeu synthétique ne vaut prévision de performance réelle.

## Documentation

| Fichier | Contenu |
| :--- | :--- |
| `AGENTS.md` | Manuel opératoire de l'agent développeur. Point d'entrée. |
| `docs/decisions.md` | Décisions closes, de D1 à D11, et points ouverts. |
| `docs/data-contract.md` | Forme des données d'entrée, construction du jeu d'apprentissage, règle de non-fuite, schéma de sortie. |
| `docs/roadmap.md` | Sept lots, avec critères d'acceptation. |
| `docs/revue-spec-v3.md` | Revue critique du cadrage initial et motifs des corrections. |
| `refs/` | Cadrage d'origine, conservé comme archive. |

Le guide de rédaction d'AGENTS.md qui a servi de modèle est un support de cours externe. Il n'est pas redistribué ici et reste hors du suivi de version. Sa substance est intégrée à `AGENTS.md`.

## Démarrage

```bash
uv sync
uv run pytest
```

## Périmètre de la version 1

Contrat de données, générateur synthétique, construction du jeu d'apprentissage sans fuite temporelle, protocole d'évaluation, modélisation, explicabilité locale par TreeSHAP, export Parquet et CSV.

Hors périmètre : synchronisation CRM, base de données, API HTTP, interface web.
