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

**Précision du 2026-09-14, décision D24.** La cible se résout quand elle est constatée, pas quand elle est datée. Sur KKBox, une résiliation n'est acquise que 30 jours après sa date : l'embargo couvre l'horizon et ce délai de constat réunis, soit 60 jours, et la purge compte à partir de la date de constat.

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

**Statut** : Actée le 2026-09-07. L'échéance a été levée le 2026-09-13 ; la grille réduite est révisée par D23.

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

## D17. La grille démarre avec le journal, et un compte n'y entre qu'une fois observé

**Statut** : Actée le 2026-09-13, après mesure sur KKBox.

Deux règles d'éligibilité s'ajoutent à la construction de la grille. Les dates d'observation commencent au premier événement du journal, augmenté de la profondeur d'historique minimale, et non à la plus ancienne date d'inscription. Un couple `(client_id, T0)` n'entre dans la grille que si le compte présente au moins un événement strictement antérieur à `T0`.

**Mesure qui fonde la décision.** Sur un échantillon KKBox de 8 150 comptes, les inscriptions remontent à 2004 alors que les transactions ne commencent qu'en janvier 2015. La grille partait donc de 2004 : 662 dates hebdomadaires et 1 202 169 lignes, dont 56 % antérieures à 2015, où aucune résiliation ne pouvait être observée. Les quatre plis d'entraînement ne contenaient pas un seul positif. La régression logistique, réduite à des scores constants départagés par le revenu, reproduisait exactement le tri par revenu. Le protocole avait produit un chiffre, pas une mesure.

Une fois la grille recalée sur le journal, 20,5 % des lignes restantes portaient encore un compte sans aucun événement antérieur à `T0`, c'est-à-dire inscrit mais pas encore client. Prédire la résiliation de quelqu'un qui n'a jamais souscrit n'a pas de sens pour une équipe de rétention.

**Absence de fuite.** La date du premier événement est lue strictement avant `T0`. Cette règle-ci ne dépend donc d'aucun fait postérieur à sa date d'observation.

*Rectification du 2026-09-14.* Cette décision affirmait que l'éligibilité entière ne dépendait d'aucun fait postérieur à `T0`. C'était faux sur KKBox pour la règle du compte actif, qui lisait la date de résiliation brute alors qu'une résiliation n'y est constatée que 30 jours plus tard. Corrigé par la décision D24.

**Garde-fou ajouté.** Le protocole d'évaluation refuse désormais un pli dont l'entraînement ne contient qu'une seule classe, au lieu de laisser une ligne de base produire des scores constants en silence.

**Pourquoi le jeu synthétique ne l'avait pas révélé.** Ses comptes commencent à produire des événements le jour même de leur souscription. Inscription et début du journal y coïncident, et le défaut restait invisible.

---

## D18. Le revenu d'un couple se lit dans le journal à sa date d'observation, jamais dans le référentiel

**Statut** : Actée le 2026-09-13, après mesure sur KKBox.

Un type d'événement s'ajoute à la nomenclature, `revenu_mensuel`, qui enregistre le revenu mensuel en vigueur à chaque changement de contrat. Le revenu d'un couple `(client_id, T0)` est la dernière valeur de ce type strictement antérieure à `T0`, et zéro quand aucune n'est encore connue. C'est lui qui alimente la variable `mrr`, le tri par revenu et le départage des égalités. La colonne `mrr` du référentiel décrit le compte à la date d'extraction : elle garde sa place dans l'export, jamais dans l'apprentissage ni dans l'évaluation.

**Mesure qui fonde la décision.** Sur KKBox, l'adaptateur calculait le revenu du référentiel à partir de la dernière transaction de chaque compte, parfois postérieure de plusieurs mois à la date d'observation. Sur la grille hebdomadaire de l'échantillon de 8 150 comptes, soit 410 523 couples, la valeur figée différait de la valeur en vigueur dans 22,5 % des cas, et dans 32,6 % des couples positifs. Dans le journal projeté, 34 % des comptes ont connu plus d'un revenu. La section 3.3 du contrat l'interdisait déjà : aucune colonne du référentiel postérieure à `T0`.

**Le sens de l'effet dépend de la mesure, la violation non.** Sur cette grille, le revenu figé obtient un meilleur ROC-AUC que le revenu en vigueur, 0,641 contre 0,607 : l'écart se concentre sur les comptes qui partent, dont la dernière transaction reflète souvent un changement de formule ou une annulation. En tête de liste, c'est l'inverse : sur les dates de test, la Precision@50 du tri par revenu vaut 0,0795 avec le revenu figé et 0,0980 avec le revenu en vigueur. Mais chaque semaine, 141 à 261 comptes partagent le revenu maximal, et leur ordre relève du départage par identifiant. Aucune conclusion du type « la fuite flattait le résultat » n'est donc retenue. Ce qui est établi : la règle était violée, le classement en dépendait, et les lignes de base sont remesurées au lot 5 sur la grille corrigée. Une première mesure faite le même jour, sur des dates mensuelles et les seuls comptes ayant déjà une transaction, n'est pas retenue : elle portait sur une autre population.

**Revenu inconnu.** 27,3 % des couples n'ont encore aucun revenu connu à `T0` et portent zéro. Sur KKBox, ce zéro ne désigne pas un compte gratuit : l'extrait ne contient aucune transaction antérieure à 2015, et un abonné à une formule longue souscrite avant n'apparaît qu'à son renouvellement. Il signifie « aucun revenu connu dans le journal ».

**Pourquoi la sentinelle ne l'avait pas vu.** Elle tronque le journal à `T0` et vérifie que rien ne change ; elle ne touche pas au référentiel. Un second test la complète : réécrire toutes les colonnes du référentiel dont aucune règle de la grille n'a besoin ne doit changer ni la grille ni les variables.

**Un état, pas un flux.** `revenu_mensuel` se lit à la date et ne se somme jamais sur une fenêtre : additionner un revenu mensuel sur 90 jours n'a pas de sens. Plusieurs valeurs au même instant se résolvent par leur maximum, pour que le résultat ne dépende pas de l'ordre d'arrivée des lignes.

---

## D19. L'export n'affiche que des facteurs actionnables

**Statut** : Actée le 2026-09-14, au démarrage du lot 6.

Seules les variables d'origine dont le libellé porte une action concourent aux trois cases de facteur de l'export. Les variables structurelles, dont l'action est vide dans `config/feature_mapping.yaml`, comme le revenu en vigueur ou l'ancienneté, continuent de peser dans le score, mais n'occupent jamais une case.

**Motif.** Au lot 5, le premier compte de la dernière période affichait « [GENERAL] Revenu mensuel en vigueur » en premier facteur. Un commercial ne peut rien en faire : on n'agit ni sur l'ancienneté d'un abonné ni sur le prix qu'il paie pour le retenir. Une case prise par un facteur sans levier masque un motif sur lequel il pourrait agir. La table ronde du 28 août l'avait d'ailleurs posé dès le premier tour : isoler les variables actionnables des simples variables structurelles.

**Ce qui ne change pas.** Le seuil de signification reste celui calculé à l'entraînement sur toutes les variables d'origine. Un compte dont seuls des facteurs structurels sont significatifs reçoit des cases vides, jamais un motif inventé.

---

## D20. Un export reproductible et lisible sans outil

**Statut** : Actée le 2026-09-14, au démarrage du lot 6.

Quatre règles fixent la forme de l'export.

**Identifiant de lot déterministe.** `batch_run_id` est un UUID de version 5, dérivé de la version du modèle, de la date de scoring et d'une empreinte des lignes scorées et de leurs variables. Un UUID aléatoire rendait impossible le premier critère du lot 6, deux exécutions sur les mêmes données produisant des fichiers identiques. L'identifiant reste unique par lot réel : toute différence d'entrée en produit un autre.

**Revenu à la date de scoring.** La colonne `mrr` de l'export est le revenu en vigueur à la date de scoring, lu dans le journal comme pour l'apprentissage, décision D18. C'est aussi celui du départage des égalités. Il coïncide avec le revenu du référentiel quand la date de scoring est la date d'extraction.

**Population de scoring.** Les comptes scorés obéissent aux mêmes règles d'éligibilité que la grille d'apprentissage, sans la règle d'issue connue, qui n'a pas de sens le jour du scoring. Leurs variables sont calculées par la même fonction, vérifiée par un test d'égalité sur une date commune. Sans date explicite, la date de scoring est la dernière date d'observation que le journal permet.

**Fichiers.** Trois fichiers par date, sous `paths.exports/<source>/` : `scoring_<date>.parquet`, source de vérité portant l'identité du lot dans ses métadonnées ; `scoring_<date>.csv`, en `utf-8-sig`, séparateur `;` et virgule décimale pour Excel en français ; `scoring_<date>.json`, identité du lot suivie des lignes, pour un front dédié éventuel, décision D15. Le dossier par source empêche un export simulé de côtoyer un export réel.

---

## D21. L'interface lit des fichiers, elle ne calcule rien

**Statut** : Actée le 2026-09-14, au démarrage du lot 7.

Tout ce qu'affiche l'application Streamlit est lu dans des fichiers produits par le pipeline. Elle n'importe aucun code d'entraînement, de variables ou de scoring, ce qu'un test vérifie sur l'arbre syntaxique de ses imports.

**Ce que le pipeline écrit en plus.** La fiche d'un compte doit montrer la contribution de chaque facteur, et la courbe de performance la précision de chaque semaine. Aucune des deux ne se trouvait dans un fichier. Deux ajouts les rendent lisibles sans recalcul :

- à côté de chaque export, `scoring_<date>_contributions.parquet`, une ligne par compte et par variable d'origine, avec son libellé, sa contribution et son caractère actionnable. Le seuil de signification rejoint l'identité du lot, dans les métadonnées ;
- à côté du rapport d'évaluation, `evaluation_summary.csv` et `evaluation_precision_per_period.csv`, chacun ouvert par la ligne qui nomme sa source.

**L'historique d'un compte s'arrête strictement avant la date de scoring.** Montrer les événements qui ont suivi afficherait ce que le modèle ne pouvait pas savoir, et inviterait à lire le futur dans le classement.

**Le profil de l'abonné suit la même règle, précisée le 2026-09-14.** Il est calculé sur les événements strictement antérieurs à la date de scoring : dernier usage, jours actifs sur 30 jours, dernière facture, annulations et renouvellements automatiques désactivés. Du référentiel, seule la date d'inscription est affichée, parce qu'elle est un fait figé du passé. Le type de contrat est écarté, il décrit le compte à la date d'extraction, décision D18. Le segment et le canal d'acquisition le sont aussi, ce ne sont sur KKBox que des codes sans signification. La date de résiliation, fait du futur, n'est jamais lue. L'action conseillée sous chaque motif vient du dictionnaire statique `config/feature_mapping.yaml`, aucun texte n'est généré.

**Séparation du code.** La lecture des fichiers vit dans `churn.interface.readers`, testable sans Streamlit. L'application, dans `app/`, ne fait qu'afficher. Elle se teste sans navigateur avec `streamlit.testing.v1.AppTest`, sur une racine de projet temporaire désignée par la variable d'environnement `NSY_CHURN_ROOT`.

**Mise en ligne publique.** Streamlit Community Cloud installe les dépendances depuis `uv.lock`, mais l'application en ligne devrait lire des fichiers dérivés de KKBox, dont le journal d'écoute. Les règles de la compétition encadrent l'usage et la redistribution des données, et leur texte n'a pas pu être relu automatiquement. Le choix des données publiées, point ouvert O5, a été tranché par le propriétaire du projet : décision D22.

---

## D22. La démonstration en ligne publie des agrégats KKBox et une chaîne simulée

**Statut** : Actée le 2026-09-14 par le propriétaire du projet. Tranche le point ouvert O5.

L'interface en ligne ne publie aucune donnée individuelle KKBox : ni export, ni contributions, ni journal, ni liste de comptes. Elle publie :

- les deux fichiers de mesures agrégées du rapport d'évaluation KKBox, une ligne par classement ou par classement et par semaine ;
- une chaîne simulée complète de 300 comptes, journal, export, contributions et rapport, pour parcourir la liste et la fiche d'un compte sous le bandeau des données simulées.

**Motif.** Les règles de la compétition encadrent l'usage et la redistribution des données, et leur texte n'a pas pu être vérifié. Les mesures agrégées ne décrivent aucun abonné et portent l'argument central du projet. Les identifiants et les historiques d'écoute sont écartés par prudence.

**Mise en œuvre.** Le dossier `demo/` est une racine de projet complète, construite par `scripts/build_demo.py`, qui refuse de copier un fichier portant une colonne d'identifiant. L'application en ligne le lit par la variable `NSY_CHURN_ROOT`, déclarée dans les secrets de Streamlit Community Cloud et résolue depuis la racine du dépôt. Sa configuration renseigne `interface.missing_export_notice`, qui explique, à la place de la liste KKBox, pourquoi elle n'est pas publiée. Deux tests gardent la règle : les seuls fichiers KKBox de `demo/` sont les deux agrégats, et tout identifiant publié suit le format du générateur synthétique.

**Exception au suivi de version.** `demo/` est le seul dossier de données versionné, parce qu'une application en ligne lit ses fichiers depuis le dépôt. Il ne contient que des données simulées et des agrégats.

---

## D23. Mesure complémentaire : grille élargie et régression logistique réglée

**Statut** : Actée le 2026-09-14. Décidée avant la mesure, consignée après. Révise la grille réduite de D16.

Deux changements ont été décidés avant de mesurer, pour que leur résultat ne puisse pas les choisir.

- **La grille XGBoost passe de 8 à 24 combinaisons**, vers des modèles plus simples : profondeurs 2, 3, 4 et 6, et 100, 300 ou 600 arbres. La grille réduite de D16 tenait à une échéance, levée depuis.
- **Une régression logistique réglée rejoint les lignes de base.** Elle compresse les variables par un logarithme signé, puis choisit sa force de régularisation parmi 0,01, 0,1, 1 et 10, sur la même validation interne que XGBoost. La sélection devient une fonction générique, `churn.evaluation.selection`.

**Motif.** Au lot 5, la sélection se logeait dans le coin le plus prudent de la grille, et la régression logistique n'était pas réglée. Un lecteur pouvait objecter que le modèle battait une ligne de base trop faible.

**Résultat sur KKBox, mesure du 14 septembre.**

- **La logistique réglée fait moins bien que la logistique simple en tête de liste** : Precision@50 de 0,126 contre 0,149, inférieure sur les quatre plis. Son ROC-AUC est un peu meilleur, 0,739 contre 0,721 : elle ordonne mieux la liste entière et moins bien ses 50 premiers. La force retenue varie de 0,1 à 10 selon le pli, signe que la validation interne départage mal ces réglages.
- **Le gain du modèle se mesure donc contre la plus forte des logistiques**, la simple : +0,176 à variables financières égales, positif sur les quatre plis, avec un écart type de 0,005.
- **La grille élargie ne change pas le résultat au-delà du bruit** : Precision@50 de 0,323 pour XGBoost contre 0,333 au lot 5, soit −0,010 en moyenne par pli pour un écart type de 0,014. La sélection par pli retient plus souvent la profondeur 3 ou 100 arbres. Le modèle final, entraîné sur toute la grille, garde profondeur 4, 300 arbres et taux 0,05 : même version, même export.

**Ce qui est retenu.** La grille élargie reste en configuration, puisqu'elle était décidée avant la mesure. Revenir à la grille réduite parce qu'elle donne un meilleur chiffre en test reviendrait à choisir un réglage en regardant le test. Les chiffres de référence du projet deviennent ceux de cette mesure.

---

## D24. Une résiliation compte à la date où elle est constatée

**Statut** : Actée le 2026-09-14 par le propriétaire du projet, après mesure. Précise D4, rectifie D17, et remplace les chiffres de référence de D23.

**Le défaut.** Sur KKBox, `date_resiliation` porte l'expiration de l'abonnement non renouvelé. Le départ n'est pourtant acquis que 30 jours plus tard, une fois écoulé le délai laissé pour renouveler. Deux règles lisaient la date brute :

- l'éligibilité écartait un compte dès son expiration, alors que personne ne pouvait savoir, pendant ces 30 jours, s'il renouvellerait ;
- la règle d'issue connue, la purge et l'embargo supposaient la cible connue à `T0 + 30 jours`, alors qu'elle ne l'est qu'à `T0 + 60 jours`.

Aucun test ne pouvait le voir : la sentinelle tronque le journal, et le test du référentiel ne réécrit que les colonnes dont la grille n'a pas besoin. Le défaut a été trouvé en relisant le code pour écrire la définition exacte de la cible dans le README.

**Exposition mesurée avant correction**, sur la grille de la mesure D23 :

- 10 095 couples écartés pendant le délai, soit 2,46 % de la grille, pour 2 494 comptes. Réintégrés et scorés par le modèle final, ils occupaient en moyenne de 2,6 à 4,9 des 50 places selon le pli, jusqu'à 18, sur 78 des 80 semaines de test ;
- de 93 à 216 positifs d'apprentissage par pli n'étaient constatés qu'après le début du test.

**La correction.** Chaque source déclare un délai de constat, `confirmation_delay_days` : 30 jours sur KKBox, 0 sur le jeu synthétique, où une résiliation est connue le jour même.

- Un compte reste éligible tant que `date_resiliation` augmentée du délai n'est pas passée. Pendant le délai, il porte la cible 0, puisque sa résiliation est datée avant `T0`.
- Un couple n'est gardé que si `T0 + horizon + délai` tient dans l'historique.
- La purge compte à partir de `T0 + horizon + délai`, et la configuration refuse un embargo inférieur à l'horizon augmenté du délai. L'embargo KKBox passe à 60 jours.

Un test échoue si l'éligibilité, la règle d'issue connue, la purge ou la vérification de la configuration revient à la date brute.

**Résultat sur KKBox, mesure du 14 septembre après correction.** Grille de 400 059 couples et 8 881 positifs, 76 semaines de test.

- XGBoost atteint une Precision@50 de 0,274, contre 0,323 avant correction, soit environ 14 départs sur 50 appels. Régression logistique 0,135, tri par revenu 0,089, hasard 0,019.
- **Au pli 0, la sélection des réglages n'a pas pu se faire.** Avec 60 jours d'embargo, la validation interne des 39 617 lignes de ce pli ne laisse aucune ligne d'entraînement, et chaque modèle réglé garde le premier réglage de sa grille, comme le prévoit D23. XGBoost y tombe à 0,165. Sur les plis 1 à 3, il vaut 0,310 en moyenne, contre 0,330 avant correction sur des périodes voisines : c'est l'ordre de grandeur de l'exposition estimée.
- Le gain du modèle sur la régression logistique, à variables financières égales, vaut +0,133, positif sur les quatre plis, avec un écart type de 0,070. Il n'est que de +0,033 au pli 0.
- Le gain du journal d'écoute reste non établi : +0,008, positif sur deux plis sur quatre.
- Le modèle final, entraîné sur toute la grille, retient profondeur 6, 100 arbres et taux 0,05 : version `0.1.0-1799d44265f1`.

**Ce qui est retenu.** Les chiffres de cette mesure deviennent la référence du projet, pli 0 compris. Changer le repli de la sélection, le nombre de plis ou la date de départ après avoir vu ce résultat reviendrait à choisir le protocole en regardant le test.

**Limite qui demeure.** L'adaptateur KKBox retire du journal les événements postérieurs à `date_resiliation`. Un compte dans son délai de constat perd donc ses écoutes des jours qui suivent son expiration, selon un fait que personne ne connaissait encore à `T0`. L'effet n'est pas mesuré.

---

## D25. Le cours a sa propre application, qui lit les fichiers Markdown

**Statut** : Actée le 2026-09-14 par le propriétaire du projet.

Le cours pour débutant est publié dans une seconde application Streamlit, `app/cours_app.py`, distincte de la démonstration du produit. Trois formes ont été comparées : un écran de plus dans l'application existante, qui mêlait la démonstration et le cours ; un site statique MkDocs sur GitHub Pages, plus confortable à lire, mais qui demandait une dépendance, un workflow de publication et des quiz restés statiques ; une application dédiée, retenue.

**Une seule source.** L'application lit `docs/cours` tel quel, par `churn.interface.course`. Chaque lot continue de n'écrire que le Markdown. Les formes lues, plan, correction, schémas, quiz et glossaire, sont vérifiées par `tests/test_course.py` sur les vrais fichiers : un changement de format fait échouer un test, pas une page.

**Ce qu'elle ajoute.** Un menu avec la progression, les corrections dépliables, des quiz corrigés avec l'explication de chaque réponse, un glossaire filtrable, et un lien direct vers une leçon par `?lecon=`.

**Schémas.** Les schémas Mermaid du cours sont traduits en Graphviz, que Streamlit dessine sans charger de script extérieur. Seuls les organigrammes simples utilisés par le cours sont compris, et toute autre construction lève une erreur.

**Limites.** La progression vit dans la session du navigateur et se perd à la fermeture de la page. Une application gratuite de Streamlit Community Cloud s'endort faute de visites, et met quelques instants à se réveiller. Aucune dépendance n'est ajoutée.

---

## Points ouverts

| Réf | Question | Qui tranche | Bloque |
| :--- | :--- | :--- | :--- |
| O1 | Définition métier exacte du churn : résiliation contractuelle ferme, ou seuil d'inactivité ? | Métier | Le générateur et la construction de la cible |
| O2 | Capacité hebdomadaire réelle de l'équipe commerciale, qui fixe K | Métier | Le calibrage de la métrique, pas le code |
| O3 | Horizon de 60 jours : confirmé par le délai réel d'intervention commerciale ? | Métier | Le paramètre d'embargo et la construction de la cible |
| O4 | Accès Kaggle : compte, acceptation des règles et jeton d'API | Utilisateur | Le lot 2 de la roadmap |
| O5 | Données publiables par l'interface en ligne, au regard des règles de la compétition KKBox | Utilisateur | Tranché le 2026-09-14 : décision D22 |

Les trois premiers points ne bloquent pas le démarrage : les lots 0 et 1 se construisent avec les valeurs par défaut du fichier de configuration, et un changement de valeur ne demande aucune réécriture. Le quatrième, O4, bloque le lot 2 et doit être levé avant la fin du lot 1.
