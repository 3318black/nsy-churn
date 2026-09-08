# Prompt d'implémentation, lot 0 : socle du dépôt

## Objectif

Rendre le dépôt exécutable et vérifiable. À la fin de ce lot, `uv sync` puis `uv run pytest` doivent passer sur un poste vierge, la configuration doit se charger de façon typée en échouant explicitement sur toute incohérence, et l'intégration continue doit être verte.

Aucune logique métier dans ce lot. Ni données, ni variables, ni modèle.

## Documents à lire avant d'écrire

1. `AGENTS.md`, en entier
2. `docs/decisions.md`, en particulier D9, D13 et D16
3. `docs/roadmap.md`, lot 0
4. `config/config.yaml` et `config/feature_mapping.yaml`, qui existent déjà et ne doivent pas être modifiés
5. `pyproject.toml` et `uv.lock`, qui existent déjà et sont verrouillés

## Fichiers attendus

```text
src/churn/__init__.py
src/churn/config.py          chargement typé de la configuration
src/churn/logging.py         journalisation structurée en JSON
tests/__init__.py
tests/conftest.py
tests/test_config.py
.github/workflows/ci.yml
```

## Exigences

### `src/churn/config.py`

Modèles Pydantic reflétant la structure réelle de `config/config.yaml`. Cette structure comporte une clé `active_source` et un dictionnaire `sources` contenant deux profils, `kkbox` et `synthetic`, dont les champs diffèrent partiellement.

- **Aucune valeur par défaut silencieuse.** Une clé absente du fichier lève une erreur explicite au chargement, nommant la clé fautive. C'est le critère d'acceptation 2 et il n'est pas négociable.
- Les chemins de la section `paths` sont exposés en `Path`, résolus relativement à la racine du projet.
- **Validation croisée obligatoire** : pour chaque profil de `sources`, `embargo_days` doit être supérieur ou égal à `horizon_days`. Un profil qui viole cette règle fait échouer le chargement en nommant le profil concerné. Le motif est en décision D4 : un embargo plus court que l'horizon laisse la cible d'entraînement se résoudre dans la période de test.
- Une fonction d'accès au profil actif, qui échoue si `active_source` ne correspond à aucune clé de `sources`.
- Le chargement de `config/feature_mapping.yaml` est également typé. Chaque entrée porte `label`, `source` et `action`. Le champ `source` est contraint aux valeurs `SUPPORT`, `PRODUCT`, `FINANCE`, `COMMERCIAL` et `GENERAL`. Le champ `action` peut être vide, jamais absent.

### `src/churn/logging.py`

Journalisation structurée émettant du JSON sur la sortie standard, une ligne par événement, avec au minimum l'horodatage en UTC, le niveau, le nom du module et le message.

- **Aucune dépendance nouvelle.** Utilise le module `logging` de la bibliothèque standard avec un formateur maison. Ajouter un paquet exigerait une entrée dans `docs/decisions.md`, ce qui n'est pas le sujet de ce lot.
- Les horodatages portent un fuseau. Les règles `DTZ` de `ruff` sont actives et refuseront un `datetime` naïf.
- Une fonction de configuration idempotente : l'appeler deux fois ne doit pas dupliquer les gestionnaires.

### `tests/`

Couvre au minimum les cas suivants.

1. Le chargement de `config/config.yaml`, le vrai fichier du dépôt, réussit.
2. Une configuration à laquelle il manque une clé obligatoire échoue, et le message nomme la clé.
3. Une configuration dont un profil a `embargo_days` inférieur à `horizon_days` échoue, et le message nomme le profil.
4. Un `active_source` inconnu échoue explicitement.
5. Le chargement de `config/feature_mapping.yaml` réussit et une entrée dont `source` vaut une valeur hors nomenclature échoue.
6. La journalisation produit une ligne JSON valide, contenant les champs attendus.

Les configurations fautives se construisent dans des fichiers temporaires, via `tmp_path`. Ne modifie jamais les fichiers de `config/`.

### `.github/workflows/ci.yml`

Déclenchement sur `push` et `pull_request`. Installation par `uv`, puis dans l'ordre : `ruff check`, `ruff format --check`, `mypy src`, `pytest`.

Matrice sur Python 3.12 et 3.14, qui sont respectivement le minimum déclaré et la version de développement.

## Contrôles à exécuter avant de rendre

```bash
uv sync
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest -q
```

Les quatre doivent passer. Si `ruff format --check` échoue, lance `uv run ruff format src tests` puis recommence.

## Critères d'acceptation

1. `uv sync` puis `uv run pytest` passent sur un poste vierge
2. une clé absente du fichier de configuration lève une erreur explicite au démarrage, jamais une valeur par défaut silencieuse
3. l'incohérence entre `embargo_days` et `horizon_days` est détectée au démarrage
4. la CI est verte

## Contraintes de dépôt

- Tu travailles sur la branche `lot-0-socle`, déjà créée. N'en change pas et ne touche pas à `main`.
- Aucun trailer d'attribution dans les messages de commit. Ni `Co-Authored-By`, ni mention d'outil.
- Messages de commit en français. Le tiret cadratin employé pour accoler une explication est proscrit : construis la phrase ou fais-en deux.
- Code, noms de variables et docstrings en anglais.
- N'ouvre pas la pull request. Committe sur la branche et arrête-toi là.

## Rapport attendu

Trois sections courtes.

1. **Ce que j'ai fait**
2. **Tests**, avec les commandes exécutées et leur sortie réelle, échecs compris
3. **Ce qui demande attention**, hypothèses prises, dette introduite, points restés ouverts

Un test qui échoue se rapporte tel quel. Ne présente jamais comme vérifié ce qui ne l'a pas été.
