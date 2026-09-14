# Chapitre 7. Évaluer honnêtement : le protocole et les lignes de base

> **Partie 3, mesurer et prédire** · Lecture : 35 minutes · Prérequis : partie 2

## Ce que vous allez apprendre

À la fin de ce chapitre, vous saurez :

- expliquer pourquoi l'exactitude ne convient pas à ce problème ;
- calculer une **Precision@K** par semaine, et la distinguer du rappel, du lift et du ROC-AUC ;
- expliquer comment séparer passé et futur avec un **embargo** et une **purge** ;
- justifier le rôle des **lignes de base**, et lire un tableau de résultats.

---

## 1. Évaluer, c'est simuler l'avenir avec le passé

On ne peut pas attendre un an pour savoir si le modèle fonctionne. On le juge donc sur le passé, en recréant les conditions réelles : le modèle apprend sur une période, puis on lui demande de classer les abonnés d'une période **suivante**, qu'il n'a jamais vue. Comme on connaît déjà la fin de l'histoire pour cette période, on peut compter ses réussites.

Toute la difficulté est de faire cette simulation **sans tricher**. Ce chapitre présente les règles qui l'empêchent. Leur ensemble s'appelle le **protocole d'évaluation**.

> **À retenir.** Le protocole a été fixé au lot 4, **avant** tout modèle complexe. Une méthode d'évaluation construite après avoir vu les résultats tend à se plier à ces résultats.

## 2. Choisir la bonne mesure

### Le taux de base

Sur la grille KKBox, environ **2 %** des lignes ont une cible à 1 : chaque lundi, à peine 2 abonnés actifs sur 100 partent dans les 30 jours. Cette proportion s'appelle le **taux de base**.

> **Attention.** Pourquoi 2 %, alors que l'étiquette officielle de KKBox affiche environ 9 % de départs ? Parce que l'étiquette officielle ne concerne que les abonnés dont l'abonnement expire dans le mois. La grille, elle, contient chaque semaine **tous** les abonnés actifs, y compris ceux dont l'abonnement court encore pour des mois.

### Pourquoi l'exactitude ne convient pas

L'**exactitude** est la part de bonnes réponses. Avec 2 % de départs, un modèle qui répond toujours « il reste » obtient 98 % d'exactitude sans détecter un seul départ. Cette mesure ne dit donc rien d'utile ici.

### La Precision@K, mesure principale

Revenons au besoin : chaque lundi, l'équipe appelle les 50 premiers de la liste. Ce qui compte, c'est la qualité de ces 50 noms.

La **Precision@K** répond exactement à cette question : parmi les K premiers de la liste, quelle part est réellement partie ? Avec K = 50, si 17 abonnés sur les 50 premiers partent, la Precision@50 vaut 17 / 50 = 0,34.

Deux précisions importantes.

- **Elle se calcule semaine par semaine, puis on fait la moyenne.** Prendre les 50 meilleurs scores de toute l'année n'aurait aucun sens : l'équipe appelle 50 personnes **par semaine**, pas 50 par an.
- **Les égalités sont départagées toujours de la même façon** : par score, puis par revenu, puis par identifiant. Deux exécutions sur les mêmes données donnent donc exactement la même liste.

### Trois mesures complémentaires

- Le **rappel au rang K** : parmi **tous** les abonnés partis, quelle part figurait dans les listes ? Il mesure ce qu'on capture, là où la précision mesure la qualité des appels.
- Le **lift** : combien de fois une méthode fait mieux qu'une méthode de référence. Un lift de 3,4 contre le tri par revenu signifie une précision 3,4 fois plus élevée.
- Le **ROC-AUC** : il mesure si une méthode place globalement les abonnés qui partent au-dessus de ceux qui restent. 0,5 correspond au hasard, 1 à un classement parfait. Il est calculé **pour information** seulement, car il juge toute la liste, alors que l'équipe n'en utilise que le haut.

## 3. Séparer passé et futur

### Pourquoi on ne mélange pas au hasard

La méthode classique consiste à mélanger les lignes au hasard, puis à en garder 80 % pour l'apprentissage et 20 % pour le test. Ici, ce serait une tricherie.

Pourquoi ? Parce qu'un même abonné apparaît chaque semaine. Sa ligne du lundi 7 mars pourrait tomber dans l'apprentissage, et sa ligne du lundi 14 mars dans le test. Les deux se ressemblent énormément, et la première dit déjà si l'abonné est parti. Le modèle aurait vu la réponse.

La séparation se fait donc **dans le temps** : on apprend sur le passé, on teste sur la période qui suit.

### Le piège qui reste : l'embargo

Même avec une coupure dans le temps, une fuite subsiste. Prenons une coupure au 1er juin.

- La dernière ligne d'apprentissage est celle du lundi 30 mai.
- Sa cible dit si l'abonné part **entre le 30 mai et le 29 juin**.
- Donc cette cible dépend de ce qui se passe **pendant la période de test**.

Le modèle apprendrait des faits qui appartiennent à la période qu'il doit prédire.

La parade s'appelle l'**embargo** : on laisse un intervalle vide entre la fin de l'apprentissage et le début du test, au moins aussi long que l'horizon de 30 jours.

```text
temps ──────────────────────────────────────────────────────────────►
|<────────── apprentissage ──────────>|<─ embargo ─>|<──── test ────>|
                                      |   30 jours   |
```

La **purge** complète l'embargo : on retire de l'apprentissage toute ligne dont la cible se résout après le début du test. Les deux protections sont appliquées ensemble, pour ne pas supposer que l'une implique l'autre.

> **Dans les coulisses.** L'outil standard de scikit-learn pour les séries temporelles propose un paramètre d'écart, `gap`. La première revue du projet l'avait présenté comme la solution. C'était inexact : ce paramètre compte des **lignes**, pas des **jours**. Or la grille contient un nombre variable d'abonnés par semaine. Le découpage est donc fait sur les dates, dans `src/churn/evaluation/splitting.py`, et l'erreur de la revue a été corrigée par écrit.

### Quatre plis, une fenêtre qui s'agrandit

Une seule période de test serait fragile : un bon résultat pourrait tenir à une période facile. Le projet découpe donc les dates en cinq blocs successifs et construit quatre **plis** :

| Pli | Apprentissage | Test |
| ---: | :--- | :--- |
| 0 | bloc 1 | bloc 2 |
| 1 | blocs 1 et 2 | bloc 3 |
| 2 | blocs 1 à 3 | bloc 4 |
| 3 | blocs 1 à 4 | bloc 5 |

À chaque pli, l'apprentissage s'agrandit, comme un modèle réentraîné au fil du temps en situation réelle. Les résultats sont ensuite moyennés sur les quatre plis, et leur **écart type**, qui mesure leur dispersion, donne une idée de ce qui relève du bruit.

Un test vérifie qu'aucune ligne d'apprentissage n'a une cible qui se résout pendant son test. Et pour prouver que ce test sait mordre, un pli volontairement mal construit, sans embargo, doit le faire échouer.

## 4. Les lignes de base : que faut-il battre ?

Une précision de 0,33 est-elle bonne ? Impossible de le dire sans point de comparaison. Le projet mesure donc trois méthodes simples, appelées **lignes de base**. Chacune répond à une question qu'un lecteur sceptique poserait.

| Ligne de base | Question | Ce qu'on attend |
| :--- | :--- | :--- |
| **Hasard** | Que donne une liste tirée au sort ? | Une précision égale au taux de base. C'est un contrôle de la mesure. |
| **Tri par revenu** | Que fait un conseiller sans outil, qui appelle d'abord les clients qui paient le plus ? | La référence métier. Le lift de chaque méthode s'exprime contre elle. |
| **Régression logistique** | Que donne un modèle simple et classique ? | Si un modèle complexe ne la bat pas nettement, il ne justifie pas sa complexité. |

La **régression logistique** attribue un poids à chaque variable, additionne le tout, et transforme la somme en score entre 0 et 1. Elle est simple, rapide et bien connue.

> **Attention.** Avant d'entraîner la régression logistique, les variables sont mises à la même échelle, ce qu'on appelle la **normalisation**. La moyenne et l'écart type utilisés sont calculés **sur les seules lignes d'apprentissage**. Les calculer sur tout le tableau ferait fuiter une information de la période de test.

## 5. Un protocole unique pour tous

Tout classement, qu'il s'agisse d'une ligne de base ou du futur modèle, passe par la **même fonction** d'évaluation : mêmes plis, mêmes semaines, même K. C'est la seule façon de comparer à armes égales.

Et chaque rapport produit porte en première ligne la **source des données** : KKBox, ou la mention de données fictives. Un chiffre recopié dans une présentation perd son contexte ; la mention voyage avec lui.

> **Dans les coulisses.** La première mesure des lignes de base sur KKBox donnait exactement la même précision, 0,0068, au tri par revenu et à la régression logistique. Une coïncidence parfaite est suspecte. L'enquête a montré que les données d'apprentissage ne contenaient **aucun départ** : la grille partait de 2004, dix ans avant les premières transactions. La régression logistique, n'ayant rien à apprendre, rendait des scores identiques, départagés par le revenu. La grille a été corrigée, c'est la décision D17. Et le protocole **refuse désormais** d'évaluer un pli dont l'apprentissage ne contient qu'une seule classe, au lieu de produire un chiffre en silence.

## 6. Les résultats des lignes de base

Voici les lignes de base mesurées sur KKBox, sur la grille actuelle, moyennées sur les quatre plis :

| Classement | Precision@50 | Sur 50 appels, départs trouvés | ROC-AUC |
| :--- | ---: | ---: | ---: |
| Hasard | 0,021 | 1 | 0,50 |
| Tri par revenu | 0,098 | 5 | 0,69 |
| Régression logistique | 0,149 | 7 | 0,72 |

Le hasard retombe bien sur le taux de base : la mesure est cohérente. La régression logistique fait mieux que le tri par revenu. C'est la barre que le modèle du chapitre 8 doit franchir.

Ces chiffres ne sont pas ceux mesurés à l'origine au lot 4. Ils ont été **remesurés** au lot 5, après la correction d'une fuite et l'ajout du journal d'écoute complet. Le chapitre 8 explique pourquoi, et `docs/resultats.md` conserve les deux mesures.

---

## À vous de jouer

**Contexte.** Une petite équipe appelle **4 abonnés par semaine**. Voici, pour deux semaines, les 4 premiers de la liste et ce qu'ils sont devenus : 1 signifie « parti dans les 30 jours ».

| Semaine | Rang 1 | Rang 2 | Rang 3 | Rang 4 | Départs au total dans la semaine |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Semaine 1 | 1 | 0 | 1 | 1 | 4 |
| Semaine 2 | 0 | 0 | 1 | 0 | 2 |

**Questions.**

1. Calculez la Precision@4 de chaque semaine, puis leur moyenne.
2. Calculez le rappel au rang 4 sur les deux semaines réunies.
3. Un collègue propose de prendre « les 4 meilleurs scores des deux semaines confondues ». Pourquoi est-ce une mauvaise idée ?
4. Le taux de base de ces deux semaines vaut 3 %. Une liste tirée au hasard obtient une Precision@4 de 0,25. Que concluez-vous sur la mesure ?

<details>
<summary>Voir la correction</summary>

1. **Semaine 1 : 3 / 4 = 0,75. Semaine 2 : 1 / 4 = 0,25. Moyenne : 0,50.**

2. **Rappel : 4 / 6 ≈ 0,67.** Les listes ont capturé 3 + 1 = 4 départs, sur 4 + 2 = 6 départs au total.

3. **Parce que l'équipe appelle 4 personnes chaque semaine, pas 4 en tout.** Si les 4 meilleurs scores tombent tous en semaine 1, la semaine 2 n'aurait aucun appel. Une mesure globale ne correspond à aucune situation réelle.

4. **Il y a probablement un problème.** Sur une liste tirée au hasard, la précision doit rester proche du taux de base, ici 0,03. Un écart aussi grand, 0,25, signale soit un défaut de calcul, soit un échantillon trop petit pour conclure. C'est pourquoi le hasard sert de contrôle.

</details>

---

## En résumé

- Évaluer, c'est **simuler l'avenir avec le passé**, sans tricher. Le **protocole** est fixé avant tout modèle.
- Avec un **taux de base** de 2 %, l'**exactitude** ne veut rien dire. La mesure principale est la **Precision@50**, calculée **chaque semaine** puis moyennée.
- Le **rappel**, le **lift** et le **ROC-AUC** complètent la lecture. Le ROC-AUC est donné pour information seulement.
- Les données sont séparées **dans le temps**, avec un **embargo** de 30 jours et une **purge**, sur **quatre plis** dont l'apprentissage s'agrandit.
- Trois **lignes de base**, hasard, tri par revenu et régression logistique, donnent les points de comparaison.
- Tout classement passe par le **même protocole**, et chaque rapport indique sa **source**.

**Chapitre précédent :** [6. Le tableau d'apprentissage](06-tableau-apprentissage.md) · **Chapitre suivant :** [8. Entraîner le modèle sans se tromper soi-même](08-entrainer-le-modele.md)
