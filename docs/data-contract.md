# Contrat de données

Ce document définit la forme des données que le pipeline consomme. Il est antérieur à toute implémentation, y compris celle du générateur synthétique. Voir décision D1.

Toute source de données, réelle ou simulée, doit produire exactement ces deux tables. Un adaptateur qui n'y parvient pas est un adaptateur incomplet, et non une raison d'assouplir le contrat.

## 1. Table `accounts`, référentiel des comptes

Une ligne par compte client. Vision à date, sans historique de modification en version 1.

| Colonne | Type | Nullable | Règle |
| :--- | :--- | :--- | :--- |
| `client_id` | chaîne | non | Identifiant unique et stable. Clé primaire. |
| `date_debut_contrat` | date | non | Date d'entrée en vigueur du contrat. Fixe l'ancienneté. |
| `date_resiliation` | date | oui | Date de fin effective. `null` pour un compte actif. C'est la source unique de la cible. |
| `type_contrat` | catégorie | non | Valeurs : `mensuel`, `annuel`, `pluriannuel`. |
| `mrr` | décimal | non | Revenu mensuel récurrent en euros, positif ou nul. |
| `segment` | catégorie | non | Valeurs : `TPE`, `PME`, `ETI`, `GrandCompte`. |
| `canal_acquisition` | catégorie | non | Valeurs : `direct`, `partenaire`, `inbound`, `marketplace`. |
| `nb_licences` | entier | non | Nombre de sièges souscrits, strictement positif. |

**Invariants vérifiés à l'ingestion, en échec bloquant :**

- `client_id` unique, sans valeur manquante
- `date_resiliation` strictement postérieure à `date_debut_contrat` quand elle est renseignée
- aucune date postérieure à la date d'exécution du pipeline
- `mrr` supérieur ou égal à zéro

## 2. Table `events`, journal d'événements

Une ligne par événement daté. C'est la seule source d'information comportementale.

| Colonne | Type | Nullable | Règle |
| :--- | :--- | :--- | :--- |
| `client_id` | chaîne | non | Clé étrangère vers `accounts.client_id`. |
| `event_ts` | horodatage | non | Horodatage de l'événement, en UTC, avec fuseau. |
| `event_type` | catégorie | non | Voir la nomenclature ci-dessous. |
| `event_value` | décimal | oui | Valeur portée par l'événement, selon son type. |

### Nomenclature des types d'événement

| `event_type` | Sens de `event_value` | Source métier |
| :--- | :--- | :--- |
| `connexion` | Nombre de sessions du jour | Produit |
| `usage_module_cle` | Durée d'usage en minutes | Produit |
| `desactivation_module` | Identifiant numérique du module | Produit |
| `ticket_support_ouvert` | Niveau de priorité, de 1 à 4 | Support |
| `ticket_support_resolu` | Délai de résolution en heures | Support |
| `facture_emise` | Montant en euros | Finance |
| `facture_payee` | Délai de paiement en jours, négatif si anticipé | Finance |
| `echec_prelevement` | Montant en euros | Finance |
| `contact_commercial` | Durée de l'échange en minutes | Commercial |

**Invariants vérifiés à l'ingestion, en échec bloquant :**

- tout `client_id` présent dans `events` existe dans `accounts`
- aucun `event_ts` antérieur à `date_debut_contrat` du compte, ni postérieur à `date_resiliation` quand elle existe
- `event_type` appartient à la nomenclature, une valeur inconnue est une erreur, jamais un rejet silencieux
- `event_ts` porte un fuseau horaire, une date naïve est refusée

## 3. Construction du jeu d'apprentissage

C'est le cœur du projet et l'endroit où se joue la validité de tout le reste.

### 3.1 Grille d'observation

Le jeu d'apprentissage est une grille de couples `(client_id, T0)`. Les dates `T0` sont espacées régulièrement, chaque lundi par défaut, sur toute la profondeur d'historique disponible.

Un couple `(client_id, T0)` entre dans la grille si et seulement si les trois conditions suivantes sont réunies à `T0` :

1. le compte est actif, c'est-à-dire `date_resiliation` absente ou postérieure à `T0`
2. l'ancienneté du compte atteint au moins 60 jours, soit `T0 - date_debut_contrat >= 60 jours`
3. l'historique disponible couvre au moins la plus longue fenêtre de calcul de variables, soit 90 jours

### 3.2 Cible

`y = 1` si `date_resiliation` tombe dans l'intervalle ouvert à gauche et fermé à droite `]T0, T0 + 60 jours]`. Sinon `y = 0`.

Un couple `(client_id, T0)` dont la fenêtre de cible dépasse la fin de l'historique disponible est écarté, car sa cible est inconnue et non pas nulle. Confondre les deux introduit un biais systématique en fin de période.

### 3.3 Règle de non-fuite

**Règle centrale : toute variable calculée pour un couple `(client_id, T0)` n'utilise que des événements strictement antérieurs à `T0`, et aucune colonne de `accounts` postérieure à `T0`.**

En pratique, cela interdit les usages suivants :

- utiliser `date_resiliation` dans une variable, sous quelque forme que ce soit, y compris une durée
- utiliser un événement du jour même de `T0` si l'horodatage n'est pas strictement inférieur à `T0`
- calculer une statistique de normalisation, moyenne ou écart-type, sur l'ensemble du jeu avant le découpage temporel
- imputer une valeur manquante à partir de statistiques calculées sur la période de test

Un test automatique, décrit en section 3.5, vérifie cette règle par construction.

### 3.4 Fenêtres de calcul autorisées

Les variables se calculent sur des fenêtres glissantes se terminant à `T0` : 7, 30 et 90 jours. Toute autre fenêtre doit être ajoutée explicitement au fichier de configuration, jamais codée en dur.

Les variables de tendance comparent deux fenêtres adjacentes, par exemple les 30 derniers jours contre les 30 précédents. Ce sont ces variables qui portent le signal actionnable, puisqu'un niveau absolu décrit un client alors qu'une rupture décrit un risque.

### 3.5 Pièges d'implémentation mesurés, à traiter obligatoirement

Ces trois points ne sont pas théoriques. Ils ont été reproduits sur ce poste, sur un jeu de 2 millions d'événements et une grille de 600 000 couples. Chacun produit des variables fausses sans lever la moindre erreur.

**Résolution temporelle sous pandas 3.0.** pandas gère désormais plusieurs résolutions d'horodatage. `pd.date_range` produit du `datetime64[us]`, alors qu'une construction par `pd.to_timedelta` peut produire du `datetime64[ns]`. Mélanger les deux fait échouer `merge_asof` avec `MergeError: incompatible merge keys`. C'est le cas favorable, puisque l'erreur est visible. La résolution doit être normalisée explicitement à l'ingestion, dans `validate.py`, et le contrôle doit être fait sur les deux tables.

**Réindexation par `merge_asof`.** La fonction retourne un résultat réordonné. Un `sort_index()` ne restaure pas l'ordre d'origine, et les colonnes se retrouvent affectées aux mauvaises lignes. Il faut conserver explicitement une colonne d'index d'origine et trier dessus après la jointure.

**Horodatages dupliqués.** Quand plusieurs événements partagent le même horodatage pour un même client, `merge_asof` ne garantit pas de retenir la dernière ligne du groupe, et le cumul récupéré est alors intermédiaire. Sur le jeu de test, cette seule cause produisait 63 319 lignes fausses sur 600 000, soit 10,5 %, silencieusement.

**Correction obligatoire** : agréger au cumul maximal par `(client_id, event_ts)` avant toute jointure temporelle, et couvrir ce cas par un test dédié construit sur des horodatages volontairement dupliqués.

### 3.6 Sentinelle anti-fuite

Un test obligatoire, `tests/test_no_leakage.py`, procède ainsi : il construit les variables pour un couple `(client_id, T0)` donné, puis reconstruit les mêmes variables après avoir supprimé du journal tous les événements postérieurs ou égaux à `T0`. Les deux résultats doivent être strictement identiques.

Si une seule variable diffère, elle regarde dans le futur. Le test échoue et la construction est fausse.

### 3.7 Contrôle par force brute

Second test obligatoire, complémentaire du précédent et de nature différente. La sentinelle vérifie qu'on ne regarde pas le futur ; ce contrôle vérifie que le calcul est juste.

Sur un échantillon aléatoire d'au moins 200 couples `(client_id, T0)`, chaque variable de fenêtre est recalculée par filtrage naïf, en parcourant les événements du client et en comptant ceux qui tombent dans l'intervalle. Le résultat doit correspondre exactement à celui de l'implémentation vectorisée.

Ce contrôle est le seul qui aurait détecté les 10,5 % de lignes fausses décrites en section 3.5. Aucune assertion sur des totaux, des moyennes ou des formes de tableau ne les repère. Il reste exigé quelle que soit la bibliothèque utilisée.

## 4. Schéma de sortie

Une ligne par client scoré, pour une date d'exécution donnée.

| Colonne | Type | Sens |
| :--- | :--- | :--- |
| `batch_run_id` | UUID | Identifiant de l'exécution, pour la traçabilité. |
| `date_scoring` | date | Date `T0` du scoring. |
| `client_id` | chaîne | Identifiant du compte. |
| `rang_priorite` | entier | Rang dans la liste, à partir de 1. |
| `decile_risque` | entier | Décile de risque, de 1, le plus risqué, à 10. |
| `is_top_k` | booléen | Le client appartient aux K premiers de la période. |
| `mrr` | décimal | Repris du référentiel, pour l'arbitrage commercial. |
| `facteur_risque_1` | chaîne | Libellé métier préfixé par sa source. |
| `facteur_risque_2` | chaîne | Idem, vide si le seuil de signification n'est pas atteint. |
| `facteur_risque_3` | chaîne | Idem. |
| `score_brut_technique` | décimal | Sortie non calibrée du modèle. Réservé au diagnostic. |
| `model_version` | chaîne | Version du modèle ayant produit le score. |

**Tri de sortie déterministe** : `score_brut_technique` décroissant, puis `mrr` décroissant, puis `client_id` croissant. Ce troisième critère garantit que deux exécutions sur les mêmes données produisent exactement le même fichier.

**Format** : `data/exports/scoring_<date>.parquet` comme source de vérité, doublé de `scoring_<date>.csv` en `utf-8-sig`.
