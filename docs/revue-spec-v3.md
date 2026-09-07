# Revue critique de la spec issue de la table ronde du 28 août 2026

Document de référence : `refs/table-ronde-cadrage-2026-08-28.md`, section « SPECS TECHNIQUES, ARCHITECTURE ET CODE BASE » du tour 3.

Cette revue ne rejette pas le travail de la table ronde. Elle en conserve les décisions solides, écarte celles qui ne résistent pas à l'examen, et documente sept défauts techniques qui auraient produit un modèle faux ou un projet bloqué.

## 1. Ce qui est juste et qui est conservé

| Décision de la table ronde | Verdict | Motif |
| :--- | :--- | :--- |
| Rejet du Rappel pur au profit d'une métrique de tête de liste | Conservé | L'argument de saturation des commerciaux et de coût de rétention est exact. |
| Explicabilité locale par client plutôt que globale | Conservé | Une importance globale ne donne aucun levier d'action lors d'un appel. |
| TreeSHAP calculé en batch, jamais à la volée | Conservé | Sur un horizon de 60 jours, le temps réel n'apporte rien et coûte de la latence. |
| Mapping statique de la variable technique vers un libellé métier | Conservé | Déterministe, testable, sans dépendance à un modèle de langage. |
| Purge des comptes de moins de 60 jours d'ancienneté | Conservé | Un compte trop jeune n'a pas d'historique exploitable. |
| Tri déterministe pour départager les ex aequo | Conservé | Sans lui, deux exécutions successives donnent deux listes différentes. |

## 2. Le bloquant que la table ronde n'a jamais levé

Au tour 1, le Développeur pose la question suivante : « A-t-on déjà le pipeline d'extraction des données historiques prêt, ou faut-il tout construire depuis les logs bruts ? »

Cette question n'a reçu aucune réponse pendant les trois tours. Elle est pourtant la condition d'existence du projet. La réponse réelle, confirmée le 7 septembre 2026, est qu'aucune donnée n'est disponible à ce jour.

Conséquence directe : le sprint 1 tel qu'il est écrit, « scripts SQL et loader.py de chargement des snapshots T-60j », ne peut pas démarrer. La réponse retenue figure dans `docs/decisions.md`, décision D1.

## 3. Sept défauts techniques à corriger

### 3.1 Le TimeSeriesSplit sans embargo laisse fuir la cible

C'est le défaut le plus grave, et il produit un modèle qui paraît excellent en validation puis s'effondre en production.

La cible d'une observation datée `T0` se résout à `T0 + 60 jours`. Un `TimeSeriesSplit` classique coupe le jeu en un point unique : les dernières observations d'entraînement ont donc une cible qui se réalise à l'intérieur de la période de test. Le modèle apprend sur des issues qui appartiennent à la fenêtre qu'il est censé prédire.

Correction obligatoire : intercaler une période d'embargo d'au moins 60 jours entre la fin de l'entraînement et le début du test, et purger toute observation d'entraînement dont la fenêtre de cible empiète sur le test. La classe `TimeSeriesSplit` de scikit-learn accepte un paramètre `gap` qui répond exactement à ce besoin. Il n'apparaît nulle part dans la spec V3.

### 3.2 La Precision@K est mal définie

La spec fixe `precision_k_target_k: 50` et parle d'un tri par `np.argsort`. Prendre les 50 meilleurs scores de l'ensemble de la période de test n'a aucun sens métier, puisque la capacité de 50 clients est une capacité hebdomadaire.

Définition correcte : découper la période d'évaluation en semaines de scoring, prendre les K premiers de chaque semaine, calculer la précision de chaque semaine, puis moyenner. La valeur obtenue est directement interprétable, car c'est le taux de réussite qu'un commercial constatera dans sa liste du lundi.

### 3.3 Aucune ligne de base de comparaison

La spec passe directement à XGBoost. Sans point de comparaison, la Precision@K obtenue est ininterprétable.

Trois lignes de base sont exigées avant tout modèle : le hasard, le tri par MRR décroissant (ce que fait un commercial sans outil), et une régression logistique régularisée sur les variables brutes. Si le modèle à arbres ne bat pas nettement les trois, le projet ne justifie pas son coût.

### 3.4 SHAP sur variables encodées produit un affichage absurde

Un modèle entraîné sur des variables encodées en indicatrices donne des contributions par colonne encodée. Le top 3 brut peut donc afficher trois fois la même variable métier sous trois modalités différentes.

Correction : agréger les contributions SHAP par variable d'origine avant l'extraction du top 3, en sommant les contributions des colonnes issues d'une même source. Point non traité par la spec V3.

### 3.5 Le seuil epsilon de 0,01 est arbitraire

La spec fixe `shap_epsilon: 0.01` sans unité ni justification. Les valeurs SHAP d'un classifieur à arbres s'expriment en log-odds, dont l'échelle dépend du modèle et de la prévalence du churn. Vérification faite localement, la valeur de base d'un modèle sur une classe positive à 10 % vaut environ -2,39 en log-odds.

Correction : ne pas figer ce seuil avant mesure. Le définir comme un quantile de la distribution des contributions absolues observées, calculé à l'entraînement et sérialisé avec le modèle.

### 3.6 Le score affiché doit être calibré, ou ne pas être présenté comme une probabilité

La spec pousse un `Score_Churn__c` arrondi à deux décimales. Un score de sortie d'un modèle à arbres n'est pas une probabilité calibrée. Afficher « 0,87 » à un commercial qui le lira comme « 87 % de chances de partir » est une erreur de restitution.

Deux options, à trancher : calibrer explicitement le modèle sur un jeu de calibration temporellement distinct, ou n'afficher qu'un rang et un décile de risque. Recommandation retenue en décision D6.

### 3.7 Versions de dépendances périmées de deux ans

La spec fige `pandas==2.2.0`, `scikit-learn==1.4.0`, `shap==0.44.1`, `xgboost==2.0.3` et `pydantic==2.6.0`. Ces versions datent du début 2024.

État réel vérifié sur PyPI le 7 septembre 2026 : `pandas 3.0.5`, `numpy 2.5.3`, `scikit-learn 1.9.0`, `xgboost 3.4.1`, `shap 0.52.0`, `pydantic 2.13.5`. L'installation et un test fonctionnel de la chaîne XGBoost plus TreeSHAP ont été validés sous Python 3.14.4 sur ce poste.

Un point de vigilance subsiste. La version `seaborn 0.13.2` déclenche une dépréciation de matplotlib 3.11 sur le paramètre `vert`, qui deviendra une erreur en matplotlib 3.13. La contrainte correspondante est posée dans `pyproject.toml`.

## 4. Ce qui est retiré du périmètre

La restitution retenue est un export exploitable, et non une synchronisation CRM. Les composants suivants sortent donc du périmètre de la version 1 :

- `crm_sync.py`, l'API Bulk Salesforce et la dépendance `simple-salesforce`
- le circuit breaker et sa politique de seuil à 5 %
- la dead letter queue et sa table PostgreSQL
- la table `active_churn_alerts` et l'algorithme de delta sync Set A et Set B
- la récupération de secrets par KMS ou Vault
- PostgreSQL comme dépendance de la version 1

Ces éléments représentent l'essentiel du sprint 3 de la spec V3, soit environ 60 % de sa complexité, pour une valeur nulle tant qu'aucun CRM n'est raccordé. Ils redeviennent pertinents le jour où la synchronisation revient au programme, et la frontière de sortie du pipeline est conçue pour les accueillir sans réécriture.

## 5. Défaut de méthode dans la table ronde elle-même

Deux observations, utiles pour les prochaines sessions de cadrage.

Le président avait pour consigne explicite de ne jamais trancher seul un désaccord de fond et de le remonter à l'humain. Sa synthèse déclare qu'il n'y a « plus de désaccord de fond », alors que la question des données posée par le Développeur était restée sans réponse. Un point ouvert a été converti en point clos.

L'annexe des prompts figés montre que les six agents portaient tous la mention « Projet en cours : DASHBOARD RH INTERACTIF », et non le projet de churn. Cela explique certaines contributions hors sujet, notamment le développement du Designer sur l'accessibilité des zones de dépôt de fichiers, qui n'a aucun objet dans un pipeline batch.
