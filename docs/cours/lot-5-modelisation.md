# Lot 5. Modélisation et explicabilité

> Ce cours raconte le lot 5 du projet : ce qui a été fait, pourquoi, et comment. Il suppose seulement de savoir ce qu'est un tableau de données. Chaque terme technique est défini à sa première apparition. Les chiffres détaillés sont dans `docs/resultats.md`.

## En une phrase

On a entraîné un modèle qui classe les abonnés KKBox selon leur risque de partir dans les 30 jours, on a vérifié honnêtement qu'il fait mieux que des méthodes simples, et on lui a appris à dire pourquoi il juge un abonné à risque.

## 1. Où on en était

Rappel des lots précédents, en quatre idées.

**La question posée.** Chaque lundi, une équipe peut appeler 50 abonnés. Lesquels appeler pour en retenir le plus ? On cherche donc à **classer**, pas à prédire une probabilité exacte.

**La grille.** Le jeu d'apprentissage est un grand tableau. Chaque ligne est un couple *(abonné, lundi)*, noté `(client_id, T0)`. `T0` est la date d'observation : on se place ce lundi-là, et on ne regarde que le passé.

**La cible.** Pour chaque ligne, `y = 1` si l'abonné a résilié dans les 30 jours qui suivent `T0`, sinon `y = 0`. C'est ce que le modèle doit apprendre à deviner.

**La mesure.** La *Precision@50* : parmi les 50 abonnés classés en tête chaque semaine, quelle part est vraiment partie ? Le lot 4 avait mesuré trois méthodes simples, appelées *lignes de base* : le hasard, le tri par revenu, et une régression logistique, qui est un modèle linéaire classique. Un modèle plus complexe n'a d'intérêt que s'il les bat nettement.

## 2. Avant de modéliser : une fuite trouvée

### Qu'est-ce qu'une fuite ?

Une *fuite de données* se produit quand le modèle apprend avec une information qu'il n'aurait pas eue au moment de décider. C'est comme réviser un examen avec le corrigé : les notes à l'entraînement sont excellentes, et le jour de l'examen, tout s'effondre.

Dans ce projet, la règle est simple : pour une ligne `(abonné, T0)`, on n'a le droit d'utiliser que ce qui s'est passé **strictement avant** `T0`.

### Le symptôme

En relisant les résultats du lot 4, un chiffre a attiré l'attention. Trier les abonnés par revenu donnait un *ROC-AUC* de 0,663. Le ROC-AUC mesure si une méthode place les abonnés qui partent au-dessus de ceux qui restent : 0,5 correspond au hasard, 1 à un classement parfait. Pour un simple tri par prix d'abonnement, c'était étonnamment élevé.

### L'enquête

Le revenu d'un abonné, la colonne `mrr`, était calculé une seule fois, à partir de **sa dernière transaction**. Or cette dernière transaction peut dater de plusieurs mois après `T0`.

Exemple : un abonné paie un forfait mensuel en 2015, puis passe à un forfait annuel en 2016. Pour une ligne observée en 2015, le tableau affichait le revenu du forfait de 2016. On lisait le futur.

La mesure a confirmé le problème. Sur les 410 523 lignes de la grille, le revenu figé différait du revenu réellement en vigueur à `T0` dans **22,5 %** des cas, et même dans **32,6 %** des lignes où l'abonné allait partir. Un tiers des abonnés, 34 %, a changé de revenu au moins une fois.

### Pourquoi les tests ne l'avaient pas vu

Le projet possède une *sentinelle anti-fuite* : un test qui supprime tous les événements postérieurs à `T0`, recalcule les variables, et vérifie que rien ne change. Mais ce test coupe le **journal des événements**. Le revenu venait d'une autre table, le **référentiel des comptes**, que la sentinelle ne touchait pas. La fuite passait donc à côté.

### La fuite gonflait-elle les résultats ? Trois réponses

La question paraît simple. Elle a reçu trois réponses différentes, et c'est instructif.

1. **Une première mesure rapide**, sur une date par mois et les seuls abonnés ayant déjà payé, répondait non : le revenu en vigueur classait mieux que le revenu figé.
2. **Le ROC-AUC sur la vraie grille** répondait oui : 0,641 pour le revenu figé contre 0,607 pour le revenu en vigueur.
3. **La Precision@50 sur la vraie grille**, la mesure qui pilote le projet, répondait non : 0,0795 pour le revenu figé contre 0,0980 pour le revenu en vigueur.

Pourquoi ces contradictions ? La première mesure écartait 27 % des lignes : ce n'était pas la même population. Et en tête de liste, chaque semaine, 141 à 261 abonnés partagent le même revenu maximal. Le choix des 50 premiers parmi eux dépend surtout de la règle de départage, pas du revenu.

La seule conclusion solide est donc : **la règle était violée, et le classement en dépendait**. On corrige, et on remesure tout.

> **Leçon.** Une conclusion vaut pour une mesure et une population. Quand deux mesures se contredisent, on écrit ce qui est établi, pas ce qui arrange.

### La correction

Chaque transaction émet désormais un événement `revenu_mensuel`, daté, dans le journal. Le revenu d'une ligne `(abonné, T0)` est la dernière valeur de cet événement **strictement avant** `T0`.

Ce type d'événement est particulier. La plupart des événements sont des **flux** : des choses qui arrivent, qu'on peut compter ou additionner sur une période, comme « 12 jours d'écoute sur 30 jours ». Le revenu est un **état** : une valeur en vigueur. Additionner un revenu mensuel sur 90 jours n'a aucun sens. On lit donc la dernière valeur connue, sans jamais la sommer.

Deux tests protègent maintenant cette règle :

- la sentinelle est étendue au revenu ;
- un nouveau test **réécrit toutes les colonnes du référentiel** avec des valeurs absurdes, et vérifie que la grille et les variables restent strictement identiques. S'il échoue un jour, c'est qu'une colonne du référentiel s'est glissée dans l'apprentissage.

C'est la décision D18.

> **Leçon.** Un test anti-fuite ne protège que ce qu'il manipule. Pour chaque source d'information, il faut se demander quel test la couvre vraiment.

### Un revenu nul ne veut pas dire gratuit

27 % des lignes n'ont aucun revenu connu à `T0`. L'extrait KKBox commence en janvier 2015. Un abonné qui a payé une formule annuelle en 2014 n'a aucune transaction visible avant son renouvellement. Son revenu vaut donc zéro dans nos données, ce qui signifie « aucun revenu connu », pas « abonné gratuit ». On ne remplace surtout pas ce zéro par la valeur du référentiel : ce serait réintroduire la fuite.

## 3. Le journal d'écoute complet

Au lot 4, les 36 variables d'écoute étaient **constantes** : le seul journal d'écoute disponible couvrait mars 2017, après la dernière date d'observation. La régression logistique ne s'appuyait donc que sur les transactions.

Le journal complet, `user_logs.csv`, pèse 6,65 Go compressé et 30,5 Go une fois décompressé. Il n'est jamais chargé en mémoire d'un bloc : il est lu par morceaux d'un million de lignes, et seules les lignes des abonnés de l'échantillon sont gardées. La lecture a pris 18 minutes et n'a jamais dépassé 0,55 Go de mémoire. Résultat : 1 391 093 jours d'écoute pour 7 881 abonnés.

Un petit défaut a été corrigé au passage. Le script considérait qu'une archive était déjà décompressée dès que le fichier existait. Or une extraction interrompue laisse un fichier incomplet sur le disque. Le script compare maintenant la taille du fichier à celle annoncée par l'archive.

> **Leçon.** « Le fichier existe » ne veut pas dire « le fichier est complet ».

Un second piège, du même genre, a été évité de justesse au moment du commit. Le fichier `.gitignore` indique à Git quels fichiers ne jamais enregistrer. Il contenait la ligne `models/`, destinée à exclure les modèles entraînés, trop lourds et régénérables. Mais un motif sans `/` au début s'applique à **tout** dossier de ce nom, où qu'il soit. Le dossier de code `src/churn/models/` était donc ignoré lui aussi, sans le moindre message. Les tests passaient sur ce poste, et le code du modèle ne serait jamais parti sur GitHub. La ligne est devenue `/models/`, qui ne vise que le dossier à la racine du projet.

> **Leçon.** Avant un commit, relire la liste des fichiers ajoutés. Un fichier absent ne produit aucune erreur.

## 4. Le modèle : XGBoost, expliqué simplement

### Un arbre de décision

Un *arbre de décision* pose une suite de questions : « le renouvellement automatique est-il désactivé ? », puis « l'abonné a-t-il écouté moins de 10 jours ce mois-ci ? ». Chaque chemin mène à une feuille qui donne un score. Un arbre seul est lisible mais peu précis.

### Le boosting

Le *gradient boosting* construit des arbres **les uns après les autres**. Chaque nouvel arbre se concentre sur les erreurs laissées par les précédents, et le score final est la somme des réponses de tous les arbres. XGBoost est une bibliothèque qui fait cela très efficacement. Elle a été retenue au cadrage, décision D12, notamment parce qu'elle sait calculer elle-même l'explication de chaque score, ce qui sert en section 7.

Contrairement à la régression logistique, un ensemble d'arbres capte naturellement les **seuils** et les **combinaisons** : « aucune écoute depuis 7 jours **et** renouvellement désactivé » peut peser bien plus que la somme des deux signaux pris séparément.

### Les hyperparamètres

Un *hyperparamètre* est un réglage choisi avant l'apprentissage, et non appris par le modèle. On en règle trois :

| Réglage | Ce qu'il contrôle | Valeurs essayées |
| :--- | :--- | :--- |
| `max_depth` | Nombre de questions par arbre. Plus il est grand, plus un arbre capte des combinaisons fines, et plus il risque d'apprendre du bruit | 4, 6 |
| `n_estimators` | Nombre d'arbres | 300, 600 |
| `learning_rate` | Poids de chaque nouvel arbre. Petit, l'apprentissage est prudent et lent | 0,05 ; 0,1 |

Cela fait 2 × 2 × 2 = 8 combinaisons. La grille est volontairement petite, décision D16 : un gain minime obtenu par une recherche plus large ne se verrait pas, un protocole correct si.

## 5. Choisir les réglages sans tricher

### Le piège

Imaginons qu'on essaie les 8 combinaisons sur la période de test, et qu'on garde la meilleure. Le chiffre annoncé serait le meilleur de 8 tirages, donc optimiste par construction. On aurait choisi le réglage **en regardant les réponses de l'examen**.

### La méthode

Le choix se fait **à l'intérieur des données d'entraînement de chaque pli**, sans jamais toucher à la période de test :

```text
|<------------------ entraînement du pli ------------------>| embargo |<-- test -->|
|<-- apprentissage interne -->| embargo |<-- validation -->|
```

1. Les dates d'entraînement sont coupées en deux moitiés chronologiques, avec le même embargo qu'au lot 4.
2. Chaque combinaison apprend sur la première moitié et est mesurée, en Precision@50, sur la seconde.
3. La meilleure est retenue, puis le modèle est réentraîné sur tout l'entraînement du pli avec ce réglage.
4. Il est enfin évalué sur la période de test, qu'il n'a jamais vue.

Rappel : l'*embargo* est un intervalle vide entre apprentissage et évaluation, au moins aussi long que l'horizon de 30 jours. Sans lui, les dernières lignes d'apprentissage auraient une cible qui se résout pendant la période évaluée.

Sur KKBox, la sélection a presque toujours retenu la combinaison la plus prudente : profondeur 4, 300 arbres, taux 0,05. C'est un indice que des modèles encore plus simples feraient peut-être aussi bien. On ne l'a pas vérifié, et c'est écrit dans les limites.

### Quand le choix est impossible

Sur un pli trop court, le découpage interne peut ne laisser aucune ligne d'apprentissage, ou une seule classe. Le code ne s'arrête pas en silence : il garde le premier réglage de la grille, écrit un avertissement, et le rapport affiche la raison. C'est arrivé sur le petit jeu synthétique des tests, jamais sur KKBox.

### Une précaution de plus

Le protocole transmet à chaque classement les lignes de test **sans leur colonne cible**. Avant ce lot, la grille de test arrivait complète, cible comprise. Aucune ligne de base ne la lisait, mais rien ne l'empêchait. Un test vérifie désormais que la cible n'atteint jamais un classement.

## 6. Deux questions, deux mesures

Comparer « XGBoost avec le journal d'écoute » à « régression logistique sans le journal » mélangerait deux effets. Si le score monte, est-ce grâce au modèle ou grâce aux données ? On sépare donc les deux questions. Retirer un ingrédient à la fois pour mesurer son apport s'appelle une *ablation*.

| Question | Comparaison, à armes égales |
| :--- | :--- |
| Que gagne-t-on avec le modèle ? | Régression logistique contre XGBoost, **mêmes variables** : transactions, ancienneté et revenu |
| Que gagne-t-on avec les données ? | XGBoost contre XGBoost, **même modèle** : avec et sans le journal d'écoute |

Les six classements passent exactement dans les mêmes plis, les mêmes semaines et avec le même K.

### Résultats sur KKBox

Moyenne sur les quatre plis :

| Classement | Precision@50 | Sur 50 appels, départs trouvés |
| :--- | ---: | ---: |
| Hasard | 0,021 | 1 |
| Tri par revenu | 0,098 | 5 |
| Régression logistique, finance seule | 0,145 | 7 |
| Régression logistique, tout | 0,149 | 7 |
| XGBoost, finance seule | 0,314 | 16 |
| **XGBoost, tout** | **0,333** | **17** |

### Lecture

**Le gain du modèle est net.** Sur les mêmes variables financières, XGBoost fait plus que doubler la précision de la régression logistique : +0,169. Surtout, le gain est positif **sur chacun des quatre plis**, entre +0,155 et +0,179. Quand un écart est aussi régulier et bien plus grand que la variation d'un pli à l'autre, on peut le considérer comme établi.

**Le gain des données ne l'est pas.** Ajouter le journal d'écoute fait passer XGBoost de 0,314 à 0,333, soit +0,019 en moyenne. Mais par pli, l'écart vaut -0,025, +0,030, +0,033 et +0,038. Il est négatif sur un pli, et sa variation d'un pli à l'autre, 0,026, dépasse sa moyenne. Avec quatre plis, on ne peut pas distinguer ce gain du bruit.

C'est un résultat, pas un échec. Avant la mesure, l'hypothèse était que le taux de complétion d'écoute porterait le signal le plus fort du jeu. **La mesure ne le confirme pas.** Une explication plausible, non vérifiée : un abonné qui s'apprête à partir cesse aussi d'écouter, donc l'écoute répète en partie ce que les transactions disent déjà.

> **Leçon.** Mesurer deux effets séparément évite d'attribuer au modèle ce qui vient des données, ou l'inverse. Et une hypothèse non confirmée s'écrit comme telle, dans le rapport.

## 7. Expliquer un score : les trois facteurs de risque

Un score dit **qui** appeler. Il ne dit pas **quoi** dire au téléphone. Le lot 5 produit donc, pour chaque abonné, jusqu'à trois motifs lisibles.

### L'idée des valeurs de Shapley

Pensez à une addition partagée au restaurant. Le modèle part d'un score moyen, identique pour tout le monde. Pour un abonné donné, chaque variable pousse ce score vers le haut ou vers le bas. Les *valeurs de Shapley* répartissent l'écart entre le score de l'abonné et le score moyen, de façon équitable, entre toutes les variables. Leur somme, ajoutée au score moyen, redonne exactement le score de l'abonné.

XGBoost les calcule lui-même avec l'option `pred_contribs=True`. Le tableau renvoyé contient une colonne de plus que le nombre de variables : la dernière est le **biais**, ce score moyen commun à tous. Elle n'appartient à aucune variable, donc elle est retirée avant de chercher les facteurs. Sinon, le même « motif » apparaîtrait pour tout le monde. Un test vérifie que cette colonne est bien constante, et que la somme retombe sur le score brut du modèle.

### Additionner par variable d'origine

Le nombre de jours d'écoute existe en plusieurs exemplaires : sur 7, 30 et 90 jours, en comptage et en somme. Ce sont six colonnes, mais **une seule raison**. Si on classait les colonnes séparément, le commercial lirait trois fois « fréquence d'usage ». Les contributions sont donc additionnées par *variable d'origine* avant le classement, décision D7.

Exemple :

| Colonne | Contribution |
| :--- | ---: |
| `count_connexion_7j` | + 0,10 |
| `sum_connexion_30j` | + 0,05 |
| `trend_count_connexion_30j` | + 0,20 |

Les deux premières donnent la variable `connexion` : + 0,15. La troisième donne `trend_connexion` : + 0,20. Une tendance est gardée à part, parce qu'un niveau bas et une chute récente sont deux motifs d'appel différents.

### Ne garder que les motifs significatifs

Seules les contributions **positives**, celles qui augmentent le risque, peuvent devenir un motif. Et seulement si elles dépassent un *seuil de signification*. Ce seuil est calculé à l'entraînement comme le 75e centile des contributions en valeur absolue, puis enregistré avec le modèle. Il n'est jamais écrit à la main dans le code. Sur KKBox, il vaut 0,1627.

Un abonné sans contribution au-dessus du seuil reçoit des motifs **vides**. Un motif inventé est pire qu'un motif absent. Sur les 5 074 abonnés de la dernière semaine observée :

| Motifs significatifs | Part des abonnés |
| :--- | ---: |
| Aucun | 26 % |
| Un | 48 % |
| Deux | 18 % |
| Trois | 8 % |

Les abonnés les plus à risque ont presque toujours un motif clair : aucun des 50 premiers n'en manque. Parmi les 50 derniers, 36 % n'en ont pas, ce qui est logique : rien ne les pousse vers le risque.

### Des libellés qui ne mentent pas

Chaque variable d'origine a un libellé métier dans `config/feature_mapping.yaml`, par exemple `[PRODUCT] Fréquence d'usage`. Si le modèle peut produire une variable absente de ce dictionnaire, l'entraînement échoue : un motif ne s'affiche jamais sous un nom technique.

Les libellés sont **neutres**. Une contribution positive dit que la valeur de la variable pousse le risque vers le haut, pas si cette valeur est haute ou basse. Écrire « Chute de l'usage » serait une supposition. Déduire le sens à partir de la valeur elle-même est laissé à un lot ultérieur.

### Exemple réel

Voici les trois premières lignes de la liste de la dernière semaine :

| Rang | Motif 1 | Motif 2 | Motif 3 |
| ---: | :--- | :--- | :--- |
| 1 | [GENERAL] Revenu mensuel en vigueur | [FINANCE] Statut du renouvellement automatique | [FINANCE] Évolution récente du renouvellement automatique |
| 2 | [FINANCE] Évolution récente de la facturation | [FINANCE] Statut du renouvellement automatique | [FINANCE] Facturation |
| 4 | [FINANCE] Annulations d'abonnement | [FINANCE] Évolution récente de la facturation | [GENERAL] Ancienneté du compte |

Deux remarques honnêtes. D'abord, cette liste est **en échantillon** : le modèle final a été entraîné sur ces lignes, cible comprise. Elle montre la forme de l'explication, elle ne mesure pas la performance, qui se lit en section 6. Ensuite, les motifs `[GENERAL]` comme le revenu ou l'ancienneté n'offrent aucun levier au commercial. Faut-il les montrer ? La question est reportée au lot 6, qui construit l'export.

## 8. Sauvegarder un modèle qu'on peut retrouver

Le modèle est enregistré avec une fiche d'identité, `metadata.json` :

- une **version**, calculée à partir des données, des réglages et de la graine. Deux entraînements identiques donnent la même version. Sur KKBox : `0.1.0-b8f55da1e566` ;
- l'**empreinte** des données d'entraînement, une signature qui change si une seule valeur change ;
- les réglages retenus, la graine, le seuil de signification, la source des données.

Un test recharge le modèle et vérifie que les scores sont **identiques au bit près**. C'est ce qui permettra, au lot 6, de reproduire un export des mois plus tard.

## 9. Les tests qui protègent ce lot

| Test | Ce qu'il empêche |
| :--- | :--- |
| Le référentiel réécrit ne change rien | Qu'une colonne figée à la date d'extraction serve à apprendre |
| La sentinelle appliquée au revenu | Que le revenu lu à `T0` regarde le futur |
| Le revenu comparé à une lecture naïve | Une erreur de calcul silencieuse dans la lecture de l'état |
| Plusieurs revenus au même instant | Un résultat qui dépendrait de l'ordre des lignes |
| La cible du test n'atteint aucun classement | Qu'un modèle lise la réponse dans la grille de test |
| La sélection a lieu dans chaque pli | Que les réglages soient choisis sur la période de test |
| Les contributions d'une variable encodée s'additionnent | Qu'un motif apparaisse trois fois |
| La colonne de biais est écartée | Qu'un même motif s'affiche pour tout le monde |
| Un abonné sans facteur significatif reçoit des motifs vides | Un motif inventé |
| Une variable sans libellé fait échouer l'entraînement | Un nom technique affiché au métier |
| Le modèle rechargé score à l'identique | Un export impossible à reproduire |

## 10. Ce qu'il faut retenir

- **Corriger avant de mesurer.** Une fuite trouvée au démarrage a fait remesurer toutes les lignes de base. Mieux vaut un chiffre plus bas et juste qu'un chiffre flatteur et faux.
- **Un test ne protège que ce qu'il touche.** La sentinelle coupait le journal, la fuite venait du référentiel.
- **Choisir les réglages sans voir le test.** Sinon le chiffre annoncé est le meilleur de plusieurs tirages.
- **Séparer les effets.** Le modèle apporte un gain net et régulier, +0,169 de précision à variables égales. Le journal d'écoute apporte un gain qu'on ne peut pas distinguer du bruit.
- **Le résultat, en clair.** Sur 50 appels par semaine, le modèle trouve environ 17 abonnés sur le départ, contre 5 en appelant les plus gros revenus et 7 avec une régression logistique.
- **Expliquer sans inventer.** Trois motifs au plus, seulement s'ils sont significatifs, avec des libellés qui nomment le signal sans prétendre en connaître le sens.
