# Résultats mesurés

Ce document consigne les mesures qui engagent le projet. Les rapports détaillés sont régénérés sous `reports/`, qui n'est pas versionné ; les chiffres retenus sont recopiés ici, datés, avec leur source et leurs limites.

Règle de lecture, décision D2 : un chiffre obtenu sur données simulées ne vaut jamais prévision. Seules les mesures portant la source KKBox ont une valeur.

---

## Lot 4. Lignes de base, mesurées avant tout modèle à arbres

**Source : KKBox WSDM Churn Prediction Challenge.** Mesure du 13 septembre 2026.

### Conditions

| Paramètre | Valeur |
| :--- | :--- |
| Échantillon | 10 000 comptes tirés dans les transactions, 8 150 projetés sur le contrat |
| Grille | 373 803 couples `(client_id, T0)` hebdomadaires, 8 556 positifs, soit 2,29 % |
| Horizon et embargo | 30 jours et 30 jours, définition officielle du churn KKBox |
| Découpage | 4 plis chronologiques, fenêtre d'entraînement croissante, embargo et purge |
| K | 50 par semaine de scoring. Capacité hypothétique : KKBox n'a pas d'équipe commerciale, décision D5 |
| Variables | 86 au total : 48 financières informatives, 2 structurelles, et 36 d'écoute toutes constantes, le journal récent ne couvrant que mars 2017, après la dernière date d'observation |

### Synthèse, moyenne sur les quatre plis

| Classement | Precision@50 | Écart type entre plis | Rappel au rang 50 | ROC-AUC | Lift contre le revenu |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Hasard | 0,0175 | 0,0079 | 0,0111 | 0,502 | 0,37 |
| Tri par revenu décroissant | 0,0475 | 0,0096 | 0,0326 | 0,663 | 1,00 |
| Régression logistique | **0,1628** | 0,0140 | 0,1099 | 0,765 | **3,43** |

### Détail par pli

| Pli | Période de test | Entraînement | Taux positif en test | Hasard | Revenu | Logistique |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: |
| 0 | 2015-08-24 au 2016-01-04 | 41 245 lignes, 2 300 positifs | 2,78 % | 0,028 | 0,035 | 0,163 |
| 1 | 2016-01-11 au 2016-05-23 | 104 252 lignes, 3 827 positifs | 1,92 % | 0,012 | 0,043 | 0,184 |
| 2 | 2016-05-30 au 2016-10-10 | 177 342 lignes, 5 480 positifs | 1,42 % | 0,008 | 0,051 | 0,145 |
| 3 | 2016-10-17 au 2017-02-27 | 258 261 lignes, 6 696 positifs | 1,64 % | 0,022 | 0,061 | 0,159 |

### Lecture

**Le hasard retombe sur le taux de base**, 0,0175 pour 0,0194 en test. C'est le contrôle de cohérence de la métrique : une Precision@K qui s'en écarterait signalerait un défaut de calcul, pas un signal.

**La régression logistique bat le tri par revenu sur chacun des quatre plis**, pas seulement en moyenne. Sur une liste de 50 comptes par semaine, elle en désigne environ 8 qui partiront dans les 30 jours, contre 2 à 3 pour un commercial qui appellerait les plus gros comptes en premier.

**La barre du lot 5 est fixée ici.** Le modèle à arbres doit dépasser nettement 0,1628. L'écart type entre plis, 0,014, donne l'ordre de grandeur de ce qui relève du bruit : un gain inférieur ne justifierait pas le coût du modèle.

### Limites assumées

- K = 50 est une capacité hypothétique, KKBox n'ayant pas d'équipe commerciale.
- **Les lignes de base n'exploitent aucune donnée d'usage.** Les 36 variables d'écoute sont constantes sur toute la grille : le journal récent couvre du 1er au 31 mars 2017, et la dernière date d'observation est le 27 février 2017. Le journal complet, 30,5 Go décompressés et déjà téléchargé, n'est pas encore extrait ; il porte le taux de complétion. Le 0,1628 repose donc sur les seules variables financières. *Rectification du 13 septembre : une première version de cette phrase présentait le taux de complétion comme le signal le plus prometteur du jeu, sans mesure pour l'appuyer. C'est une hypothèse, que le lot 5 tranche.*
- **Le revenu utilisé ici venait de la dernière transaction du compte**, postérieure à la date d'observation sur 19 % des couples. Le défaut est corrigé par la décision D18 et les trois lignes de base sont remesurées au lot 5 sur la grille corrigée. La valeur datée classant mieux que la valeur figée, cette fuite ne flattait pas le tri par revenu.
- Certaines semaines, autour de mars et d'août 2016, affichent une précision nulle pour les trois classements à la fois. Ce comportement n'est pas expliqué à ce jour.
- L'échantillon de 8 150 comptes est modeste au regard des 2,36 millions disponibles.

### Mesure invalide écartée

Une première exécution, le même jour, donnait la même Precision@50 de 0,0068 pour le revenu et la logistique. Elle était fausse : la grille démarrait aux inscriptions de 2004 alors que les transactions commencent en 2015, et les quatre plis d'entraînement ne contenaient aucun positif. La logistique produisait des scores constants départagés par le revenu. Le défaut est corrigé par la décision D17, et le protocole refuse désormais un pli d'entraînement à une seule classe.

### Reproduire

```bash
uv run python scripts/download_kkbox.py --skip-download --sample-size 10000
uv run python scripts/evaluate_baselines.py --source kkbox
```

Aucun accès réseau. Graine fixée dans `config/config.yaml`.

---

## Rappel : mesure sur données simulées

> SIMULATED DATA. No performance figure holds here.

Sur le jeu synthétique de 1 500 comptes, la régression logistique atteint 0,1741 de Precision@50. Ce chiffre mesure la cohérence du générateur, dont la famille financière sépare presque parfaitement les deux classes, et non un pouvoir prédictif. Il sert uniquement à vérifier que la chaîne tourne.
