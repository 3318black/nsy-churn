# AGENTS.md

Manuel opératoire du projet `nsy-churn`. Ce fichier n'est pas une documentation utilisateur. Il s'adresse à l'agent développeur qui écrit le code.

Tu lis ce fichier avant toute action. Les décisions produit et architecture sont déjà prises : tu les appliques, tu ne les rejoues pas au moment d'implémenter.

---

## 1. Ce que nous construisons

Un moteur de prédiction de résiliation client. À une date donnée, il classe les comptes actifs par risque de résiliation dans les 60 jours, et livre pour chaque compte prioritaire les trois facteurs de risque qui expliquent son score.

L'utilisateur final est un commercial. Chaque lundi, il ouvre une liste de comptes à rappeler, triée par priorité, chaque ligne portant trois motifs lisibles du type `[SUPPORT] Hausse des tickets support`.

Ce qui fait la valeur du produit n'est pas le score. C'est le fait que le commercial sache quoi dire quand il décroche son téléphone. Un score sans motif actionnable ne sert à rien, et un motif inventé est pire qu'un motif absent.

**Dans le périmètre de la version 1** : contrat de données, générateur de données synthétiques, construction du jeu d'apprentissage sans fuite temporelle, protocole d'évaluation, modélisation, explicabilité locale, export de fichiers.

**Hors périmètre de la version 1** : toute synchronisation CRM, toute base de données, toute API HTTP, toute interface web, tout modèle de langage. Ne construis rien au-delà. Utile ne suffit pas, il faut que ce soit dans le périmètre.

---

## 2. Comment tu travailles

N'ouvre pas le code pour éditer immédiatement. La séquence est la suivante.

1. Lis `AGENTS.md`, puis `docs/decisions.md`, puis `docs/data-contract.md`, puis le lot concerné dans `docs/roadmap.md`
2. Inspecte le code et la configuration existants avant d'écrire
3. Pose une seule question ciblée, et seulement si la tâche est réellement ambiguë après ces lectures
4. Écris un prompt d'implémentation dans `prompts/<lot>-<sujet>.md`
5. Demande validation
6. Implémente uniquement après validation
7. Exécute les contrôles de la section 8
8. Termine par le rapport court de la section 9

Le prompt d'implémentation contient : l'objectif, les documents lus, le code inspecté, les décisions et hypothèses, les fichiers attendus, les exigences, les critères d'acceptation, les contrôles à exécuter et les tests manuels.

Cycle : **plan, revue, validation, implémentation, tests, correction, livraison.**

Le raisonnement détaillé appartient au fichier de prompt. Le message de fin reste court.

---

## 3. Règles de travail sur le dépôt

- Jamais de commit ni de push direct sur `main`. Une branche par lot, nommée `lot-<n>-<sujet>`, puis une pull request.
- Aucun trailer d'attribution dans les messages de commit ni dans les descriptions de pull request, sauf autorisation explicite demandée au préalable.
- Aucune donnée, aucun modèle sérialisé, aucun rapport généré dans le suivi de version. Voir `.gitignore`.
- Les messages de commit et la documentation sont rédigés en français, avec une ponctuation correcte. Le tiret cadratin employé pour accoler une explication est proscrit : construis la phrase, ou fais-en deux.
- Le code, les noms de variables, les docstrings et les messages de journalisation sont en anglais. La documentation et les libellés destinés au métier sont en français.

---

## 4. Stack

Python 3.12 minimum, développement sous 3.14. Environnement et verrouillage par `uv`.

`pandas`, `numpy`, `scikit-learn`, `xgboost`, `shap`, `pydantic`, `pyarrow`, `pyyaml`, `seaborn`, `matplotlib`, `pytest`, `ruff`, `mypy`.

**Ce qu'il ne faut pas utiliser :**

- pas de `simple-salesforce`, pas de client CRM, pas de `requests` vers un service tiers
- pas de PostgreSQL, pas de SQLAlchemy, pas de base de données en version 1
- pas de FastAPI, pas d'Uvicorn, pas de serveur HTTP. L'architecture est entièrement batch
- pas de framework d'orchestration, ni Airflow ni Prefect. Un point d'entrée en ligne de commande suffit
- pas de deep learning, pas de PyTorch, pas de TensorFlow
- pas d'appel à un modèle de langage pour traduire ou reformuler un facteur de risque. Le mapping est un dictionnaire statique, déterministe et testable
- pas de nouvelle dépendance sans une entrée justifiée dans `docs/decisions.md`

---

## 5. Décisions déjà prises

Elles sont dans `docs/decisions.md`, de D1 à D11. Les quatre qui cassent le plus souvent une implémentation :

- **D4** : découpage temporel avec embargo d'au moins 60 jours. Jamais de `train_test_split` aléatoire sur ces données.
- **D5** : `Precision@K` se calcule par semaine de scoring, puis se moyenne. Ce n'est pas un top K global.
- **D6** : la restitution montre un rang et un décile, jamais un pourcentage. Le score brut est une colonne technique.
- **D7** : les contributions SHAP sont sommées par variable d'origine avant l'extraction du top 3.

Si une consigne de tâche contredit une de ces décisions, arrête-toi et signale la contradiction. Ne tranche pas seul.

---

## 6. Modèle de données

Défini dans `docs/data-contract.md`. Deux tables d'entrée, `accounts` et `events`, une grille d'apprentissage `(client_id, T0)`, un schéma de sortie.

Le point à ne jamais perdre de vue : **toute variable calculée pour un couple `(client_id, T0)` n'utilise que des événements strictement antérieurs à `T0`.** La sentinelle de `tests/test_no_leakage.py` vérifie cette propriété par reconstruction. Si tu la modifies pour la faire passer, tu as cassé le projet.

---

## 7. Responsabilités des modules

| Module | Responsabilité | Ce qu'il ne fait pas |
| :--- | :--- | :--- |
| `data/schemas.py` | Contrats Pydantic des tables d'entrée | Ne transforme rien |
| `data/validate.py` | Contrôle des invariants, échec bloquant | Ne corrige jamais une donnée fautive en silence |
| `data/synthetic.py` | Génération d'événements horodatés | Ne génère aucune variable agrégée |
| `data/loader.py` | Lecture depuis une source, derrière une interface | Ne calcule aucune variable |
| `features/windows.py` | Agrégations sur fenêtres glissantes | N'accède pas à la cible |
| `features/build.py` | Grille, cible, matrice de variables | Ne modélise pas |
| `evaluation/splitting.py` | Découpage temporel avec embargo et purge | N'entraîne rien |
| `evaluation/metrics.py` | Métriques de tête de liste | Ne trace aucun graphique |
| `models/train.py` | Entraînement et recherche d'hyperparamètres | Ne définit aucune métrique |
| `models/explain.py` | TreeSHAP, agrégation, extraction du top 3 | N'écrit aucun fichier de sortie |
| `pipeline/sinks.py` | Écriture vers une destination | Ne transforme aucune valeur |

Deux règles transverses. Aucune valeur métier en dur dans le code : tout paramètre passe par `config/config.yaml`. Aucun module ne fabrique un chemin de fichier lui-même : les chemins viennent de la configuration.

---

## 8. Contrôles à exécuter

Avant toute demande de revue :

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest -q
```

Et selon la nature du changement :

- si tu touches à la construction des variables, exécute `pytest tests/test_no_leakage.py -v` et rapporte le résultat explicitement
- si tu touches au découpage ou aux métriques, exécute `pytest tests/test_split.py tests/test_metrics.py -v`
- si tu touches à l'export, ouvre le CSV produit et vérifie de visu les accents et le séparateur
- si tu produis des chiffres de performance sur données synthétiques, vérifie que le rapport porte bien la mention correspondante

Ce qui doit être testé sans exception : le chemin nominal, le jeu vide, une valeur manquante dans chaque colonne critique, un client sans aucun événement, un client résilié le jour même de `T0`, une fenêtre de cible qui dépasse la fin de l'historique.

---

## 9. Rapport de fin

Trois sections, courtes.

1. **Ce que j'ai fait**
2. **Tests**, avec les commandes exécutées et leur résultat réel, y compris les échecs
3. **Ce qui demande ton attention**, hypothèses prises, dette introduite, points restés ouverts

Un test qui échoue se rapporte tel quel, avec sa sortie. Une étape sautée se signale. Ne présente jamais comme vérifié ce qui ne l'a pas été.

---

## 10. Erreurs à ne pas commettre

Recensées à partir de la revue de la spec initiale, dans `docs/revue-spec-v3.md`.

- utiliser `train_test_split` avec `shuffle=True` sur des données temporelles
- oublier l'embargo entre entraînement et test, et livrer une performance flatteuse et fausse
- calculer une statistique de normalisation ou d'imputation avant le découpage temporel
- étiqueter à zéro un couple dont la fenêtre de cible dépasse l'historique disponible
- prendre un top K global au lieu d'un top K par période de scoring
- afficher trois fois la même variable métier sous trois modalités encodées
- figer un seuil de signification SHAP en dur, sans l'avoir mesuré
- présenter un score de modèle à arbres comme une probabilité
- ajouter une dépendance parce qu'elle est pratique, sans passer par `docs/decisions.md`
- traiter les chiffres obtenus sur données synthétiques comme une prévision de performance réelle
