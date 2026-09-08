# Prompt d'implémentation, lot 1 : contrat de données, validation et générateur synthétique

## Objectif

Rendre le contrat de données exécutable. À la fin de ce lot, une source de données quelconque peut être validée contre le contrat, et un générateur synthétique produit un jeu conforme, reproductible et volontairement difficile.

Aucune variable agrégée dans ce lot, aucune modélisation. Le générateur écrit des événements horodatés bruts, jamais des agrégats. C'est la décision D3, et elle existe pour que le pipeline affronte la même difficulté que sur les données réelles.

## Documents à lire avant d'écrire

1. `AGENTS.md`, en entier
2. `docs/data-contract.md`, sections 1, 2 et 4. C'est le document de référence de ce lot
3. `docs/decisions.md`, en particulier D1, D3, D13 et D14
4. `docs/roadmap.md`, lot 1
5. `src/churn/config.py`, déjà écrit au lot 0, dont tu réutilises le chargement typé
6. `config/config.yaml`, section `sources.synthetic`, qui porte les paramètres du générateur

## Fichiers attendus

```text
src/churn/data/__init__.py
src/churn/data/schemas.py      declaration du contrat
src/churn/data/validate.py     controle des invariants
src/churn/data/synthetic.py    generateur d'evenements horodates
src/churn/data/sources.py      interface de source unique
tests/test_schemas.py
tests/test_validate.py
tests/test_synthetic.py
```

## Exigences

### `src/churn/data/schemas.py`

Déclaration du contrat des deux tables, `accounts` et `events`, telles que définies aux sections 1 et 2 du contrat de données.

- **Distinction entre noyau obligatoire et colonnes optionnelles.** `nb_licences` est optionnelle : une source qui ne la fournit pas reste conforme, et les variables qui en dépendent seront simplement absentes. Une colonne du noyau absente est en revanche une erreur.
- La nomenclature des types d'événement est fermée et compte treize valeurs. Elle vit ici, en un seul endroit. Aucune source n'a le droit d'en introduire une nouvelle : ajouter un type est une modification du contrat, qui se fait dans `docs/data-contract.md`.
- **Attention au coût de la validation.** N'utilise pas Pydantic pour valider les lignes une par une. Le jeu réel compte 21,5 millions de transactions, une validation ligne à ligne serait inexploitable. Pydantic sert ici à déclarer le schéma et ses métadonnées ; la vérification effective est vectorisée dans `validate.py`, avec pandas.
- La résolution temporelle attendue vient de `config.features.datetime_resolution`, actuellement `us`. Voir la section 3.5 du contrat pour le motif : sous pandas 3.0, mélanger `[us]` et `[ns]` fait échouer `merge_asof`.

### `src/churn/data/validate.py`

Contrôle des invariants listés aux sections 1 et 2 du contrat, en échec bloquant.

Invariants de `accounts` : identifiant unique et non manquant, date de résiliation strictement postérieure à la date de début, aucune date postérieure à l'exécution, revenu positif ou nul.

Invariants de `events` : tout identifiant existe dans `accounts`, aucun événement antérieur au début de contrat ni postérieur à la résiliation, type appartenant à la nomenclature, horodatage portant un fuseau.

- **Le rapport doit être lisible et actionnable.** Il nomme la table, l'invariant violé, le nombre de lignes fautives et un échantillon d'identifiants concernés. Un message du type « validation failed » est inutilisable sur un jeu de plusieurs millions de lignes.
- **Chaque invariant est vérifié indépendamment**, et le rapport les cumule. S'arrêter au premier échec obligerait à relancer la validation autant de fois qu'il y a de défauts.
- Une donnée fautive n'est jamais corrigée en silence. Voir le tableau des responsabilités en section 7 d'`AGENTS.md`.
- Les contrôles sont vectorisés. Aucune boucle Python sur les lignes.

### `src/churn/data/synthetic.py`

Générateur d'événements horodatés, piloté par `config.sources.synthetic`.

Il doit produire un problème difficile, pas un problème confortable. Au minimum :

- une saisonnalité hebdomadaire de l'activité, avec creux de fin de semaine
- trois profils de résiliation distincts, portés par des familles d'événements différentes
- un quatrième profil sans aucun signal précurseur, dont la part vient de `unpredictable_churn_share`. Il fixe le plafond de performance atteignable et empêche de se mentir sur la qualité du modèle
- des comptes qui présentent tous les signaux sans jamais résilier
- des horodatages dupliqués pour un même compte, selon `duplicate_timestamp_rate`. **Ce cas n'est pas décoratif** : il a produit 10,5 % de lignes fausses lors d'une mesure du 2026-09-07, sans lever la moindre erreur. Le générateur doit le produire pour que les lots suivants aient de quoi le détecter
- des valeurs manquantes et des trous d'observation, selon `missing_data_rate`
- une graine tirée de `config.project.random_seed`, jamais d'aléa non semé

**Reproductibilité stricte.** Deux exécutions à graine identique produisent des fichiers identiques. Cela vaut aussi pour l'ordre des lignes, qui doit être déterministe.

### `src/churn/data/sources.py`

Interface de source unique, que toute origine de données implémente. Le lot 2 y branchera l'adaptateur KKBox sans rien changer ailleurs.

Elle expose au minimum le chargement des deux tables et une description de la source, dont son caractère synthétique ou non. Le drapeau `is_synthetic` remonte jusqu'aux rapports, c'est la décision D2 qui l'exige.

L'écriture et la lecture se font en Parquet, via `pyarrow`. Les chemins viennent de `config.paths`, aucun module ne fabrique un chemin.

## Contrôles à exécuter avant de rendre

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest -q
```

Les quatre doivent passer.

## Critères d'acceptation

1. le jeu généré passe l'intégralité des contrôles de `validate.py`
2. un jeu volontairement corrompu, comportant un identifiant orphelin, un horodatage sans fuseau et un type d'événement inconnu, est rejeté avec trois messages distincts, chacun nommant son invariant
3. deux exécutions à graine identique produisent des fichiers strictement identiques
4. une source qui ne fournit pas une colonne optionnelle reste conforme
5. le taux de résiliation annuel produit correspond à `annual_churn_rate`, à une tolérance raisonnable près, et cette tolérance est justifiée dans le test

## Contraintes de dépôt

- Tu travailles sur la branche `lot-1-contrat-donnees`, déjà créée. N'en change pas et ne touche pas à `main`.
- Ne modifie ni `config/config.yaml`, ni `config/feature_mapping.yaml`, ni `pyproject.toml`, ni `uv.lock`. Si l'un d'eux te paraît fautif, signale-le dans ton rapport au lieu de le corriger.
- N'ajoute aucune dépendance.
- Aucun trailer d'attribution dans les messages de commit.
- Messages de commit en français, sans accents, pour rester homogène avec l'historique. Le tiret cadratin employé pour accoler une explication est proscrit.
- Code, noms de variables et docstrings en anglais.
- N'ouvre pas la pull request. Committe sur la branche et arrête-toi là.

## Rapport attendu

Trois sections courtes : ce que tu as fait, les tests avec leur sortie réelle, et ce qui demande attention. Un contrôle qui échoue se rapporte tel quel.
