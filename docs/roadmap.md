# Roadmap

Neuf lots, séquentiels par construction : chacun consomme la sortie du précédent. Un lot n'est clos que si tous ses critères d'acceptation passent. Un lot clos ne se rouvre pas sans une entrée dans `decisions.md`.

**Contexte de planification.** Le projet alimente un portfolio destiné à une recherche d'emploi sur un poste de Data Scientist, avec une échéance inférieure à deux semaines. Les arbitrages correspondants sont actés en D16. La démonstration repose sur le jeu KKBox, le générateur synthétique servant les tests, décision D14.

**Convention d'effort** : une unité vaut une séance de travail cadrée, soit une implémentation par l'agent développeur suivie d'une revue. Ce n'est pas un jour-homme.

---

## Lot 0. Socle du dépôt

**Effort** : 1 unité. **Dépend de** : rien.

**Livrables**

- `pyproject.toml` avec contraintes de version, `uv.lock` versionné
- `src/churn/config.py`, chargement typé de la configuration par Pydantic
- `src/churn/logging.py`, journalisation structurée en JSON
- `.github/workflows/ci.yml` : `ruff`, `mypy`, `pytest`

**Critères d'acceptation**

1. `uv sync` puis `uv run pytest` passent sur un poste vierge
2. une clé absente du fichier de configuration lève une erreur explicite au démarrage, jamais une valeur par défaut silencieuse
3. l'incohérence entre `embargo_days` et `horizon_days` est détectée au démarrage
4. la CI est verte

---

## Lot 1. Contrat de données, validation et générateur synthétique

**Effort** : 2 unités. **Dépend de** : lot 0. **Référence** : `data-contract.md` sections 1 et 2, décisions D1, D3 et D14.

**Livrables**

- `src/churn/data/schemas.py`, schémas Pydantic des tables `accounts` et `events`, avec la distinction entre noyau obligatoire et colonnes optionnelles
- `src/churn/data/validate.py`, contrôle des invariants, échec bloquant avec un rapport lisible des lignes fautives
- `src/churn/data/synthetic.py`, générateur d'événements horodatés
- `src/churn/data/sources.py`, interface de source unique

**Le générateur sert désormais les tests, pas la démonstration.** Il reste exigeant sur les cas limites :

- trois profils de churn distincts, plus un profil sans signal antérieur représentant 20 à 30 % des résiliations
- des clients qui présentent les signaux sans résilier
- des horodatages dupliqués pour un même client, cas qui a produit 10,5 % de lignes fausses lors de la mesure du 2026-09-07
- des données manquantes et des trous d'observation
- une graine fixée et configurable

**Critères d'acceptation**

1. le jeu généré passe l'intégralité des contrôles de `validate.py`
2. un jeu volontairement corrompu, avec un identifiant orphelin, une date sans fuseau et un type d'événement inconnu, est rejeté avec trois messages distincts
3. deux exécutions à graine identique produisent des fichiers strictement identiques
4. une source qui ne fournit pas une colonne optionnelle reste conforme

---

## Lot 2. Adaptateur KKBox et reconstruction de la cible

**Effort** : 2 unités. **Dépend de** : lot 1. **Référence** : `dataset-kkbox.md`. **Dépendance externe** : accès Kaggle.

**Livrables**

- `src/churn/data/kkbox.py`, échantillonnage des comptes puis projection des fichiers sur le contrat
- `src/churn/data/target.py`, reconstruction de la cible depuis les transactions
- `scripts/download_kkbox.py`, téléchargement, décompression et échantillonnage, exécuté une seule fois

**Le socle suffit pour ce lot.** Les fichiers de transactions et de comptes, environ 1 Go, portent la cible et toutes les variables `FINANCE`. Les journaux d'écoute, 7,8 Go, ne sont requis qu'au lot 3. Voir la section 2.3 de `dataset-kkbox.md`.

**Trois pièges mesurés le 2026-09-07** : les fichiers sont livrés en `.7z` et non en CSV, les archives portent une arborescence interne `data/churn_comp_refresh/` à aplatir, et les fichiers suffixés `_v2` ne contiennent pas l'historique. Détails en sections 2.1 et 2.2 du même document.

**Critères d'acceptation**

1. les journaux d'écoute sont lus par morceaux, jamais chargés en une fois
2. l'échantillon est tiré parmi les comptes présents dans les transactions, et non dans le référentiel : sur 6,77 millions de comptes, seuls 2,36 millions ont une transaction
3. les données brutes restent sous `data/raw/` et n'apparaissent dans aucun commit
4. la colonne `bd` est explicitement rejetée, avec une trace dans le journal, et non ignorée en silence
5. les dates d'expiration aberrantes, jusqu'à `20361015`, sont bornées ou écartées explicitement
6. **la cible reconstruite est comparée à `train_v2.csv` sur le mois de référence, et le taux de concordance est consigné dans un rapport.** C'est le critère le plus important du lot. Référence mesurée : 970 960 comptes, dont 87 330 en churn, soit 8,99 %
7. le jeu projeté passe tous les contrôles de `validate.py` du lot 1, sans assouplissement

---

## Lot 3. Construction du jeu d'apprentissage

**Effort** : 3 unités. C'est le lot le plus risqué du projet. **Dépend de** : lot 2. **Référence** : `data-contract.md` section 3.

**Livrables**

- `src/churn/features/windows.py`, agrégations sur fenêtres glissantes de 7, 30 et 90 jours
- `src/churn/features/build.py`, grille `(client_id, T0)`, cible et matrice de variables
- `tests/test_no_leakage.py`, la sentinelle anti-fuite
- `tests/test_windows_bruteforce.py`, le contrôle par force brute

**Trois pièges mesurés à traiter dès l'écriture**, détaillés en section 3.5 du contrat de données : normalisation de la résolution temporelle sous pandas 3.0, conservation de l'ordre après `merge_asof`, et agrégation par horodatage avant jointure.

**Variables de tendance obligatoires.** Un niveau absolu décrit un client, une rupture décrit un risque. Sur KKBox, le taux de complétion d'écoute et son évolution portent le signal le plus intéressant.

**Critères d'acceptation**

1. la sentinelle anti-fuite passe sur au moins cinquante couples tirés au hasard
2. le contrôle par force brute passe sur au moins deux cents couples, avec zéro écart
3. un test dédié couvre le cas des horodatages dupliqués pour un même client
4. les couples dont la fenêtre de cible dépasse la fin de l'historique sont écartés, et non étiquetés à zéro
5. les comptes de moins de 60 jours d'ancienneté sont absents de la grille
6. un rapport Seaborn de distribution des variables par classe est produit dans `reports/`

---

## Lot 4. Protocole d'évaluation

**Effort** : 2 unités. **Dépend de** : lot 3. **Référence** : décisions D4 et D5.

Ce lot est délibérément placé avant toute modélisation. Un protocole d'évaluation ne se construit jamais après avoir vu les résultats d'un modèle.

**Livrables**

- `src/churn/evaluation/splitting.py`, découpage chronologique avec embargo et purge
- `src/churn/evaluation/metrics.py`, `precision_at_k` par période, rappel au rang K, lift contre le tri par revenu
- `src/churn/evaluation/baselines.py`, les trois lignes de base : hasard, tri par revenu décroissant, régression logistique
- `src/churn/evaluation/report.py`, rapport portant la mention de la source de données
- `src/churn/evaluation/protocol.py`, passage de tout classement dans les mêmes plis, périodes et K, pour que les lignes de base et le modèle du lot 5 soient comparés à armes égales
- `scripts/evaluate_baselines.py`, mesure des trois lignes de base sur une source donnée, sans accès réseau

**Critères d'acceptation**

1. `tests/test_split.py` échoue si une observation d'entraînement a une date de résolution de cible postérieure au début du test
2. `precision_at_k` sur un cas construit à la main donne la valeur attendue calculée manuellement
3. les trois lignes de base sont mesurées et consignées avant tout entraînement de modèle à arbres
4. tout rapport indique la source utilisée, KKBox ou synthétique

---

## Lot 5. Modélisation et explicabilité

**Effort** : 3 unités. **Dépend de** : lot 4. **Référence** : décisions D6, D7 et D12.

**Livrables**

- `src/churn/models/train.py`, entraînement et grille d'hyperparamètres réduite, décision D16
- `src/churn/models/explain.py`, contributions natives `pred_contribs` de XGBoost, agrégation par variable d'origine, extraction des trois facteurs
- `src/churn/models/registry.py`, sérialisation avec métadonnées : version, graine, seuil de signification, empreinte du jeu d'entraînement
- `src/churn/features/catalog.py`, variable d'origine et famille de chaque colonne, dont dépendent l'agrégation des contributions et la mesure par famille
- `scripts/train_model.py`, comparaison du modèle aux lignes de base dans le protocole du lot 4, puis entraînement, sauvegarde et explication de la dernière période
- les chapitres 8 et 9 du cours, `docs/cours/08-entrainer-le-modele.md` et `docs/cours/09-expliquer-les-predictions.md`

**Préalable découvert au démarrage, décision D18.** Le revenu utilisé comme variable et comme ligne de base venait de la dernière transaction du compte, différente du revenu en vigueur à `T0` sur 22,5 % des lignes de la grille. Il est désormais lu dans le journal, par l'événement `revenu_mensuel`, et les lignes de base sont remesurées sur la grille corrigée.

**Deux mesures, deux questions.** Le gain du modèle se mesure à variables égales, régression logistique contre XGBoost sur la seule famille financière. Le gain des données se mesure à modèle égal, XGBoost avec et sans la famille d'usage issue du journal d'écoute complet.

**Critères d'acceptation**

1. le modèle bat les trois lignes de base sur la Precision@K, résultat consigné. S'il ne les bat pas, c'est un résultat à publier et à expliquer, pas à masquer
2. les contributions d'une même variable d'origine sont sommées, vérifié par un test sur une variable encodée en indicatrices
3. la dernière colonne de `pred_contribs`, le biais, est explicitement écartée du classement des facteurs
4. le seuil de signification est calculé à l'entraînement, sérialisé, jamais écrit en dur
5. le rechargement d'un modèle sérialisé produit exactement les mêmes scores
6. un client sans facteur significatif obtient des libellés vides, et non des facteurs inventés

---

## Lot 6. Exécution batch et export

**Effort** : 1,5 unité. **Dépend de** : lot 5. **Référence** : `data-contract.md` section 4, décision D8.

**Livrables**

- `src/churn/pipeline/run_scoring.py`, point d'entrée en ligne de commande
- `src/churn/pipeline/sinks.py`, interface de destination, implémentations Parquet, CSV et JSON. La destination JSON prépare un front dédié éventuel sans jamais toucher au pipeline, voir décision D15
- `src/churn/pipeline/schemas.py`, schéma Pydantic de la ligne d'export

**Facteurs actionnables seulement, choix arrêté le 2026-09-14.** L'export n'affiche que des facteurs dont le libellé porte une action, c'est-à-dire aucun facteur de la famille `GENERAL` comme le revenu ou l'ancienneté. Ils continuent de peser dans le score, mais n'occupent pas une case de motif que le commercial ne pourrait pas exploiter. Consigné en D19.

**Livrables ajoutés au démarrage, décision D20.** `src/churn/pipeline/scoring.py` calcule rang, décile, facteurs et identité du lot, pour que `sinks.py` n'ait rien à transformer. `build_scoring_set` dans `features/build.py` construit la population du jour de scoring avec les règles et les variables de l'apprentissage, sans la règle d'issue connue. Le chapitre 10 du cours accompagne le lot.

**Critères d'acceptation**

1. deux exécutions consécutives sur les mêmes données produisent des fichiers identiques
2. `batch_run_id` et `model_version` figurent sur chaque ligne
3. le CSV s'ouvre dans Excel avec les accents corrects, vérification manuelle exigée
4. l'ajout d'une destination fictive dans un test ne demande aucune modification hors de `sinks.py`

---

## Lot 7. Interface Streamlit

**Effort** : 2 unités. **Dépend de** : lot 6. **Référence** : décision D15.

**Livrables**

- `app/streamlit_app.py`, application en lecture seule sur les fichiers produits par le lot 6
- déploiement public, avec l'adresse consignée dans le README
- `src/churn/interface/readers.py`, lecture des fichiers, testable sans Streamlit
- le fichier de contributions de l'export et les fichiers de données du rapport d'évaluation, sans lesquels les écrans 2 et 3 auraient dû recalculer, décision D21
- le chapitre 11 du cours

**Mise en ligne, décision D22.** L'application en ligne lit `demo/`, construit par `scripts/build_demo.py` : les mesures agrégées de KKBox et une chaîne simulée complète, sans aucune donnée individuelle KKBox. La publication sur Streamlit Community Cloud se fait avec le compte propriétaire du dépôt, et son adresse est consignée dans le README.

**Quatre écrans, par ordre de priorité**

1. la liste priorisée de la semaine, triable, avec rang, décile et trois facteurs de risque
2. la fiche d'un compte : chronologie de ses événements et contribution de chaque facteur
3. la courbe de Precision@K face aux trois lignes de base, qui est l'argument technique central
4. un bandeau permanent indiquant la source de données affichée

**Critères d'acceptation**

1. l'application ne recalcule aucun score et n'entraîne aucun modèle. Elle lit les exports
2. aucune valeur métier n'est écrite en dur dans l'application, tout vient de la configuration
3. l'application démarre sans erreur sur un export vide
4. le bandeau de source est visible sur les quatre écrans

**Enrichissements du 2026-09-14, demandés par le propriétaire du projet.** Un écran d'accueil, « Le projet », ouvre l'application : le problème, les chiffres clés lus dans le rapport d'évaluation, la méthode, les limites et les liens vers le code et le cours. La fiche d'un compte donne l'action conseillée sous chaque motif, lue dans `config/feature_mapping.yaml`, et un profil de l'abonné limité à ce qui était connu avant la date de scoring, calculé par `src/churn/interface/accounts.py`. Les critères ci-dessus valent pour les quatre écrans.

---

## Lot 8. README et mise en ligne

**Effort** : 1 unité. **Dépend de** : lot 7. **Référence** : décision D16.

Écrit en dernier, prévu dès le départ. C'est le premier et souvent le seul document lu.

**Mesure complémentaire préalable, choix arrêté le 2026-09-14.** Avant d'écrire les résultats, une dernière mesure dans le protocole du lot 4 : une grille de réglages élargie vers des modèles plus simples, la sélection du lot 5 se logeant dans son coin le plus prudent, et une régression logistique mieux préparée, avec régularisation choisie et comptages transformés. Le but est que la comparaison publiée résiste à l'objection d'une ligne de base trop faible. Les chiffres retenus remplacent ceux du lot 5 dans `docs/resultats.md` s'ils changent.

**Réalisée le 2026-09-14, décision D23.** La régression logistique réglée fait moins bien que la simple en tête de liste, 0,126 contre 0,149, et la grille élargie ne change pas le résultat au-delà du bruit, 0,323 contre 0,333. Le gain du modèle contre la plus forte des logistiques est de +0,176, positif sur les quatre plis. Ces chiffres ont été remplacés le même jour.

**Correction du 2026-09-14, décision D24.** En écrivant la définition exacte de la cible, un défaut est apparu : une résiliation KKBox était comptée à sa date, alors qu'elle n'est constatée que 30 jours plus tard. L'éligibilité, la règle d'issue connue, la purge et l'embargo sont corrigés, et la mesure refaite : Precision@50 de 0,274 pour XGBoost, 0,135 pour la régression logistique et 0,089 pour le tri par revenu. Les chiffres de référence du README sont ceux de cette mesure.

**Plan imposé**

1. le problème métier et la définition exacte de la cible
2. les données, leur origine, et pourquoi ce jeu plutôt qu'un autre
3. le protocole de validation, avec l'embargo expliqué en trois phrases
4. les résultats face aux trois lignes de base, chiffres à l'appui
5. l'explicabilité et un exemple concret de facteurs restitués
6. les limites assumées et ce qui manque encore
7. le lien vers l'application déployée et la commande pour reproduire

**Critères d'acceptation**

1. un lecteur non technique comprend le problème et le résultat en lisant les deux premières sections
2. un lecteur technique trouve l'embargo, la définition de la Precision@K et les lignes de base sans ouvrir le code
3. aucune affirmation de performance n'est faite sans indiquer la source de données correspondante
4. les limites sont écrites, pas éludées

**Livré le 2026-09-14, hors adresse en ligne.** README réécrit selon ce plan, chapitre 12 et quiz de la partie 4 du cours. La section 7 du README attend l'adresse de l'application, reportée après la publication sur Streamlit Community Cloud.

---

## Lot 9. Industrialisation

**Statut** : hors périmètre, conservé pour mémoire.

Connecteur CRM, delta sync, dead letter queue, circuit breaker, gestion des secrets, ordonnancement. Le détail figure aux sections 4 et 5 de `refs/table-ronde-cadrage-2026-08-28.md`. Ce lot redeviendrait pertinent pour un poste de Machine Learning Engineer.

---

## Chemin critique et charge

```text
Lot 0 ─► Lot 1 ─► Lot 2 ─► Lot 3 ─► Lot 4 ─► Lot 5 ─► Lot 6 ─► Lot 7 ─► Lot 8
 1u       2u       2u       3u       2u       3u      1,5u      2u       1u
                    ▲        ▲
              acces Kaggle  risque maximal
```

Charge totale : 17,5 unités. L'échéance annoncée est inférieure à deux semaines, ce qui laisse peu de marge. Deux points de vigilance.

L'accès Kaggle conditionne le lot 2 et doit être levé avant la fin du lot 1, sans quoi le chemin critique se décale d'autant.

Le lot 3 concentre le risque. S'il déborde, l'arbitrage se fait sur le lot 5, en réduisant la grille d'hyperparamètres, et sur le lot 7, en ne livrant que les écrans 1 et 3. Jamais sur les cinq points non négociables de la décision D16.
