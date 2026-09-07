# nsy-churn

Moteur de prédiction de résiliation client. À une date donnée, il classe les comptes actifs par risque de résiliation à l'horizon retenu et livre, pour chaque compte prioritaire, les trois facteurs qui expliquent son score.

## État du projet

Cadrage terminé le 7 septembre 2026. Implémentation non démarrée.

Ce README sera réécrit au dernier lot, une fois les résultats disponibles. Le plan imposé figure au lot 8 de la roadmap.

## Ce que ce projet fait différemment

La plupart des projets de churn publics reposent sur un fichier plat sans axe temporel, découpé aléatoirement, évalué en accuracy. Le résultat paraît bon et ne survivrait pas une semaine en production.

Ce projet prend le problème par le temps.

- **Cible reconstruite et vérifiée.** La cible n'est pas une colonne fournie, elle est reconstruite depuis l'historique de transactions à chaque date d'observation, puis la reconstruction est validée contre l'étiquette officielle.
- **Embargo temporel.** L'entraînement et le test sont séparés par une période au moins égale à l'horizon de prédiction. Sans cela, la cible d'entraînement se résout à l'intérieur de la période de test et la validation ment.
- **Sentinelle anti-fuite.** Un test reconstruit chaque variable après suppression de tout événement postérieur à la date d'observation. Le moindre écart signale une variable qui regarde le futur.
- **Contrôle par force brute.** Chaque variable de fenêtre est recalculée par filtrage naïf sur un échantillon et comparée au calcul vectorisé. Ce contrôle a détecté 10,5 % de lignes fausses lors d'une mesure préparatoire.
- **Precision@K par période.** La métrique correspond à la capacité de traitement réelle d'une équipe, et non à un top K global dépourvu de sens opérationnel.
- **Trois lignes de base.** Hasard, tri par revenu décroissant, régression logistique. Un modèle qui ne les bat pas ne justifie pas son coût, et le résultat est publié dans les deux cas.
- **Explicabilité actionnable.** Les contributions sont agrégées au niveau de la variable métier, jamais au niveau de la colonne encodée, et traduites par un dictionnaire statique et testable.

## Données

La démonstration repose sur le jeu **KKBox WSDM Churn Prediction Challenge**, retenu parce qu'il possède ce qui manque aux jeux de churn usuels : deux ans d'observation continue, des logs d'usage quotidiens horodatés, un historique de transactions et un churn défini contractuellement.

Un générateur de données synthétiques est également fourni. Son rôle est différent et strictement délimité : il alimente les tests automatisés, où il apporte reproductibilité, rapidité et couverture des cas limites. Aucune mesure de performance n'est produite sur ce jeu sans mention explicite. Voir la décision D14.

Les données brutes ne sont pas versionnées.

## Documentation

| Fichier | Contenu |
| :--- | :--- |
| `AGENTS.md` | Manuel opératoire de l'agent développeur. Point d'entrée. |
| `docs/decisions.md` | Décisions closes, de D1 à D16, et points ouverts. |
| `docs/data-contract.md` | Tables d'entrée, construction du jeu d'apprentissage, règle de non-fuite, pièges mesurés, schéma de sortie. |
| `docs/dataset-kkbox.md` | Projection du jeu KKBox sur le contrat et reconstruction de la cible. |
| `docs/roadmap.md` | Neuf lots, avec critères d'acceptation. |
| `docs/revue-spec-v3.md` | Revue critique du cadrage initial et motifs des corrections. |
| `refs/` | Cadrage d'origine, conservé comme archive. |

Le guide de rédaction d'AGENTS.md qui a servi de modèle est un support de cours externe. Il n'est pas redistribué ici et reste hors du suivi de version. Sa substance est intégrée à `AGENTS.md`.

## Démarrage

```bash
uv sync
uv run pytest
```

## Périmètre

Contrat de données, générateur synthétique, adaptateur KKBox, construction du jeu d'apprentissage sans fuite temporelle, protocole d'évaluation, modélisation, explicabilité locale, export Parquet et CSV, interface Streamlit en lecture seule.

Hors périmètre : synchronisation CRM, base de données, API HTTP.
