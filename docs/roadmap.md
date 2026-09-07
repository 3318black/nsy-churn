# Roadmap

Sept lots, séquentiels par construction : chacun consomme la sortie du précédent. Un lot n'est clos que si tous ses critères d'acceptation passent. Un lot clos ne se rouvre pas sans une entrée dans `decisions.md`.

L'ordre diffère de celui de la spec V3. Le motif est en section 2 de `revue-spec-v3.md` : sans données, l'ancien sprint 1 ne peut pas démarrer.

**Convention d'effort** : une unité vaut une séance de travail cadrée, c'est-à-dire une implémentation par l'agent développeur suivie d'une revue. Ce n'est pas un jour-homme.

---

## Lot 0. Socle du dépôt

**Effort** : 1 unité. **Dépend de** : rien.

**Livrables**

- `pyproject.toml` avec contraintes de version, `uv.lock` versionné
- `config/config.yaml`, paramètres métier et techniques, aucune valeur en dur dans le code
- `config/feature_mapping.yaml`, correspondance entre variable technique et libellé métier
- `src/churn/config.py`, chargement typé de la configuration par Pydantic
- `src/churn/logging.py`, journalisation structurée en JSON
- `.github/workflows/ci.yml` : `ruff`, `mypy`, `pytest`

**Critères d'acceptation**

1. `uv sync` puis `uv run pytest` passent sur un poste vierge
2. une clé absente du fichier de configuration lève une erreur explicite au démarrage, jamais une valeur par défaut silencieuse
3. la CI est verte

---

## Lot 1. Contrat de données, validation et générateur synthétique

**Effort** : 2 unités. **Dépend de** : lot 0. **Référence** : `data-contract.md` sections 1 et 2, décisions D1 et D3.

**Livrables**

- `src/churn/data/schemas.py`, schémas Pydantic des tables `accounts` et `events`
- `src/churn/data/validate.py`, contrôle des invariants, échec bloquant avec un rapport lisible des lignes fautives
- `src/churn/data/synthetic.py`, générateur d'événements horodatés
- `src/churn/data/loader.py`, chargement depuis Parquet derrière une interface de source unique

**Le générateur doit produire un problème difficile, pas un problème confortable.** Il implémente au minimum :

- une saisonnalité hebdomadaire des connexions, avec creux le week-end
- trois profils de churn distincts : dégradation du support, désengagement produit, incident de paiement
- un quatrième profil de churn sans signal antérieur, entre 20 et 30 % des résiliations, qui fixe le plafond de performance atteignable
- du bruit : des clients qui présentent les signaux sans résilier
- des données manquantes et des trous d'observation, car aucune source réelle n'est complète
- une graine aléatoire fixée et configurable

**Critères d'acceptation**

1. le jeu généré passe l'intégralité des contrôles de `validate.py`
2. le taux de churn annuel généré se situe entre 8 et 15 %, valeur configurable
3. un jeu volontairement corrompu, avec un `client_id` orphelin, une date naïve et un `event_type` inconnu, est rejeté avec trois messages distincts
4. deux exécutions à graine identique produisent des fichiers strictement identiques

---

## Lot 2. Construction du jeu d'apprentissage

**Effort** : 3 unités. C'est le lot le plus risqué du projet. **Dépend de** : lot 1. **Référence** : `data-contract.md` section 3.

**Livrables**

- `src/churn/features/windows.py`, agrégations sur fenêtres glissantes de 7, 30 et 90 jours
- `src/churn/features/build.py`, construction de la grille `(client_id, T0)`, de la cible et de la matrice de variables
- `tests/test_no_leakage.py`, la sentinelle anti-fuite

**Critères d'acceptation**

1. la sentinelle anti-fuite passe sur au moins cinquante couples `(client_id, T0)` tirés au hasard
2. les couples dont la fenêtre de cible dépasse la fin de l'historique sont écartés, et non étiquetés à zéro
3. les comptes de moins de 60 jours d'ancienneté sont absents de la grille
4. le nombre de lignes produites est reproductible à graine constante
5. un rapport Seaborn de distribution des variables par classe est produit dans `reports/`

---

## Lot 3. Protocole d'évaluation

**Effort** : 2 unités. **Dépend de** : lot 2. **Référence** : décisions D4 et D5.

Ce lot est délibérément placé avant toute modélisation. Le protocole d'évaluation ne se construit jamais après avoir vu les résultats d'un modèle.

**Livrables**

- `src/churn/evaluation/splitting.py`, découpage chronologique avec embargo et purge
- `src/churn/evaluation/metrics.py`, `precision_at_k` par période, rappel au rang K, lift contre le tri par MRR
- `src/churn/evaluation/baselines.py`, les trois lignes de base : hasard, tri par MRR, régression logistique
- `src/churn/evaluation/report.py`, rapport d'évaluation avec la mention du caractère synthétique des données

**Critères d'acceptation**

1. `tests/test_split.py` échoue si une observation d'entraînement a une date de résolution de cible postérieure au début du test
2. `precision_at_k` sur un cas construit à la main donne la valeur attendue calculée manuellement
3. les trois lignes de base sont mesurées et consignées avant tout entraînement de modèle à arbres
4. tout rapport produit sur données synthétiques porte la mention correspondante en en-tête

---

## Lot 4. Modélisation et explicabilité

**Effort** : 3 unités. **Dépend de** : lot 3. **Référence** : décisions D6 et D7.

**Livrables**

- `src/churn/models/train.py`, entraînement, recherche d'hyperparamètres par validation temporelle
- `src/churn/models/explain.py`, TreeSHAP, agrégation par variable d'origine, extraction des trois facteurs
- `src/churn/models/registry.py`, sérialisation du modèle avec ses métadonnées, version, graine, seuil de signification, empreinte du jeu d'entraînement

**Critères d'acceptation**

1. le modèle bat les trois lignes de base sur la Precision@K, résultat consigné dans le rapport
2. les contributions SHAP d'une même variable d'origine sont sommées, vérifié par un test sur une variable encodée en indicatrices
3. le seuil de signification est calculé à l'entraînement, sérialisé, jamais écrit en dur
4. le rechargement d'un modèle sérialisé produit exactement les mêmes scores que la session d'entraînement
5. un client sans facteur de risque significatif obtient des libellés vides, et non des facteurs inventés

---

## Lot 5. Exécution batch et export

**Effort** : 2 unités. **Dépend de** : lot 4. **Référence** : `data-contract.md` section 4, décision D8.

**Livrables**

- `src/churn/pipeline/run_scoring.py`, point d'entrée en ligne de commande
- `src/churn/pipeline/sinks.py`, interface de destination, implémentations Parquet et CSV
- `src/churn/pipeline/schemas.py`, schéma Pydantic de la ligne d'export

**Critères d'acceptation**

1. deux exécutions consécutives sur les mêmes données produisent des fichiers identiques au bit près
2. `batch_run_id` et `model_version` figurent sur chaque ligne
3. le CSV s'ouvre dans Excel avec les accents corrects, vérification manuelle exigée
4. l'ajout d'une destination fictive dans un test ne demande aucune modification hors de `sinks.py`
5. un compte sans `client_id` ou de moins de 60 jours d'ancienneté est absent de l'export

---

## Lot 6. Bascule sur données réelles

**Effort** : non estimable à ce jour. **Statut** : bloqué par le point ouvert O4 de `decisions.md`.

**Travaux prévus**

- adaptateur de source réelle, conforme au contrat de données
- rapport d'écart entre les distributions réelles et simulées
- recalibrage de K, de l'horizon et du seuil de signification sur les données réelles
- réexécution complète du protocole d'évaluation, seuls ces chiffres ont valeur d'engagement

**Ce lot conditionne toute communication de performance vers le métier.** Voir décision D2.

---

## Lot 7. Industrialisation

**Effort** : à cadrer. **Statut** : hors périmètre de la version 1, conservé pour mémoire.

Contenu réactivable si la synchronisation CRM revient au programme : connecteur CRM, delta sync, dead letter queue, circuit breaker, gestion des secrets, ordonnancement. Le détail figure aux sections 4 et 5 de la spec V3, dans `refs/table-ronde-cadrage-2026-08-28.md`.

---

## Chemin critique

```text
Lot 0 ──► Lot 1 ──► Lot 2 ──► Lot 3 ──► Lot 4 ──► Lot 5 ──┐
                      ▲                                    │
              risque maximal                               ▼
                                                    Lot 6 (bloqué)
                                                          │
                                                          ▼
                                                    Lot 7 (optionnel)
```

Les lots 0 à 5 constituent la version 1 livrable. Ils ne dépendent d'aucune réponse métier : les valeurs par défaut de `config.yaml` suffisent, et les points ouverts O1 à O3 se règlent par un changement de paramètre.
