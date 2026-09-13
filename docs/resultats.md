# Résultats mesurés

Ce document consigne les mesures qui engagent le projet. Les rapports détaillés sont régénérés sous `reports/`, qui n'est pas versionné ; les chiffres retenus sont recopiés ici, datés, avec leur source et leurs limites.

Règle de lecture, décision D2 : un chiffre obtenu sur données simulées ne vaut jamais prévision. Seules les mesures portant la source KKBox ont une valeur.

**Mesure de référence actuelle : lot 5.** La mesure du lot 4 est conservée pour l'historique, mais elle précède la décision D18 et le journal d'écoute complet. Ses chiffres ne sont plus comparables.

---

## Lot 5. Modèle XGBoost face aux lignes de base, et explication des scores

**Source : KKBox WSDM Churn Prediction Challenge.** Mesure du 13 septembre 2026.

### Conditions

| Paramètre | Valeur |
| :--- | :--- |
| Échantillon | Les mêmes 8 150 comptes qu'au lot 4, dont 2 903 résiliés |
| Journal | 4 329 107 événements, dont le journal d'écoute complet : 7 881 comptes, 1 391 093 jours d'écoute du 1er janvier 2015 au 31 mars 2017 |
| Grille | 410 523 couples `(client_id, T0)` hebdomadaires, 9 159 positifs, 100 dates du 6 avril 2015 au 27 février 2017 |
| Revenu | Lu dans le journal à `T0`, décision D18. 27,3 % des couples n'ont encore aucun revenu connu et portent zéro |
| Horizon et embargo | 30 jours et 30 jours |
| Découpage | 4 plis chronologiques, fenêtre d'entraînement croissante, embargo et purge, identiques au lot 4 |
| K | 50 par semaine de scoring, capacité hypothétique, décision D5 |
| Variables | 86 : familles FINANCE et PRODUCT sur fenêtres de 7, 30 et 90 jours avec leurs tendances, plus l'ancienneté et le revenu en vigueur |
| Réglages XGBoost | 8 combinaisons, choisies dans chaque pli sur un découpage interne des seules lignes d'entraînement |

### Synthèse, moyenne sur les quatre plis

| Classement | Precision@50 | Écart type entre plis | Rappel au rang 50 | ROC-AUC | Lift contre le revenu |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Hasard | 0,0205 | 0,0057 | 0,0123 | 0,502 | 0,21 |
| Tri par revenu en vigueur | 0,0980 | 0,0198 | 0,0612 | 0,687 | 1,00 |
| Régression logistique, finance seule | 0,1445 | 0,0285 | 0,0894 | 0,718 | 1,47 |
| Régression logistique, toutes variables | 0,1490 | 0,0226 | 0,0924 | 0,721 | 1,52 |
| XGBoost, finance seule | 0,3138 | 0,0248 | 0,1932 | 0,832 | 3,20 |
| **XGBoost, toutes variables** | **0,3328** | 0,0215 | 0,2057 | 0,834 | **3,40** |

« Finance seule » désigne la famille FINANCE plus l'ancienneté et le revenu, c'est-à-dire tout ce que les lignes de base du lot 4 pouvaient réellement exploiter.

### Détail par pli

| Pli | Période de test | Entraînement | Taux positif | Hasard | Revenu | Logistique finance | Logistique | XGBoost finance | XGBoost |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 2015-08-24 au 2016-01-04 | 50 664 lignes, 2 317 positifs | 2,53 % | 0,029 | 0,103 | 0,159 | 0,159 | 0,338 | 0,313 |
| 1 | 2016-01-11 au 2016-05-23 | 120 909 lignes, 3 858 positifs | 1,76 % | 0,019 | 0,127 | 0,184 | 0,181 | 0,339 | 0,369 |
| 2 | 2016-05-30 au 2016-10-10 | 201 056 lignes, 5 519 positifs | 1,54 % | 0,013 | 0,089 | 0,115 | 0,132 | 0,289 | 0,322 |
| 3 | 2016-10-17 au 2017-02-27 | 291 116 lignes, 6 880 positifs | 1,93 % | 0,021 | 0,073 | 0,120 | 0,124 | 0,289 | 0,327 |

### Lecture

**Le modèle bat les trois lignes de base, nettement et sur chaque pli.** Sur une liste de 50 comptes par semaine, XGBoost en désigne environ 17 qui partiront dans les 30 jours. La régression logistique en désigne environ 7, le tri par revenu 5, le hasard 1. Le hasard retombe sur le taux de base, 0,0205 pour 0,0194, ce qui contrôle la métrique.

**Le gain du modèle est établi.** À variables égales, sur la seule famille financière, XGBoost gagne 0,169 de Precision@50 sur la régression logistique. L'écart par pli vaut 0,179, 0,155, 0,174 et 0,169 : positif sur les quatre plis, avec un écart type de 0,009, très inférieur au gain.

**Le gain des données n'est pas établi.** À modèle égal, ajouter la famille d'écoute fait passer XGBoost de 0,3138 à 0,3328. L'écart par pli vaut -0,025, +0,030, +0,033 et +0,038 : moyenne de +0,019, écart type de 0,026, positif sur trois plis sur quatre. Avec quatre plis, ce gain reste du même ordre que la variabilité entre plis. Pour la régression logistique, il est nul : +0,0045, positif sur deux plis sur quatre.

**L'hypothèse du taux de complétion n'est pas confirmée.** Parmi les variables d'écoute, c'est la fréquence d'usage qui pèse le plus dans les contributions du modèle final, loin devant le taux de complétion. Sur la dernière période, la contribution positive moyenne vaut 0,120 pour la fréquence d'usage et 0,043 pour le taux de complétion. Une explication plausible, non vérifiée, rapproche ce constat de la faiblesse du gain des données : un abonné qui s'apprête à ne pas renouveler cesse aussi d'écouter, si bien que l'écoute répète en partie ce que disent déjà les transactions.

**La sélection des réglages retombe presque toujours sur le coin le plus prudent de la grille** : profondeur 4, 300 arbres, taux d'apprentissage 0,05. C'est le cas dans les quatre plis pour XGBoost toutes variables, et dans deux plis sur quatre pour la variante finance, qui retient 300 arbres à 0,1 au pli 0 et 600 arbres à 0,05 au pli 1. Des modèles encore plus simples n'ont pas été essayés.

### Modèle final et explication des scores

Le modèle final est entraîné sur toute la grille avec le même mécanisme de sélection. Version `0.1.0-b8f55da1e566`, profondeur 4, 300 arbres, taux 0,05. Seuil de signification calculé à l'entraînement : 0,1627, soit le 75e centile des contributions agrégées en valeur absolue.

Sur les 5 074 comptes de la dernière date, le 27 février 2017, voici combien de facteurs de risque dépassent ce seuil :

| Facteurs significatifs | Part des comptes |
| :--- | ---: |
| Aucun | 26,3 % |
| Un | 47,9 % |
| Deux | 17,9 % |
| Trois | 7,9 % |

Aucun des 50 comptes les mieux classés n'est sans motif. Parmi les 50 comptes les moins bien classés, 36 % n'en ont pas. Le premier motif le plus fréquent est « [PRODUCT] Fréquence d'usage », pour 1 803 comptes, devant « [FINANCE] Facturation », pour 1 048. En tête de liste, les motifs financiers dominent.

Exemples de lignes en tête de la dernière période :

| Rang | Facteur 1 | Facteur 2 | Facteur 3 |
| ---: | :--- | :--- | :--- |
| 1 | [GENERAL] Revenu mensuel en vigueur | [FINANCE] Statut du renouvellement automatique | [FINANCE] Évolution récente du renouvellement automatique |
| 2 | [FINANCE] Évolution récente de la facturation | [FINANCE] Statut du renouvellement automatique | [FINANCE] Facturation |
| 4 | [FINANCE] Annulations d'abonnement | [FINANCE] Évolution récente de la facturation | [GENERAL] Ancienneté du compte |

**Cette liste est en échantillon.** Le modèle final a été entraîné sur ces lignes, cible comprise. Elle illustre la forme de l'explication ; le nombre de départs qu'elle contient ne mesure rien. La mesure de performance est le tableau par pli ci-dessus.

### Limites assumées

- K = 50 est une capacité hypothétique.
- Le gain apporté par le journal d'écoute n'est pas établi avec quatre plis.
- La grille de réglages est réduite, décision D16, et la sélection se loge dans son coin le plus prudent.
- La régression logistique n'est pas réglée : régularisation par défaut, aucune transformation des comptages très asymétriques. Une ligne de base linéaire mieux préparée ferait probablement mieux que 0,149.
- Les libellés nomment un signal sans en donner le sens, et les facteurs structurels, revenu et ancienneté, n'offrent aucun levier d'action. Leur place dans l'export se décide au lot 6.
- Un revenu nul signifie « inconnu » pour 27,3 % des couples, l'extrait ne remontant pas avant 2015.
- Les scores ne sont pas des probabilités, décision D6.
- L'échantillon de 8 150 comptes reste modeste au regard des 2,36 millions disponibles.

### Reproduire

```bash
uv run python scripts/download_kkbox.py --skip-download --with-logs --sample-size 10000
uv run python scripts/train_model.py --source kkbox
```

Aucun accès réseau. Environ 18 minutes pour reconstruire l'échantillon avec le journal d'écoute, puis 10 minutes pour la comparaison et le modèle final. Graine fixée dans `config/config.yaml`.

---

## Lot 4. Lignes de base, mesurées avant tout modèle à arbres

**Statut : remplacée par la mesure du lot 5.** Cette mesure précède la décision D18, qui corrige la lecture du revenu, et l'extraction du journal d'écoute complet, qui modifie la grille. Elle est conservée pour l'historique.

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

**La régression logistique bat le tri par revenu sur chacun des quatre plis**, pas seulement en moyenne.

**Cette mesure fixait la barre du lot 5 à 0,1628.** Elle est caduque : le lot 5 remesure les lignes de base sur la grille corrigée.

### Limites assumées

- K = 50 est une capacité hypothétique, KKBox n'ayant pas d'équipe commerciale.
- **Les lignes de base n'exploitaient aucune donnée d'usage.** Les 36 variables d'écoute étaient constantes sur toute la grille : le journal récent couvre du 1er au 31 mars 2017, et la dernière date d'observation est le 27 février 2017. *Rectification du 13 septembre : une première version de ce document présentait le taux de complétion comme le signal le plus prometteur du jeu, sans mesure pour l'appuyer. Le lot 5 ne le confirme pas.*
- **Le revenu utilisé ici venait de la dernière transaction du compte**, différente du revenu en vigueur à la date d'observation sur 22,5 % des couples et sur 32,6 % des couples positifs. Le sens de l'effet sur les lignes de base dépend de la mesure, voir D18. Le défaut est corrigé par cette décision.
- Certaines semaines, autour de mars et d'août 2016, affichaient une précision nulle pour les trois classements à la fois. Ce comportement n'a pas été réexaminé au lot 5.
- L'échantillon de 8 150 comptes est modeste au regard des 2,36 millions disponibles.

### Mesure invalide écartée

Une première exécution, le même jour, donnait la même Precision@50 de 0,0068 pour le revenu et la logistique. Elle était fausse : la grille démarrait aux inscriptions de 2004 alors que les transactions commencent en 2015, et les quatre plis d'entraînement ne contenaient aucun positif. La logistique produisait des scores constants départagés par le revenu. Le défaut est corrigé par la décision D17, et le protocole refuse désormais un pli d'entraînement à une seule classe.

---

## Rappel : mesure sur données simulées

> SIMULATED DATA. No performance figure holds here.

Sur le jeu synthétique, les chiffres servent uniquement à vérifier que la chaîne tourne. Le générateur a été écrit par l'auteur du modèle, et sa famille financière sépare presque parfaitement les deux classes : un score élevé y mesure la cohérence du générateur, pas un pouvoir prédictif.
