# Chapitre 8. Entraîner le modèle sans se tromper soi-même

> **Partie 3, mesurer et prédire** · Lecture : 35 minutes · Prérequis : chapitre 7

## Ce que vous allez apprendre

À la fin de ce chapitre, vous saurez :

- détecter une fuite d'information cachée dans une table de référence ;
- expliquer simplement ce qu'est un arbre de décision et le **gradient boosting** ;
- choisir les réglages d'un modèle sans jamais regarder la période de test ;
- séparer l'apport d'un modèle de l'apport de nouvelles données, grâce à une **ablation** ;
- lire les résultats du modèle et leurs limites.

---

## 1. Avant d'entraîner : une fuite trouvée

### Le symptôme

En relisant les résultats du lot 4, un chiffre a attiré l'attention. Trier les abonnés par revenu obtenait un ROC-AUC de 0,663. Pour un simple tri par prix d'abonnement, c'était étonnamment élevé. Un chiffre trop beau mérite une enquête.

### L'enquête

Le revenu de chaque abonné était calculé une seule fois, à partir de **sa dernière transaction**, parfois plusieurs mois après `T0`.

Exemple : un abonné paie un forfait mensuel en 2015, puis passe à un forfait annuel en 2016. Pour une ligne observée en 2015, le tableau affichait le revenu de 2016. On lisait le futur.

La mesure a confirmé le problème. Sur les 410 523 lignes de la grille, ce revenu figé différait du revenu réellement en vigueur à `T0` dans **22,5 %** des cas, et même dans **32,6 %** des lignes où l'abonné allait partir. Un tiers des abonnés, 34 %, a changé de revenu au moins une fois.

### Pourquoi la sentinelle ne l'avait pas vu

La sentinelle du chapitre 6 supprime les **événements** postérieurs à `T0` et vérifie que rien ne change. Mais ce revenu ne venait pas du journal d'événements : il venait de la **table des comptes**, que la sentinelle ne touchait pas. La fuite passait à côté.

> **À retenir.** Un test ne protège que ce qu'il manipule. Pour chaque source d'information, il faut se demander quel test la couvre vraiment.

### La fuite gonflait-elle les résultats ? Trois réponses différentes

1. Une **première mesure rapide**, sur une date par mois et les seuls abonnés ayant déjà payé, répondait non.
2. Le **ROC-AUC sur la vraie grille** répondait oui : 0,641 pour le revenu figé contre 0,607 pour le revenu en vigueur.
3. La **Precision@50 sur la vraie grille**, la mesure qui pilote le projet, répondait non : 0,0795 pour le revenu figé contre 0,0980 pour le revenu en vigueur.

Pourquoi ces contradictions ? La première mesure écartait 27 % des lignes : ce n'était pas la même population. Et en tête de liste, chaque semaine, 141 à 261 abonnés partagent le même revenu maximal : le choix des 50 premiers parmi eux dépend surtout de la règle de départage.

La seule conclusion solide : **la règle était violée, et le classement en dépendait**. On corrige, et on remesure tout.

> **À retenir.** Une conclusion vaut pour une mesure et une population. Quand deux mesures se contredisent, on écrit ce qui est établi, pas ce qui arrange.

### La correction

Chaque transaction émet désormais un événement `revenu_mensuel`, daté, dans le journal. Le revenu d'une ligne est la **dernière valeur connue strictement avant `T0`**.

Ce type d'événement est un **état**, et non un **flux**. Un flux se compte ou s'additionne sur une période, comme des jours d'écoute. Un état est une valeur en vigueur : additionner un revenu mensuel sur 90 jours n'aurait aucun sens. On lit donc la dernière valeur connue.

Un nouveau test complète la sentinelle : il **réécrit toutes les colonnes de la table des comptes** avec des valeurs absurdes, et vérifie que la grille et les variables restent identiques. C'est la décision D18.

> **Attention.** 27 % des lignes n'ont aucun revenu connu à `T0` : l'extrait KKBox commence en 2015, et un abonné qui a payé un forfait annuel en 2014 n'a aucune transaction visible avant son renouvellement. Ce zéro signifie « inconnu », pas « gratuit ». On ne le remplace surtout pas par la valeur de la table des comptes : ce serait réintroduire la fuite.

## 2. Ajouter le journal d'écoute complet

Au lot 4, les variables d'écoute étaient **constantes** : le seul journal disponible couvrait mars 2017, après la dernière date d'observation. La régression logistique ne s'appuyait donc que sur les paiements.

Le journal complet a été extrait et converti : **1 391 093 jours d'écoute** pour 7 881 abonnés. La question devient : ces données améliorent-elles vraiment les prédictions ? La section 5 y répond.

> **Dans les coulisses.** Deux pièges du même genre ont été évités à cette étape. D'abord, le script considérait une archive comme décompressée dès que le fichier existait, alors qu'une extraction interrompue laisse un fichier incomplet : la taille est maintenant vérifiée. Ensuite, le fichier `.gitignore`, qui dit à Git quoi ne pas enregistrer, contenait la ligne `models/` pour exclure les modèles entraînés. Mais cette ligne excluait **tout** dossier nommé `models`, y compris le dossier de code `src/churn/models/`. Sans relecture de la liste des fichiers avant l'enregistrement, le code du modèle ne serait jamais parti sur GitHub, sans le moindre message d'erreur.

## 3. Le modèle : XGBoost, pas à pas

### Un arbre de décision

Un **arbre de décision** pose une suite de questions : « le renouvellement automatique est-il désactivé ? », puis « l'abonné a-t-il écouté moins de 10 jours ce mois-ci ? ». Chaque chemin mène à une feuille qui donne un score. Un arbre seul est lisible, mais peu précis.

### Le gradient boosting

Le **gradient boosting** construit des arbres **les uns après les autres**. Chaque nouvel arbre se concentre sur les erreurs laissées par les précédents. Le score final est la somme des réponses de tous les arbres.

Pensez à une équipe de correcteurs : le premier fait une estimation grossière, le deuxième corrige ses plus grosses erreurs, le troisième corrige ce qui reste, et ainsi de suite.

Contrairement à la régression logistique, un ensemble d'arbres capte naturellement les **seuils** et les **combinaisons**. « Aucune écoute depuis 7 jours **et** renouvellement désactivé » peut peser bien plus que la somme de ces deux signaux pris séparément.

**XGBoost** est une bibliothèque qui fait du gradient boosting très efficacement. Elle a été retenue au chapitre 3, notamment parce qu'elle calcule elle-même l'explication de chaque score.

### Les hyperparamètres

Un **hyperparamètre** est un réglage choisi avant l'apprentissage, et non appris par le modèle. On en règle trois :

| Réglage | Ce qu'il contrôle | Valeurs essayées |
| :--- | :--- | :--- |
| `max_depth` | Nombre de questions par arbre. Plus il est grand, plus un arbre capte des combinaisons fines, et plus il risque d'apprendre du bruit | 4, 6 |
| `n_estimators` | Nombre d'arbres | 300, 600 |
| `learning_rate` | Poids de chaque nouvel arbre. Petit, l'apprentissage est prudent et lent | 0,05 ; 0,1 |

Cela fait 2 × 2 × 2 = 8 combinaisons. La grille est volontairement petite : un gain minime obtenu par une recherche plus large ne se verrait pas, un protocole correct si.

## 4. Choisir les réglages sans regarder le test

### Le piège

Imaginons qu'on essaie les 8 combinaisons sur la période de test, et qu'on garde la meilleure. Le chiffre annoncé serait le meilleur de 8 essais, donc optimiste par construction. On aurait choisi le réglage **en regardant les réponses de l'examen**.

### La méthode

Le choix se fait **à l'intérieur de l'apprentissage de chaque pli** :

```text
|<──────────────── apprentissage du pli ─────────────────>| embargo |<─ test ─>|
|<── apprentissage interne ──>| embargo |<── validation ──>|
```

1. Les dates d'apprentissage du pli sont coupées en deux moitiés, avec le même embargo qu'au chapitre 7.
2. Chaque combinaison apprend sur la première moitié, et sa Precision@50 est mesurée sur la seconde, appelée **validation**.
3. La meilleure combinaison est retenue, et le modèle est réentraîné sur tout l'apprentissage du pli.
4. Il est enfin évalué sur le test, qu'il n'a jamais vu, ni directement ni à travers le choix de ses réglages.

Sur KKBox, la sélection a presque toujours retenu la combinaison la plus prudente : profondeur 4, 300 arbres, taux 0,05. C'est un indice que des modèles encore plus simples feraient peut-être aussi bien. Ce n'est pas vérifié, et c'est écrit dans les limites.

Si la sélection est impossible, par exemple quand la validation ne contient aucun départ, le code garde le premier réglage, **écrit un avertissement** et affiche la raison dans le rapport. Rien ne se passe en silence.

> **Attention.** Une autre précaution a été ajoutée au protocole : les lignes de test sont transmises au modèle **sans leur colonne cible**. Avant, la cible était présente dans le tableau transmis. Aucune méthode ne la lisait, mais rien ne l'empêchait. Un test vérifie désormais qu'elle n'arrive jamais jusqu'au modèle.

## 5. Deux questions, deux mesures

Comparer « XGBoost avec le journal d'écoute » à « régression logistique sans le journal » mélangerait deux effets. Si le score monte, est-ce grâce au modèle ou grâce aux données ?

On sépare donc les deux questions. Retirer un ingrédient à la fois pour mesurer son apport s'appelle une **ablation**.

| Question | Comparaison, à armes égales |
| :--- | :--- |
| Que gagne-t-on avec le modèle ? | Régression logistique contre XGBoost, **mêmes variables** : paiements, ancienneté, revenu |
| Que gagne-t-on avec les données d'écoute ? | XGBoost contre XGBoost, **même modèle** : avec et sans le journal d'écoute |

### Résultats sur KKBox

Six classements, mêmes plis, mêmes semaines, même K. Moyenne sur les quatre plis :

| Classement | Precision@50 | Sur 50 appels, départs trouvés |
| :--- | ---: | ---: |
| Hasard | 0,021 | 1 |
| Tri par revenu | 0,098 | 5 |
| Régression logistique, paiements seuls | 0,145 | 7 |
| Régression logistique, toutes variables | 0,149 | 7 |
| XGBoost, paiements seuls | 0,314 | 16 |
| **XGBoost, toutes variables** | **0,333** | **17** |

### Lecture

**Le gain du modèle est établi.** À variables égales, XGBoost fait plus que doubler la précision de la régression logistique : +0,169. Surtout, l'écart est positif **sur chacun des quatre plis** : +0,179, +0,155, +0,174 et +0,169. Quand un gain est aussi régulier, et bien plus grand que la variation d'un pli à l'autre, on peut le considérer comme réel.

**Le gain des données d'écoute ne l'est pas.** Ajouter le journal fait passer XGBoost de 0,314 à 0,333, soit +0,019 en moyenne. Mais par pli, l'écart vaut -0,025, +0,030, +0,033 et +0,038 : il est négatif sur un pli, et sa dispersion, 0,026, dépasse sa moyenne. Avec quatre plis, ce gain ne se distingue pas du bruit.

C'est un résultat, pas un échec. L'hypothèse de départ était que le taux de morceaux écoutés en entier porterait le signal le plus fort. **La mesure ne le confirme pas.** Une explication plausible, non vérifiée : un abonné qui s'apprête à partir cesse aussi d'écouter, si bien que l'écoute répète en partie ce que disent déjà les paiements.

> **À retenir.** Mesurer deux effets séparément évite d'attribuer au modèle ce qui vient des données, ou l'inverse. Une hypothèse non confirmée s'écrit comme telle.

### Les limites, écrites

- La capacité de 50 appels par semaine est une hypothèse : KKBox n'a pas d'équipe qui appelle ses abonnés.
- La régression logistique n'a pas été finement réglée. Une version mieux préparée ferait probablement mieux que 0,149.
- La sélection des réglages se loge dans le coin le plus prudent de la grille, et des modèles plus simples n'ont pas été essayés.
- L'échantillon compte 8 150 abonnés, sur 2,36 millions disponibles.

---

## À vous de jouer

**Contexte.** Une équipe teste un nouveau modèle de churn pour une application de sport. Voici son compte rendu :

> « Nous avons essayé 20 réglages différents et gardé celui qui donnait la meilleure Precision@50 sur les trois derniers mois. Ce modèle, qui utilise aussi les nouvelles données de la montre connectée, atteint 0,40, contre 0,15 pour l'ancienne régression logistique sans ces données. Les données de la montre sont donc très utiles. »

**Questions.**

1. Quel problème pose le choix du réglage sur les trois derniers mois ?
2. Peut-on conclure que les données de la montre sont « très utiles » ? Pourquoi ?
3. Proposez les deux comparaisons qui permettraient de conclure.
4. Le modèle utilise la colonne « formule actuelle » de la table des clients. Quel risque devez-vous vérifier ?

<details>
<summary>Voir la correction</summary>

1. **Le chiffre annoncé est optimiste par construction.** Si les trois derniers mois servent à choisir parmi 20 réglages, puis à annoncer le résultat, le 0,40 est le meilleur de 20 essais sur la même période. Il faut choisir le réglage sur une période de validation distincte, puis mesurer une seule fois sur un test jamais utilisé.

2. **Non.** Deux choses ont changé en même temps : le modèle et les données. Le gain peut venir entièrement du nouveau modèle, sans rien devoir à la montre.

3. **Les deux ablations :** l'ancienne régression logistique contre le nouveau modèle, **sans** les données de la montre, pour mesurer le gain du modèle ; le nouveau modèle **avec** et **sans** les données de la montre, pour mesurer le gain des données. Idéalement sur plusieurs plis, en regardant si l'écart est régulier.

4. **Une fuite par la table de référence.** « Formule actuelle » décrit le client **aujourd'hui**. Pour une ligne observée il y a un an, elle peut refléter un changement survenu après la date d'observation, par exemple une résiliation déjà enregistrée. Il faut lire la formule en vigueur à la date d'observation, et vérifier par un test que modifier cette table ne change rien au tableau d'apprentissage.

</details>

---

## En résumé

- Une **fuite** peut se cacher dans une **table de référence** qui décrit les clients aujourd'hui. Le revenu figé différait du revenu en vigueur sur 22,5 % des lignes. Il est désormais lu dans le journal, à `T0`.
- Un **arbre de décision** pose une suite de questions. Le **gradient boosting** enchaîne des centaines d'arbres qui corrigent les erreurs des précédents.
- Les **hyperparamètres** se choisissent sur une **validation** interne à l'apprentissage, jamais sur le test.
- Une **ablation** sépare l'apport du modèle de l'apport des données.
- Sur KKBox, le **gain du modèle est établi** : 17 départs trouvés sur 50 appels, contre 7 pour la régression logistique et 5 pour le tri par revenu. Le **gain des données d'écoute ne l'est pas**.

**Chapitre précédent :** [7. Évaluer honnêtement](07-evaluer-honnetement.md) · **Chapitre suivant :** [9. Expliquer chaque prédiction](09-expliquer-les-predictions.md)
