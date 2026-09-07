# Registre des décisions

Chaque décision est numérotée, datée et motivée. Une décision inscrite ici est close : l'agent développeur l'applique sans la rediscuter. Pour en changer, il faut modifier ce fichier, pas le code.

Statut possible : `Actée`, `Ouverte`, `Bloquée`, `Révisée`.

---

## D1. Le projet démarre sur données synthétiques, avec un contrat de données figé d'abord

**Statut** : Actée le 2026-09-07.

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

Le découpage entraînement et test est strictement chronologique, avec un embargo d'au moins 60 jours entre les deux, égal à l'horizon de prédiction. Toute observation d'entraînement dont la fenêtre de cible franchit la frontière de test est purgée.

**Motif** : détaillé en section 3.1 de `revue-spec-v3.md`. Sans embargo, la cible d'entraînement se résout dans la période de test et la validation devient mensongère.

**Test de non-régression associé** : `tests/test_split.py` doit échouer si une observation d'entraînement possède une date de résolution de cible postérieure au début de la période de test.

---

## D5. Precision@K définie par période de scoring

**Statut** : Actée le 2026-09-07.

`Precision@K` se calcule par semaine de scoring, puis se moyenne sur les semaines de la période d'évaluation. K représente la capacité de traitement hebdomadaire de l'équipe commerciale et vaut 50 par défaut, valeur à confirmer avec le métier.

**Motif** : détaillé en section 3.2 de `revue-spec-v3.md`.

**Métriques secondaires obligatoires** : le rappel au rang K sur la même base, pour mesurer la part de churn effectivement capturée, et le lift par rapport au tri par MRR décroissant. Le ROC-AUC est calculé pour information mais ne pilote aucune décision, car il est peu sensible sur une classe rare.

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

---

## D9. Stack et versions

**Statut** : Actée le 2026-09-07.

Python 3.12 minimum, développement et validation sous 3.14.4. Gestion d'environnement et de verrouillage par `uv`. Bibliothèques : pandas, numpy, scikit-learn, xgboost, shap, pydantic, pyarrow, pyyaml, seaborn, matplotlib, pytest.

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

## Points ouverts

| Réf | Question | Qui tranche | Bloque |
| :--- | :--- | :--- | :--- |
| O1 | Définition métier exacte du churn : résiliation contractuelle ferme, ou seuil d'inactivité ? | Métier | Le générateur et la construction de la cible |
| O2 | Capacité hebdomadaire réelle de l'équipe commerciale, qui fixe K | Métier | Le calibrage de la métrique, pas le code |
| O3 | Horizon de 60 jours : confirmé par le délai réel d'intervention commerciale ? | Métier | Le paramètre d'embargo et la construction de la cible |
| O4 | Date d'arrivée des données réelles et forme sous laquelle elles arriveront | Utilisateur | Le lot 5 de la roadmap |

Ces quatre points ne bloquent pas le démarrage : les lots 1 à 4 se construisent avec les valeurs par défaut du fichier de configuration, et un changement de valeur ne demande aucune réécriture.
