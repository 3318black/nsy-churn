# Registre des décisions

Chaque décision est numérotée, datée et motivée. Une décision inscrite ici est close : l'agent développeur l'applique sans la rediscuter. Pour en changer, il faut modifier ce fichier, pas le code.

Statut possible : `Actée`, `Ouverte`, `Bloquée`, `Révisée`.

---

## D1. Le projet démarre sur données synthétiques, avec un contrat de données figé d'abord

**Statut** : Révisée le 2026-09-07 par D14. Le principe du contrat écrit en premier reste intégralement valable ; c'est le rôle du jeu synthétique qui change.

Aucune donnée réelle n'est disponible, alors que la cible est une mise en production. La séquence retenue est la suivante : écrire le contrat de données d'entrée, puis un générateur de données synthétiques qui respecte ce contrat, puis le pipeline complet sur ces données.

**Motif** : le contrat écrit en premier fait de l'origine des données un simple adaptateur. Le jour où les données réelles arrivent, seul le module de chargement change, et le reste du pipeline est déjà éprouvé. L'ordre inverse, générer d'abord et formaliser ensuite, produit un pipeline moulé sur les commodités du générateur.

**Conséquence non négociable** : les données synthétiques valident la mécanique du pipeline, jamais la performance du modèle. Aucun chiffre de performance obtenu sur données synthétiques ne sera communiqué comme une prévision de performance réelle. Voir D2.

---

## D2. Aucune promesse de performance avant les données réelles

**Statut** : Actée le 2026-09-07.

Les métriques produites sur données synthétiques sont étiquetées comme telles dans tous les rapports et graphiques, avec la mention explicite du caractère simulé du jeu.

**Motif** : un générateur écrit par la même personne que le modèle encode les relations que le modèle va retrouver. La performance mesurée dans ce cadre mesure la cohérence du générateur, pas le pouvoir prédictif. Présenter ce chiffre à une direction serait une faute professionnelle.

---

## D3. Le générateur produit un flux d'événements horodatés, pas une table de variables

**Statut** : Actée le 2026-09-07.

Le générateur écrit deux tables brutes : un référentiel de comptes et un journal d'événements datés. Il n'écrit jamais directement de variables agrégées.

**Motif** : générer directement des variables du type « nombre de tickets sur 30 jours » supprime précisément l'étape qui concentre le risque du projet, c'est-à-dire la construction de fenêtres temporelles sans fuite. Le pipeline doit affronter la même difficulté que sur les données réelles.

---

## D4. Validation temporelle avec embargo, jamais de découpage aléatoire

**Statut** : Actée le 2026-09-07.

Le découpage entraînement et test est strictement chronologique, avec un embargo au moins égal à l'horizon de prédiction. Cet horizon vaut 60 jours par défaut et 30 jours sur la source KKBox, où il découle de la définition officielle du churn. Le rapport entre les deux est vérifié au démarrage, la valeur absolue ne l'est pas. Toute observation d'entraînement dont la fenêtre de cible franchit la frontière de test est purgée.

**Motif** : détaillé en section 3.1 de `revue-spec-v3.md`. Sans embargo, la cible d'entraînement se résout dans la période de test et la validation devient mensongère.

**Test de non-régression associé** : `tests/test_split.py` doit échouer si une observation d'entraînement possède une date de résolution de cible postérieure au début de la période de test.

---

## D5. Precision@K définie par période de scoring

**Statut** : Actée le 2026-09-07.

`Precision@K` se calcule par semaine de scoring, puis se moyenne sur les semaines de la période d'évaluation. K représente la capacité de traitement hebdomadaire d'une équipe commerciale et vaut 50 par défaut.

Sur la source KKBox, aucune équipe commerciale n'existe. K y représente alors une capacité de traitement hypothétique, ce qui doit être écrit explicitement dans le rapport et le README. La métrique garde tout son sens comme mesure de qualité de tête de liste.

**Motif** : détaillé en section 3.2 de `revue-spec-v3.md`.

**Métriques secondaires obligatoires** : le rappel au rang K sur la même base, pour mesurer la part de churn effectivement capturée, et le lift par rapport au tri par revenu décroissant. Le ROC-AUC est calculé pour information mais ne pilote aucune décision, car il est peu sensible sur une classe rare.

---

## D6. Le rang et le décile de risque sont restitués, pas la probabilité brute

**Statut** : Actée le 2026-09-07.

L'export contient le rang de priorité, le décile de risque, et le score brut dans une colonne technique clairement nommée comme telle. La colonne présentée au métier n'est jamais un pourcentage.

**Motif** : la sortie d'un modèle à arbres n'est pas une probabilité calibrée. Le besoin métier est un ordre de priorité, pas une estimation de probabilité. Restituer un rang évite un contresens d'interprétation sans coûter un étage de calibration.

**Réserve** : si le métier exige un pourcentage, une calibration isotonique sur un fold temporel dédié devient obligatoire, et cette décision sera révisée.

---

## D7. Explicabilité par TreeSHAP, agrégée au niveau de la variable métier

**Statut** : Actée le 2026-09-07.

Les contributions SHAP sont sommées par variable d'origine avant l'extraction des trois principaux facteurs de risque. Seules les contributions positives au risque sont retenues. Le seuil de signification est calculé à l'entraînement comme un quantile de la distribution des contributions absolues, puis sérialisé avec le modèle.

**Motif** : détaillé en sections 3.4 et 3.5 de `revue-spec-v3.md`.

---

## D8. Restitution par export de fichiers, sans synchronisation CRM

**Statut** : Actée le 2026-09-07.

La sortie du pipeline est un fichier Parquet, source de vérité technique, doublé d'un CSV encodé en `utf-8-sig` pour l'ouverture directe dans Excel. Aucune dépendance CRM, aucune base de données en version 1.

**Motif** : décision produit prise le 2026-09-07. L'encodage `utf-8-sig` est retenu parce qu'Excel sous Windows interprète mal un UTF-8 sans marque d'ordre d'octets et casse les accents.

**Frontière de sortie** : le pipeline écrit ses résultats via une interface de destination unique. Ajouter une destination CRM ou une base consistera à implémenter cette interface, sans toucher au reste.

**Révision** : l'exclusion de toute interface web est levée par la décision D15. L'export de fichiers reste la sortie du pipeline, l'interface se contentant de lire ces fichiers.

---

## D9. Stack et versions

**Statut** : Actée le 2026-09-07.

Python 3.12 minimum, développement et validation sous 3.14.4. Gestion d'environnement et de verrouillage par `uv`.

Production : pandas, numpy, scikit-learn, xgboost, pydantic, pyarrow, pyyaml, seaborn, matplotlib. Développement seulement : shap, pytest, ruff, mypy. Le placement de `shap` hors production est motivé en D12.

**Motif** : les versions de la spec V3 datent du début 2024. Les versions courantes ont été vérifiées sur PyPI et la chaîne complète a été installée et testée sur ce poste le 2026-09-07.

**Règle de versionnage** : contraintes minimales dans `pyproject.toml` et verrouillage exact dans `uv.lock`, versionné. Pas de version exacte figée à la main dans le fichier de projet.

**Dette identifiée** : `seaborn 0.13.2` déclenche une dépréciation de matplotlib 3.11 qui deviendra une erreur en matplotlib 3.13. La contrainte `matplotlib<3.13` est posée et devra être levée à la prochaine version de seaborn.

---

## D10. Seaborn reste un outil d'analyse interne

**Statut** : Actée le 2026-09-07.

Les graphiques Seaborn servent l'analyse exploratoire, le diagnostic de fuite et les rapports d'évaluation destinés à l'équipe projet. Ils ne constituent pas le support de restitution de l'équipe commerciale, qui reçoit un tableau exploitable.

**Motif** : position du Designer au tour 1 de la table ronde, retenue. Une image statique n'est ni triable ni filtrable, donc inutilisable pour préparer une liste d'appels.

---

## D11. Dépôt public, flux par pull request, aucune licence

**Statut** : Actée le 2026-09-07.

Le code est hébergé sur `github.com/3318black/nsy-churn`, en dépôt public. La branche `main` est protégée, sans acteur autorisé à contourner la protection. Chaque lot part sur une branche `lot-<n>-<sujet>` et passe par une pull request. Le seul commit direct sur `main` est le commit d'amorçage, antérieur à la protection.

Aucune licence n'est publiée. Le dépôt est donc en tous droits réservés : le code est lisible, sa réutilisation n'est pas autorisée.

Aucun document tiers n'est versionné. Le support de cours ayant servi de modèle pour `AGENTS.md` est exclu par `.gitignore`, car le publier sur un dépôt public reviendrait à le redistribuer.

**Motif** : règles de travail posées par le propriétaire du dépôt. La protection sans acteur de contournement répond à un incident antérieur, où un bypass administrateur avait laissé passer un commit sur une branche censée être protégée.

---

## D12. XGBoost retenu, la bibliothèque shap sort de la production

**Statut** : Actée le 2026-09-07, après mesure.

Le modèle de production est XGBoost. Les contributions SHAP sont obtenues par `booster.predict(dmatrix, pred_contribs=True)`, la fonction native de XGBoost. La bibliothèque `shap` reste une dépendance de développement, réservée à l'exploration et à la comparaison de modèles.

**Mesures qui fondent la décision**, réalisées sur ce poste avec 20 000 observations et 30 variables :

| Modèle | Entraînement | TreeSHAP | Verdict |
| :--- | ---: | ---: | :--- |
| XGBoost | 1,63 s | 0,53 s | Retenu |
| LightGBM | 0,79 s | 1,01 s | Écarté, voir ci-dessous |
| scikit-learn `HistGradientBoostingClassifier` | 1,35 s | 1,44 s | Écarté, voir ci-dessous |

Les trois sont compatibles avec TreeSHAP, contrairement à ce que laissait craindre l'historique de la bibliothèque. Aucun des trois n'est disqualifié techniquement.

Le point décisif est ailleurs. Les contributions natives de XGBoost et celles de la bibliothèque `shap` ont été comparées ligne à ligne sur 2 000 observations : **l'écart maximal est exactement nul**, et la version native est légèrement plus rapide, 0,47 s contre 0,59 s. Or `shap` tire sept paquets supplémentaires, dont `numba` et `llvmlite`, soit environ 138 Mo. Un pipeline de production qui embarque un compilateur à la volée pour recalculer ce que le modèle sait déjà produire est une dépendance gratuite.

LightGBM est écarté pour une raison de robustesse et non de performance : `shap` émet un avertissement sur le changement de format de sortie pour ses classifieurs binaires, ce qui est une source d'erreur silencieuse. Le `HistGradientBoostingClassifier` de scikit-learn est écarté parce qu'il n'expose pas d'équivalent natif de `pred_contribs`, ce qui rendrait `shap` obligatoire en production.

**Réserve** : si un autre modèle devait être retenu plus tard, `shap` redevient une dépendance de production, et cette décision est révisée.

---

## D13. pandas conservé, avec deux garde-fous obligatoires

**Statut** : Actée le 2026-09-07, après mesure.

pandas reste la bibliothèque de manipulation de données. polars n'est pas introduit.

**Mesure**, sur le cas d'usage réel du lot 3, soit 2 millions d'événements et une grille de 600 000 couples `(client_id, T0)` : `polars.join_asof` s'exécute en 0,46 s contre 2,06 s pour `pandas.merge_asof`, soit un facteur 4,5. À ce volume, l'écart absolu est de 1,6 seconde dans un traitement nocturne. Il ne justifie pas une dépendance supplémentaire ni la coexistence de deux API dans le même dépôt, alors que le reste de la chaîne, scikit-learn, XGBoost et Seaborn, parle pandas.

**Ce que la mesure a réellement révélé est plus important que la vitesse.** La première implémentation pandas produisait 63 319 lignes fausses sur 600 000, soit 10,5 %, sans lever la moindre erreur. Deux causes, toutes deux propres à `merge_asof` :

1. `merge_asof` réindexe le résultat. Un `sort_index()` ne restaure donc pas l'ordre d'origine, et les colonnes sont réaffectées aux mauvaises lignes.
2. Quand plusieurs événements partagent le même horodatage, `merge_asof` ne garantit pas de retenir la dernière ligne du groupe. Le cumul récupéré est alors intermédiaire.

La correction consiste à conserver explicitement l'index d'origine, et à agréger au cumul maximal par `(client_id, event_ts)` avant la jointure. Après correction, pandas et polars donnent des résultats strictement identiques, tous deux vérifiés à zéro erreur contre un calcul de référence par force brute.

**Deux garde-fous deviennent donc obligatoires dans le lot 3 :**

- agrégation par `(client_id, event_ts)` avant tout `merge_asof`, avec un test dédié sur des horodatages dupliqués
- contrôle par force brute sur un échantillon aléatoire d'au moins 200 couples, comparant le résultat vectorisé à un filtrage naïf. Ce contrôle est indépendant de la bibliothèque et resterait exigé avec polars.

---

## D14. Deux sources de données, deux rôles distincts

**Statut** : Actée le 2026-09-07. Révise partiellement D1.

Le jeu KKBox porte la démonstration et toutes les mesures de performance. Le générateur synthétique reste, mais son rôle se réduit aux tests automatisés : rapide, reproductible, versionnable sous forme de graine, et couvrant les cas limites qu'un jeu réel ne contient pas.

**Motif** : la finalité du projet a changé le 2026-09-07. Il alimente un portfolio destiné à une recherche d'emploi sur un poste de Data Scientist. Or un portfolio qui annonce des données synthétiques produites par son propre auteur ne permet à personne de distinguer un bon modèle d'un générateur complaisant. La crédibilité de tout le reste en dépend.

Le détail de la projection figure dans `dataset-kkbox.md`. Deux conséquences de configuration : l'horizon passe à 30 jours pour cette source, conformément à la définition officielle du churn, et l'embargo suit.

**Ce qui ne change pas** : D2 reste intégralement valable. Tout rapport produit sur données synthétiques porte la mention correspondante. Pouvoir expliquer pourquoi le projet utilise deux sources et ce que chacune valide est un argument, pas une faiblesse.

**Dépendance bloquante** : compte Kaggle, acceptation des règles de la compétition, et jeton d'API. Absents du poste au 2026-09-07.

---

## D15. Interface Streamlit, construite après le lot 6

**Statut** : Actée le 2026-09-07. Révise D8, qui excluait toute interface.

Une interface web est ajoutée au périmètre. Technologie retenue : Streamlit. Elle est construite après le lot 6, jamais avant.

**Motif de l'ajout** : sur un portfolio, ce qui n'est pas visible n'existe pas. Un recruteur consacre quelques minutes à un dépôt et ne lira pas `features/windows.py` pour apprécier la rigueur du pipeline. L'interface est la porte d'entrée qui donne envie de lire le reste.

**Motif du choix de Streamlit** : Python pur, donc aucune compétence ni chaîne de construction supplémentaire, et un déploiement public gratuit qui fournit un lien cliquable depuis un CV. Une application FastAPI et React coûterait plusieurs fois plus pour un signal équivalent sur un poste de Data Scientist, où le jury évalue la méthode et non la chaîne de livraison.

**Motif de l'ordre** : une interface construite avant le pipeline façonne le pipeline pour l'affichage. Elle fait aussi courir le risque de ne jamais terminer la partie qui différencie réellement le candidat.

**Ce que l'interface doit montrer**, par ordre de priorité :

1. la liste priorisée de la semaine, triable, avec le rang, le décile et les trois facteurs de risque
2. la fiche d'un compte, avec la chronologie de ses événements et la contribution de chaque facteur
3. la courbe de Precision@K du modèle face aux trois lignes de base, qui est l'argument technique central
4. la mention explicite de la source de données affichée, KKBox ou synthétique

**Ce que l'interface ne doit pas être** : un tableau de bord générique de métriques, ni une page de démonstration où l'on saisit des valeurs pour obtenir un score. Ces deux formes sont les plus répandues et ne démontrent rien.

**Porte laissée ouverte vers un front dédié.** L'auteur pratique React et Next.js couramment. Un front dédié n'est donc pas écarté pour des raisons de compétence, mais de calendrier et de positionnement : sur une candidature en Data Scientist, le temps pris sur le pipeline coûterait plus qu'il ne rapporterait.

Cette option reste peu coûteuse à activer plus tard parce que l'architecture est entièrement batch. Un front lirait un export statique, sans backend, sans contrat d'API ni authentification. Pour que cela reste vrai, `sinks.py` doit exposer une destination JSON aux côtés de Parquet et CSV, dès le lot 6. C'est une implémentation de plus derrière l'interface de destination, soit quelques lignes, et elle évite d'avoir à revenir sur le pipeline le jour où le front arrive.

---

## D16. Arbitrages liés à l'échéance de deux semaines

**Statut** : Actée le 2026-09-07.

L'échéance annoncée est inférieure à deux semaines. Les allègements suivants sont actés, et il vaut mieux les décider maintenant que les subir plus tard.

**Ce qui est allégé :**

- `mypy` passe du mode strict au mode standard. Le typage strict d'un code de manipulation de données coûte cher en temps pour un gain faible sur ce périmètre. La contrainte reste dans `pyproject.toml`, en commentaire, pour être remise après l'échéance.
- La recherche d'hyperparamètres se limite à une grille réduite et documentée. Un gain de performance marginal ne se voit pas dans un portfolio, contrairement à un protocole d'évaluation correct.
- Le lot 9, l'industrialisation, reste hors périmètre.

**Ce qui n'est pas négociable, quelle que soit la pression du calendrier :**

- l'embargo et la sentinelle anti-fuite, décision D4
- le contrôle par force brute, décision D13
- les trois lignes de base avant tout modèle, décision D5
- le contrôle de concordance de la cible reconstruite contre l'étiquette officielle, section 5 de `dataset-kkbox.md`
- le README

Ces cinq points sont exactement ce qui distingue ce projet des centaines de projets de churn publics. Les sacrifier pour gagner deux jours reviendrait à livrer un projet de plus, indistinguable des autres.

**Le README est un livrable de première classe.** C'est le premier et souvent le seul document lu. Il doit exposer le problème, la définition de la cible, le protocole de validation, les résultats face aux lignes de base, et les limites assumées. Il est écrit en dernier, mais il est prévu dès maintenant.

---

## Points ouverts

| Réf | Question | Qui tranche | Bloque |
| :--- | :--- | :--- | :--- |
| O1 | Définition métier exacte du churn : résiliation contractuelle ferme, ou seuil d'inactivité ? | Métier | Le générateur et la construction de la cible |
| O2 | Capacité hebdomadaire réelle de l'équipe commerciale, qui fixe K | Métier | Le calibrage de la métrique, pas le code |
| O3 | Horizon de 60 jours : confirmé par le délai réel d'intervention commerciale ? | Métier | Le paramètre d'embargo et la construction de la cible |
| O4 | Accès Kaggle : compte, acceptation des règles et jeton d'API | Utilisateur | Le lot 2 de la roadmap |

Les trois premiers points ne bloquent pas le démarrage : les lots 0 et 1 se construisent avec les valeurs par défaut du fichier de configuration, et un changement de valeur ne demande aucune réécriture. Le quatrième, O4, bloque le lot 2 et doit être levé avant la fin du lot 1.
