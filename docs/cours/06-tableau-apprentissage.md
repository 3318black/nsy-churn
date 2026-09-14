# Chapitre 6. Construire le tableau d'apprentissage sans tricher avec le temps

> **Partie 2, préparer les données** · Lecture : 35 minutes · Prérequis : chapitres 4 et 5

## Ce que vous allez apprendre

À la fin de ce chapitre, vous saurez :

- expliquer ce qu'est une **grille d'observation** et pourquoi on observe chaque abonné chaque semaine ;
- calculer à la main une **variable** sur une fenêtre de temps ;
- reconnaître une **fuite d'information** et appliquer la règle qui l'empêche ;
- expliquer le fonctionnement de la sentinelle anti-fuite et du contrôle par force brute.

C'est le chapitre le plus important du cours : c'est ici que se joue la validité de tout le projet.

---

## 1. Ce dont un modèle a besoin

Un modèle apprend à partir d'un **tableau d'exemples**. Chaque ligne est un exemple. Les colonnes décrivent la situation, et une dernière colonne donne la réponse.

- Les colonnes de description s'appellent des **variables**, par exemple « nombre de jours d'écoute sur les 30 derniers jours ».
- La colonne réponse est la **cible** vue au chapitre 5 : l'abonné est-il parti ensuite ?

Nos données sont un journal d'événements. Il faut donc le transformer en tableau d'exemples. Toute la difficulté est de le faire **sans jamais utiliser d'information venue du futur**.

## 2. La grille : photographier chaque abonné chaque lundi

### L'idée

Imaginez qu'on prenne une photo de chaque abonné **chaque lundi**, pendant deux ans. Sur chaque photo, on note ce qu'on savait de lui ce jour-là, puis on regarde s'il est parti dans les 30 jours suivants.

Chaque photo devient une ligne du tableau. Elle est identifiée par un couple **(abonné, lundi)**, noté `(client_id, T0)`. **`T0`** est la **date d'observation** : le lundi où l'on se place.

| client_id | T0 | Variables : ce qu'on savait avant T0 | Cible : parti dans les 30 jours ? |
| :--- | :--- | :--- | ---: |
| A1 | 2016-03-07 | 21 jours d'écoute sur 30, renouvellement actif... | 0 |
| A1 | 2016-03-14 | 18 jours d'écoute sur 30, renouvellement actif... | 0 |
| A1 | 2016-03-21 | 9 jours d'écoute sur 30, renouvellement désactivé... | 1 |

Un même abonné apparaît donc sur de nombreuses lignes, une par lundi. Sur KKBox, la grille compte **410 523 lignes** pour 8 150 abonnés et 100 lundis.

### Pourquoi chaque semaine ?

Parce que c'est exactement la situation réelle : chaque lundi, l'équipe se demande qui appeler. Le modèle apprend sur des centaines de lundis passés, dans les mêmes conditions que celles où il sera utilisé.

## 3. Qui entre dans la grille ?

Une photo n'est prise que si elle a un sens. Un couple `(abonné, T0)` n'entre dans la grille que si quatre conditions sont réunies.

1. **L'abonné est encore actif à `T0`.** Prédire le départ d'un abonné déjà parti n'a pas de sens.
2. **Il a au moins 60 jours d'ancienneté.** Un compte trop récent n'a pas d'historique exploitable.
3. **L'historique couvre au moins 90 jours**, la plus longue fenêtre de calcul. La grille commence donc 90 jours après le premier événement du journal.
4. **L'abonné a au moins un événement avant `T0`.** Sinon, il est inscrit mais pas encore client.

> **Dans les coulisses.** Les conditions 3 et 4 ont été ajoutées au lot 4, après une erreur. Sur KKBox, les inscriptions remontent à 2004, alors que les transactions ne commencent qu'en 2015. La grille partait donc de 2004 : dix ans de lundis où aucun départ ne pouvait être observé, soit 56 % des lignes. Résultat : les données d'apprentissage ne contenaient **aucun** exemple de départ, et le modèle simple produisait des scores constants. Le chiffre obtenu était faux. C'est la décision D17.

## 4. La cible, et le cas des réponses inconnues

La cible vaut 1 si le départ tombe **après `T0` et au plus tard 30 jours après**. Sinon, elle vaut 0.

Mais souvenez-vous de Chloé, dans l'exercice du chapitre 5. Pour un lundi trop proche de la fin des données, les 30 jours suivants ne sont pas encore connus. La réponse n'est pas 0, elle est **inconnue**.

**Règle :** une ligne dont la fenêtre de 30 jours dépasse la fin de l'historique est **écartée**, jamais comptée à 0.

> **Attention.** Compter ces lignes à 0 revient à affirmer que l'abonné est resté, alors que personne ne le sait. L'erreur toucherait toujours les semaines les plus récentes, celles sur lesquelles on juge un modèle. C'est un biais invisible et systématique.

## 5. Les variables : résumer le passé sur des fenêtres

### Des fenêtres de 7, 30 et 90 jours

Pour chaque ligne, on résume ce qui s'est passé **juste avant `T0`**, sur trois durées : les 7, les 30 et les 90 derniers jours. On appelle ces durées des **fenêtres**.

Pour chaque type d'événement et chaque fenêtre, on calcule deux choses :

- un **comptage** : combien de fois l'événement s'est produit, par exemple 21 jours d'écoute ;
- une **somme** : le total de la valeur associée, par exemple 1 250 minutes d'écoute.

### Des variables d'évolution

Un niveau décrit un abonné. Une **rupture** décrit un risque. Un abonné qui écoute 10 jours par mois depuis toujours n'est pas dans la même situation qu'un abonné qui passe de 25 à 10 jours.

On calcule donc aussi des **variables de tendance**, qui comparent une fenêtre à la précédente : les 30 derniers jours face aux 30 jours d'avant.

```text
tendance = (valeur récente + 1) / (valeur précédente + 1)
```

Une tendance de 1 signifie « rien n'a changé ». Inférieure à 1, l'activité baisse. Le « + 1 » évite une division par zéro quand une fenêtre est vide.

Au total, le projet produit 86 variables sur KKBox.

## 6. La règle d'or : strictement avant `T0`

> **À retenir.** Une variable calculée pour la ligne `(abonné, T0)` n'utilise que des événements **strictement antérieurs** à `T0`. Pas le jour même. Pas une seconde après.

### Qu'est-ce qu'une fuite d'information ?

Une **fuite d'information** se produit quand le modèle apprend avec une donnée qu'il n'aurait pas eue au moment de décider. Le modèle paraît excellent pendant l'évaluation, puis s'effondre en situation réelle, parce que l'information dont il dépendait n'existe plus.

Exemples de fuites que la règle interdit :

- utiliser la date de départ pour calculer une variable, même indirectement, comme une durée d'abonnement totale ;
- compter un événement survenu le lundi même, à `T0` ;
- calculer une moyenne sur tout le tableau, futur compris, pour normaliser les données ;
- lire dans la table des comptes une valeur qui décrit l'abonné **aujourd'hui** plutôt qu'à `T0`. Le chapitre 8 raconte comment ce piège a été découvert.

## 7. Calculer vite : l'astuce du compteur kilométrique

### Le problème

La grille compte 410 523 lignes, et chacune demande des dizaines de calculs sur des fenêtres différentes. Parcourir le journal pour chaque ligne et chaque fenêtre prendrait des heures.

### L'astuce

Pensez au **compteur kilométrique** d'une voiture. Pour savoir combien de kilomètres vous avez parcourus entre lundi et vendredi, inutile de refaire le trajet : vous lisez le compteur vendredi, vous soustrayez la lecture de lundi.

Le projet fait pareil :

1. pour chaque abonné, il calcule une fois pour toutes un **cumul** : le nombre total d'événements depuis le début, à chaque instant ;
2. pour une fenêtre `[T0 - 30 jours, T0[`, il lit ce cumul juste avant `T0`, puis juste avant `T0 - 30 jours` ;
3. la différence donne le nombre d'événements dans la fenêtre.

La lecture « juste avant une date » se fait avec une fonction de pandas appelée `merge_asof`, qui retrouve pour chaque ligne la dernière valeur connue avant une date donnée.

### Trois pièges qui ne préviennent pas

Cette méthode est rapide, mais une mesure faite avant le lot 3, sur 2 millions d'événements, a révélé trois pièges. Chacun produit des résultats faux **sans aucun message d'erreur**.

| Piège | Ce qui se passe | Parade |
| :--- | :--- | :--- |
| Précisions de dates différentes | pandas gère plusieurs précisions, à la microseconde ou à la nanoseconde, et refuse de les mélanger | Une précision unique, imposée à la lecture des données |
| Lignes remises dans le désordre | `merge_asof` réordonne le résultat, et les valeurs se retrouvent attachées aux mauvaises lignes | Une colonne qui retient l'ordre d'origine, pour tout remettre en place |
| Plusieurs événements au même instant | La fonction peut retenir un cumul intermédiaire au lieu du cumul final | Regrouper d'abord les événements d'un même instant |

Le troisième piège, à lui seul, produisait **10,5 % de lignes fausses**. Aucun total, aucune moyenne, aucune taille de tableau ne le trahissait : les chiffres restaient plausibles, et une ligne sur dix était simplement fausse.

## 8. Deux tests pour dormir tranquille

### La sentinelle anti-fuite

Comment prouver qu'aucune variable ne regarde le futur ? Par une expérience simple.

1. On calcule les variables pour une série de lignes `(abonné, T0)`, avec le journal complet.
2. On **supprime du journal tout ce qui arrive à partir de `T0`**.
3. On recalcule les mêmes variables.
4. Les deux résultats doivent être **strictement identiques**.

Si une seule valeur change, c'est qu'elle dépendait d'un événement du futur. Le test échoue, et la construction est fausse. Ce test, `tests/test_no_leakage.py`, vérifie des centaines de lignes à chaque exécution.

> **Attention.** Si ce test échoue un jour, on ne le modifie pas pour le faire passer. C'est le calcul qui est cassé, pas la sentinelle.

La sentinelle a une limite, découverte au lot 5 : elle coupe le journal, mais ne touche pas à la table des comptes. Un second test la complète désormais. Le chapitre 8 raconte pourquoi.

### Le contrôle par force brute

La sentinelle prouve qu'on ne regarde pas le futur. Elle ne prouve pas que le calcul est **juste**.

Le contrôle par force brute recalcule chaque variable de la façon la plus naïve possible : pour 250 lignes tirées au hasard, il parcourt les événements de l'abonné un par un et compte ceux qui tombent dans la fenêtre. Lent, mais impossible à rater. Le résultat doit correspondre exactement au calcul rapide.

C'est le seul contrôle qui aurait détecté les 10,5 % de lignes fausses. Il se trouve dans `tests/test_windows_bruteforce.py`.

---

## À vous de jouer

**Contexte.** On observe l'abonné A1 le lundi **14 mars à 00:00**, donc `T0` = 14 mars. Voici ses connexions :

| Date et heure | Événement |
| :--- | :--- |
| 5 mars, 10:00 | connexion |
| 7 mars, 00:00 | connexion |
| 9 mars, 18:00 | connexion |
| 13 mars, 23:30 | connexion |
| 14 mars, 00:00 | connexion |
| 15 mars, 09:00 | connexion |

**Questions.**

1. La fenêtre de 7 jours est `[T0 - 7 jours, T0[`, soit du 7 mars 00:00 inclus au 14 mars 00:00 exclu. Combien de connexions compte-t-elle ?
2. Pourquoi la connexion du 14 mars à 00:00 n'est-elle pas comptée ?
3. Un collègue propose de compter aussi celle du 15 mars, « puisqu'on a l'information ». Que lui répondez-vous ?

<details>
<summary>Voir la correction</summary>

1. **3 connexions** : le 7 mars à 00:00, borne incluse, le 9 mars et le 13 mars. Celle du 5 mars est avant la fenêtre.

2. **Parce que la borne de fin est exclue.** La règle impose « strictement avant `T0` ». Un événement du lundi même, à `T0`, n'était pas connu au moment de la décision. C'est la forme de fuite la plus subtile : une seule seconde suffit.

3. **C'est une fuite d'information.** Le 14 mars, jour où l'équipe prépare sa liste, la connexion du 15 mars n'existe pas encore. Un modèle entraîné avec elle apprendrait à s'appuyer sur des informations indisponibles en situation réelle, et paraîtrait bien meilleur qu'il ne l'est. La sentinelle anti-fuite détecterait immédiatement cette erreur.

</details>

---

## En résumé

- Le **tableau d'apprentissage** est une **grille** de couples `(abonné, T0)` : une photo de chaque abonné chaque lundi. 410 523 lignes sur KKBox.
- Quatre conditions décident qui entre dans la grille, dont deux ajoutées après une erreur mesurée, la décision D17.
- La **cible** vaut 1 si l'abonné part dans les 30 jours. Une ligne dont la réponse est **inconnue** est écartée, jamais comptée à 0.
- Les **variables** résument le passé sur des **fenêtres** de 7, 30 et 90 jours, avec des **tendances** qui captent les ruptures.
- **Règle d'or** : uniquement des événements **strictement antérieurs à `T0`**. Toute exception est une **fuite d'information**.
- Le calcul rapide par **cumul**, comme un compteur kilométrique, cache trois pièges silencieux, dont un produisait 10,5 % de lignes fausses.
- La **sentinelle anti-fuite** prouve qu'on ne regarde pas le futur. Le **contrôle par force brute** prouve que le calcul est juste.

**Chapitre précédent :** [5. Les vraies données et la cible](05-donnees-kkbox-et-cible.md) · **Suite :** [Quiz de la partie 2](quiz-partie-2.md), puis [7. Évaluer honnêtement](07-evaluer-honnetement.md)
