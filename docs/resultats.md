# Résultats mesurés

Ce document consigne les mesures qui engagent le projet. Les rapports détaillés sont régénérés sous `reports/`, qui n'est pas versionné ; les chiffres retenus sont recopiés ici, datés, avec leur source et leurs limites.

Règle de lecture, décision D2 : un chiffre obtenu sur données simulées ne vaut jamais prévision. Seules les mesures portant la source KKBox ont une valeur.

**Mesure de référence actuelle : la mesure corrigée du 14 septembre**, décision D24. Elle compte une résiliation KKBox à la date où elle est constatée, 30 jours après sa date, et remplace la mesure complémentaire du même jour, décision D23. Les mesures antérieures lisaient la date de résiliation brute : elles sont conservées pour l'historique et ne sont plus la référence.

---

## Mesure corrigée. Une résiliation compte à sa date de constat

**Source : KKBox WSDM Churn Prediction Challenge.** Mesure du 14 septembre 2026, décision D24.

### Conditions

Identiques à la mesure complémentaire, sauf trois règles qui attendent désormais la date de constat d'une résiliation : l'éligibilité, la règle d'issue connue et la purge. L'embargo passe de 30 à 60 jours.

| Paramètre | Valeur |
| :--- | :--- |
| Échantillon | Les mêmes 8 150 comptes |
| Grille | 400 059 couples hebdomadaires, 8 881 positifs |
| Dernière date d'observation | 30 janvier 2017, contre le 27 février avant correction |
| Horizon, délai de constat, embargo | 30, 30 et 60 jours |
| Découpage | 4 plis chronologiques, 76 semaines de test |
| K | 50 par semaine, capacité hypothétique, décision D5 |
| Variables | 86 |
| Réglages | Grille XGBoost de 24 combinaisons et régression logistique réglée, décision D23 |

### Synthèse, moyenne sur les quatre plis

| Classement | Precision@50 | Écart type entre plis | Rappel au rang 50 | ROC-AUC | Lift contre le revenu |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Hasard | 0,0189 | 0,0027 | 0,0115 | 0,500 | 0,21 |
| Tri par revenu en vigueur | 0,0889 | 0,0161 | 0,0560 | 0,683 | 1,00 |
| Régression logistique, finance seule | 0,1326 | 0,0253 | 0,0829 | 0,713 | 1,49 |
| Régression logistique, toutes variables | 0,1345 | 0,0185 | 0,0836 | 0,715 | 1,51 |
| Régression logistique réglée, finance seule | 0,1250 | 0,0265 | 0,0773 | 0,727 | 1,41 |
| Régression logistique réglée, toutes variables | 0,1182 | 0,0144 | 0,0737 | 0,736 | 1,33 |
| XGBoost, finance seule | 0,2655 | 0,0642 | 0,1685 | 0,817 | 2,99 |
| **XGBoost, toutes variables** | **0,2737** | 0,0672 | 0,1733 | 0,815 | **3,08** |

### Détail par pli

| Pli | Période de test | Entraînement | Taux positif | Hasard | Revenu | Logistique finance | Logistique | Logistique réglée | XGBoost finance | XGBoost |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 2015-08-24 au 2015-12-28 | 39 617 lignes, 2 073 positifs | 2,47 % | 0,019 | 0,085 | 0,137 | 0,144 | 0,129 | 0,169 | 0,165 |
| 1 | 2016-01-04 au 2016-05-09 | 106 047 lignes, 3 475 positifs | 1,77 % | 0,016 | 0,113 | 0,171 | 0,158 | 0,122 | 0,329 | 0,316 |
| 2 | 2016-05-16 au 2016-09-19 | 181 149 lignes, 5 102 positifs | 1,45 % | 0,018 | 0,091 | 0,122 | 0,127 | 0,127 | 0,318 | 0,341 |
| 3 | 2016-09-26 au 2017-01-30 | 265 474 lignes, 6 413 positifs | 2,01 % | 0,023 | 0,067 | 0,101 | 0,108 | 0,094 | 0,245 | 0,273 |

Réglages retenus par pli, sur la validation interne :

- logistique réglée, finance seule : C = 0,01 par repli ; 0,01 ; 1 ; 0,1 ;
- logistique réglée, toutes variables : C = 0,01 par repli ; 0,01 ; 10 ; 10 ;
- XGBoost, finance seule : profondeur et arbres de 2 et 100 par repli, 2 et 300, 4 et 300, 3 et 300 ;
- XGBoost, toutes variables : 2 et 100 par repli, 2 et 300, 6 et 100, 4 et 100.

### Lecture

**Le modèle bat toutes les lignes de base sur chaque pli, mais de peu au pli 0.** Sur 50 appels par semaine, XGBoost désigne environ 14 comptes qui partiront dans les 30 jours, contre 7 pour la régression logistique et 4 pour le tri par revenu. Il dépasse à la fois le hasard, le tri par revenu et les deux régressions logistiques toutes variables sur 64 des 76 semaines de test.

**Le pli 0 tourne sans sélection des réglages.** Avec 60 jours d'embargo, la validation interne de ses 39 617 lignes ne laisse aucune ligne d'entraînement. Chaque modèle réglé garde alors le premier réglage de sa grille, le plus simple, et le dit : c'est le repli prévu par D23. XGBoost y vaut 0,165. Sur les plis 1 à 3, il vaut 0,310 en moyenne.

**Ce que la correction a coûté.** Sur les plis 1 à 3, XGBoost passe de 0,330 à 0,310 sur des périodes de test décalées d'une semaine, l'ordre de grandeur de l'exposition estimée avant la mesure. Au pli 0, il passe de 0,300 à 0,165. L'essentiel de cet écart tient vraisemblablement au repli : la régression logistique, qui n'a rien à régler, n'y perd que 0,015.

**Le gain du modèle reste établi, avec plus de dispersion.** À variables financières égales, XGBoost gagne +0,033, +0,159, +0,196 et +0,144 sur la régression logistique : +0,133 en moyenne, positif sur les quatre plis, écart type de 0,070.

**La régression logistique réglée reste moins bonne en tête de liste** : 0,118 contre 0,135, pour un ROC-AUC meilleur, 0,736 contre 0,715.

**Le gain du journal d'écoute n'est pas établi** : +0,008 en moyenne, soit −0,004, −0,014, +0,023 et +0,027 par pli.

**Semaines à précision nulle.** XGBoost n'en a aucune : sa pire semaine vaut 0,02 et sa médiane 0,28. Le tri par revenu tombe à zéro deux semaines, la régression logistique toutes variables une, le hasard 33 sur 76.

### Modèle final et liste du lundi

Le modèle final, entraîné sur toute la grille, retient profondeur 6, 100 arbres et taux 0,05 : version `0.1.0-1799d44265f1`, seuil de signification 0,1538.

L'export du 27 mars 2017, produit avec ce modèle, score 5 165 comptes. C'est 72 de plus qu'au lot 6 : les données et la date sont les mêmes, et seule la règle d'éligibilité a changé, qui garde les comptes dont le départ n'est pas encore constaté. Chaque décile compte 516 ou 517 comptes, et 23,5 % des comptes ont un revenu inconnu.

| Motifs par compte | Part des 5 165 comptes | Parmi les 50 premiers |
| :--- | ---: | ---: |
| Aucun | 36,2 % | 0 |
| Un | 53,7 % | 0 |
| Deux | 5,9 % | 0 |
| Trois | 4,2 % | 50 |

Le premier motif le plus fréquent est « [FINANCE] Facturation », pour 1 383 comptes, devant « [PRODUCT] Fréquence d'usage », pour 1 247. Les trois premiers comptes de la liste :

| Rang | Motif 1 | Motif 2 | Motif 3 |
| ---: | :--- | :--- | :--- |
| 1 | [FINANCE] Évolution récente de la facturation | [FINANCE] Annulations d'abonnement | [FINANCE] Évolution récente des annulations d'abonnement |
| 2 | [FINANCE] Évolution récente de la facturation | [FINANCE] Annulations d'abonnement | [FINANCE] Évolution récente des annulations d'abonnement |
| 3 | [FINANCE] Évolution récente de la facturation | [FINANCE] Statut du renouvellement automatique | [FINANCE] Facturation |

### Reproduire

```bash
uv run python scripts/train_model.py --source kkbox
uv run python -m churn.pipeline.run_scoring --source kkbox
```

---

## Mesure complémentaire. Grille élargie et régression logistique réglée

**Statut : remplacée par la mesure corrigée, décision D24.** Sa grille lisait la date de résiliation brute.

**Source : KKBox WSDM Churn Prediction Challenge.** Mesure du 14 septembre 2026, décision D23.

### Conditions

Identiques au lot 5 : 8 150 comptes, grille de 410 523 couples et 9 159 positifs, 4 plis chronologiques avec embargo et purge, K = 50 hypothétique, 86 variables. Deux changements, décidés avant la mesure :

| Changement | Détail |
| :--- | :--- |
| Grille XGBoost | 24 combinaisons : profondeurs 2, 3, 4 et 6 ; 100, 300 ou 600 arbres ; taux 0,05 ou 0,1 |
| Régression logistique réglée | Logarithme signé des variables, standardisation, force de régularisation choisie parmi 0,01, 0,1, 1 et 10 sur la validation interne |

Durée : 22,5 minutes.

### Synthèse, moyenne sur les quatre plis

| Classement | Precision@50 | Écart type entre plis | Rappel au rang 50 | ROC-AUC | Lift contre le revenu |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Hasard | 0,0205 | 0,0057 | 0,0123 | 0,502 | 0,21 |
| Tri par revenu en vigueur | 0,0980 | 0,0198 | 0,0612 | 0,687 | 1,00 |
| Régression logistique, finance seule | 0,1445 | 0,0285 | 0,0894 | 0,718 | 1,47 |
| Régression logistique, toutes variables | 0,1490 | 0,0226 | 0,0924 | 0,721 | 1,52 |
| Régression logistique réglée, finance seule | 0,1318 | 0,0251 | 0,0809 | 0,731 | 1,34 |
| Régression logistique réglée, toutes variables | 0,1258 | 0,0200 | 0,0781 | 0,739 | 1,28 |
| XGBoost, finance seule | 0,3205 | 0,0251 | 0,1975 | 0,833 | 3,27 |
| **XGBoost, toutes variables** | **0,3228** | 0,0143 | 0,1991 | 0,837 | **3,29** |

### Détail par pli des nouveaux classements

| Pli | Logistique réglée, finance | Logistique réglée | XGBoost finance, grille élargie | XGBoost, grille élargie | XGBoost, grille du lot 5 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 0,169 | 0,145 | 0,338 | 0,300 | 0,313 |
| 1 | 0,140 | 0,138 | 0,352 | 0,338 | 0,369 |
| 2 | 0,113 | 0,127 | 0,293 | 0,322 | 0,322 |
| 3 | 0,105 | 0,093 | 0,299 | 0,331 | 0,327 |

Réglages retenus par pli, sur la validation interne :

- logistique réglée, finance seule : C = 1 ; 0,01 ; 0,1 ; 0,01 ;
- logistique réglée, toutes variables : C = 0,1 ; 10 ; 10 ; 0,1 ;
- XGBoost, finance seule : profondeur et arbres de 4 et 300, 3 et 300, 3 et 300, 4 et 100 ;
- XGBoost, toutes variables : 3 et 100, 3 et 100, 4 et 300, 4 et 100.

Le modèle final, entraîné sur toute la grille, retient profondeur 4, 300 arbres et taux 0,05 : version `0.1.0-b8f55da1e566`, identique au lot 5.

### Lecture

**Le modèle bat toutes les lignes de base, sur chaque pli et presque chaque semaine.** Sur 50 appels par semaine, XGBoost désigne environ 16 comptes qui partiront dans les 30 jours, contre 7 pour la meilleure régression logistique et 5 pour le tri par revenu. Il dépasse à la fois la régression logistique et le tri par revenu sur 75 des 80 semaines de test.

**La régression logistique réglée n'est pas une ligne de base plus forte en tête de liste.** Face à la logistique simple, l'écart par pli vaut −0,014, −0,043, −0,005 et −0,031 avec toutes les variables : négatif sur les quatre plis. Son ROC-AUC est pourtant meilleur, 0,739 contre 0,721 : elle ordonne mieux la liste entière, et moins bien les 50 premiers. Deux explications plausibles, non vérifiées : la compression logarithmique aplatit les valeurs extrêmes qui signalent justement les comptes les plus à risque, et la validation interne, sur une moitié de pli, mesure trop bruyamment la tête de liste pour départager les forces de régularisation.

**Le gain du modèle est établi contre la plus forte des logistiques.** À variables financières égales, XGBoost gagne +0,179, +0,168, +0,178 et +0,179 sur la logistique simple : +0,176 en moyenne, écart type de 0,005. Contre la logistique réglée, le gain est de +0,189.

**La grille élargie n'apporte rien de mesurable.** Face à la grille du lot 5, XGBoost varie de −0,013, −0,031, 0,000 et +0,004 par pli, et sa variante financière de +0,007 en moyenne. Ces écarts restent dans la variabilité entre plis.

**Le gain du journal d'écoute reste non établi** : +0,002 en moyenne, positif sur deux plis sur quatre.

**Semaines à précision nulle, décompte du 14 septembre sur `evaluation_precision_per_period.csv`.** Le lot 4 relevait des semaines de 2016 où les trois lignes de base tombaient à zéro ensemble. Sur cette mesure, aucune semaine ne voit le revenu, la régression logistique et XGBoost à zéro en même temps. XGBoost n'a aucune semaine nulle : sa pire semaine vaut 0,14 et sa médiane 0,32. Le tri par revenu tombe à zéro deux semaines, en août 2016, la régression logistique toutes variables une semaine, et le hasard 28 semaines sur 80. Ces semaines nulles des lignes de base ne sont pas expliquées. XGBoost dépasse à la fois le hasard, le tri par revenu et les deux régressions logistiques toutes variables sur 75 des 80 semaines.

### Reproduire

```bash
uv run python scripts/train_model.py --source kkbox
```

---

## Lot 6. Premier export de la liste du lundi

**Statut : produit avec le modèle `0.1.0-b8f55da1e566`, antérieur à la décision D24.** La liste actuelle est décrite dans la mesure corrigée.

**Source : KKBox WSDM Churn Prediction Challenge.** Export du 14 septembre 2026, portant sur la date de scoring du 27 mars 2017.

Ce n'est pas une mesure de performance : la réponse est inconnue le jour du scoring. Ce sont les chiffres de forme de la liste livrée.

| Élément | Valeur |
| :--- | :--- |
| Date de scoring | 27 mars 2017, dernière date d'observation permise par le journal |
| Modèle | `0.1.0-b8f55da1e566`, entraîné au lot 5 |
| Identifiant de lot | `d215541e-429a-51d0-9084-89293da7141d` |
| Comptes scorés | 5 093 |
| Déciles | 509 ou 510 comptes chacun |
| Revenu inconnu à la date | 23,9 % des comptes |
| Durée | 25 secondes |

### Motifs affichés, décision D19

| Motifs par compte | Part des 5 093 comptes | Parmi les 50 premiers |
| :--- | ---: | ---: |
| Aucun | 27,5 % | 0 |
| Un | 51,3 % | 0 |
| Deux | 15,5 % | 2 |
| Trois | 5,7 % | 48 |

Sans la règle des facteurs actionnables, avec le même modèle et le même seuil, 2,6 % des comptes auraient eu un facteur structurel en premier motif et 6,2 % au moins un. La règle fait passer la part de comptes sans motif de 26,2 % à 27,5 % : ce sont les comptes dont les seuls signaux significatifs étaient structurels.

Le premier motif le plus fréquent reste « [PRODUCT] Fréquence d'usage », pour 1 868 comptes, devant « [FINANCE] Facturation », pour 1 029.

### Critères d'acceptation vérifiés

- **Fichiers identiques** : deux exécutions successives sur KKBox donnent la même empreinte SHA-256 pour le Parquet, le CSV et le JSON.
- **Excel** : le CSV ouvert dans Excel sous Windows en français, comme par un double-clic, donne 12 colonnes et 5 094 lignes en-tête compris, des revenus et des scores reconnus comme nombres, et des accents corrects.

### Reproduire

```bash
uv run python -m churn.pipeline.run_scoring --source kkbox
```

Aucun accès réseau. Nécessite le jeu projeté et le modèle du lot 5.

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

**Le modèle bat les trois lignes de base, nettement, sur chaque pli et presque chaque semaine.** Semaine par semaine, XGBoost dépasse à la fois la régression logistique et le tri par revenu sur 78 des 80 semaines de test, décompte fait le 14 septembre sur `evaluation_precision_per_period.csv`. Sur une liste de 50 comptes par semaine, XGBoost en désigne environ 17 qui partiront dans les 30 jours. La régression logistique en désigne environ 7, le tri par revenu 5, le hasard 1. Le hasard retombe sur le taux de base, 0,0205 pour 0,0194, ce qui contrôle la métrique.

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
- Certaines semaines, autour de mars et d'août 2016, affichaient une précision nulle pour les trois classements à la fois. Ce comportement n'a pas été réexaminé au lot 5. Il l'a été le 14 septembre sur la mesure de référence, voir sa lecture en tête de document.
- L'échantillon de 8 150 comptes est modeste au regard des 2,36 millions disponibles.

### Mesure invalide écartée

Une première exécution, le même jour, donnait la même Precision@50 de 0,0068 pour le revenu et la logistique. Elle était fausse : la grille démarrait aux inscriptions de 2004 alors que les transactions commencent en 2015, et les quatre plis d'entraînement ne contenaient aucun positif. La logistique produisait des scores constants départagés par le revenu. Le défaut est corrigé par la décision D17, et le protocole refuse désormais un pli d'entraînement à une seule classe.

---

## Rappel : mesure sur données simulées

> SIMULATED DATA. No performance figure holds here.

Sur le jeu synthétique, les chiffres servent uniquement à vérifier que la chaîne tourne. Le générateur a été écrit par l'auteur du modèle, et sa famille financière sépare presque parfaitement les deux classes : un score élevé y mesure la cohérence du générateur, pas un pouvoir prédictif.
