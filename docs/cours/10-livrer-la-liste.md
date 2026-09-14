# Chapitre 10. Livrer la liste du lundi : l'export

> **Partie 4, restituer les résultats** · Lecture : 30 minutes · Prérequis : partie 3

## Ce que vous allez apprendre

À la fin de ce chapitre, vous saurez :

- expliquer ce qu'est un traitement **par lots** et ce que produit la commande de scoring ;
- lire chaque colonne de la liste livrée à l'équipe ;
- justifier pourquoi seuls les motifs **actionnables** sont affichés ;
- rendre un calcul **déterministe**, pour que deux exécutions produisent exactement les mêmes fichiers ;
- choisir le bon format de fichier, et éviter les pièges d'Excel.

---

## 1. Du modèle à la liste

Jusqu'ici, le modèle a été entraîné et évalué sur le passé. Il reste à s'en servir : **chaque lundi**, classer les abonnés actuels et livrer la liste à l'équipe.

Ce calcul est un **traitement par lots**, en anglais *batch* : une commande lancée à intervalle régulier, qui traite toutes les données d'un coup, puis s'arrête. Rien ne tourne en permanence, aucun serveur n'attend de requête.

```bash
uv run python -m churn.pipeline.run_scoring --source kkbox
```

Cette commande :

1. charge les données de la source ;
2. recharge le **dernier modèle sauvegardé** pour cette source ;
3. retient les abonnés éligibles à la date de scoring ;
4. calcule leurs variables, leur score et leurs motifs ;
5. écrit la liste dans trois fichiers.

Sur KKBox, elle a scoré **5 093 abonnés** au lundi 27 mars 2017, dernière date que permettent les données, en 25 secondes.

> **Attention.** Les chiffres de ce chapitre sont ceux du lot 6, avec le premier modèle. Depuis la correction racontée au chapitre 7, décision D24, la liste du 27 mars compte **5 165 abonnés** : les 72 de plus sont des abonnés dont le départ n'est pas encore constaté. Le détail de la liste actuelle figure dans `docs/resultats.md`.

> **Attention.** La commande refuse d'utiliser un modèle entraîné sur une autre source. Un modèle appris sur les données fictives du chapitre 4 produirait, sur les vrais abonnés, une liste d'apparence sérieuse et sans aucune valeur.

## 2. Scorer un jour où personne ne connaît la fin

### Un problème caché

Souvenez-vous du chapitre 6 : le tableau d'apprentissage **écarte** les lundis trop récents, ceux dont on ne connaît pas encore les 30 jours suivants. C'est indispensable pour apprendre, puisque la réponse est inconnue.

Mais le jour du scoring, c'est exactement la situation : **personne ne connaît la suite**. On ne peut donc pas réutiliser le tableau d'apprentissage tel quel. Il aurait écarté précisément les abonnés qu'on veut classer.

### La solution : séparer les règles

Les règles d'entrée dans la grille ont été séparées en deux groupes :

- les règles **d'éligibilité**, communes à l'apprentissage et au scoring : abonné actif, au moins 60 jours d'ancienneté, déjà observé avant la date ;
- la règle **d'issue connue**, réservée à l'apprentissage.

Et surtout, les variables du scoring sont calculées par **la même fonction** que celles de l'apprentissage.

> **À retenir.** Un modèle ne doit jamais voir, le jour où il sert, des données calculées autrement que celles dont il a appris. Cet écart entre entraînement et utilisation réelle est une cause classique de modèles qui déçoivent en production. Un test le surveille : sur une date commune, les variables du scoring et celles de l'apprentissage doivent être strictement identiques.

## 3. Lire la liste

Chaque ligne de la liste décrit un abonné. Voici les douze colonnes, dans leur ordre :

| Colonne | Ce qu'elle dit |
| :--- | :--- |
| `batch_run_id` | L'identifiant de l'exécution qui a produit la liste |
| `date_scoring` | Le lundi de la liste |
| `client_id` | L'abonné |
| `rang_priorite` | L'ordre d'appel : 1, puis 2, puis 3... |
| `decile_risque` | Le groupe de risque, de 1, le plus risqué, à 10 |
| `is_top_k` | Vrai pour les 50 premiers, ceux que l'équipe appelle cette semaine |
| `mrr` | Le revenu mensuel en vigueur à la date, pour arbitrer entre deux abonnés proches |
| `facteur_risque_1` à `3` | Jusqu'à trois motifs lisibles |
| `score_brut_technique` | Le score du modèle, réservé au diagnostic |
| `model_version` | La version du modèle utilisé |

Trois précisions.

- **Les déciles sont équilibrés.** Sur les 5 093 abonnés, chaque décile en compte 509 ou 510.
- **Le score n'est pas un pourcentage.** Il est rangé dans une colonne technique, dont le nom le dit. Le métier lit le rang et le décile.
- **Un revenu de zéro signifie « inconnu ».** C'est le cas de 24 % des abonnés de la liste, pour la raison expliquée au chapitre 8 : l'extrait KKBox ne remonte pas avant 2015.

## 4. Des motifs sur lesquels agir

### Le constat

Au chapitre 9, le premier abonné de la liste affichait comme premier motif « [GENERAL] Revenu mensuel en vigueur ». Que peut en faire un conseiller ? Rien. On n'agit ni sur l'ancienneté d'un abonné, ni sur le prix de son forfait pour le retenir.

### La règle

**Seules les variables dont le libellé propose une action peuvent occuper une case de motif.** Dans le dictionnaire des libellés, les variables structurelles comme le revenu et l'ancienneté ont une action vide : elles sont exclues des cases. Elles continuent en revanche de compter dans le score. C'est la décision D19.

### L'effet mesuré

Sur les 5 093 abonnés du 27 mars 2017 :

| | Sans la règle | Avec la règle |
| :--- | ---: | ---: |
| Abonnés dont le premier motif est structurel | 2,6 % | 0 % |
| Abonnés avec au moins un motif structurel | 6,2 % | 0 % |
| Abonnés sans aucun motif | 26,2 % | 27,5 % |

La part d'abonnés sans motif augmente un peu : ce sont ceux dont les seuls signaux nets étaient structurels. Leur case reste vide plutôt que d'afficher une information inutile.

En tête de liste, le résultat est net : sur les 50 abonnés à appeler, **48 ont trois motifs et 2 en ont deux**. Voici les trois premiers :

| Rang | Motif 1 | Motif 2 | Motif 3 |
| ---: | :--- | :--- | :--- |
| 1 | [FINANCE] Évolution récente des annulations d'abonnement | [FINANCE] Annulations d'abonnement | [PRODUCT] Fréquence d'usage |
| 2 | [FINANCE] Évolution récente de la facturation | [FINANCE] Évolution récente des annulations d'abonnement | [FINANCE] Annulations d'abonnement |
| 3 | [FINANCE] Évolution récente de la facturation | [FINANCE] Évolution récente des annulations d'abonnement | [FINANCE] Annulations d'abonnement |

## 5. Deux exécutions, les mêmes fichiers

### Pourquoi c'est important

Imaginez qu'un responsable demande dans trois mois : « pourquoi Mme X était-elle en tête de liste le 27 mars ? ». Pour répondre, il faut pouvoir **reproduire exactement** la liste. Un calcul qui donne le même résultat chaque fois qu'on le relance sur les mêmes données est dit **déterministe**.

C'était un critère d'acceptation du lot : deux exécutions sur les mêmes données doivent produire des fichiers identiques, octet par octet.

### Le piège de l'identifiant

Chaque ligne porte un identifiant d'exécution, `batch_run_id`. C'est un **UUID**, un identifiant de 36 caractères conçu pour ne jamais se répéter. La façon habituelle d'en créer un est de le tirer au hasard. Mais alors, deux exécutions produisent deux identifiants différents, donc deux fichiers différents.

La solution : **dériver** l'identifiant de ce dont l'exécution dépend. Il est calculé à partir de la version du modèle, de la date de scoring et d'une empreinte des données scorées. Mêmes entrées, même identifiant. La moindre différence, un autre identifiant. On garde ainsi la traçabilité sans perdre la reproductibilité. C'est la décision D20.

### Les autres sources de variation

D'autres détails peuvent changer un fichier sans changer son contenu apparent :

- **l'ordre des égalités** : deux abonnés au même score sont départagés par le revenu, puis par l'identifiant ;
- **les fins de ligne** : Windows et Linux ne terminent pas les lignes d'un fichier texte de la même façon. Le projet les fixe explicitement.

### La vérification

On a lancé deux fois le scoring KKBox, puis calculé l'**empreinte SHA-256** de chaque fichier : une signature de 64 caractères qui change si un seul octet change. Les empreintes des trois fichiers sont **identiques** entre les deux exécutions.

## 6. Trois formats pour trois publics

| Format | Pour qui | Pourquoi |
| :--- | :--- | :--- |
| **Parquet** | Les programmes, dont l'interface web du lot 7 | La **source de vérité** : types conservés, compression, et l'identité du lot rangée dans les métadonnées du fichier |
| **CSV** | Un conseiller qui ouvre un tableur | Lisible partout, sans outil particulier |
| **JSON** | Une éventuelle interface web dédiée | Le format natif du web, qui porte l'identité du lot suivie des lignes |

Les trois fichiers sont rangés par source, dans `data/exports/kkbox/` ou `data/exports/synthetic/`. Une liste fictive ne peut pas se retrouver à côté d'une liste réelle.

### Les pièges d'Excel

Un CSV semble simple. Il cache pourtant trois pièges qui rendent un fichier illisible pour un utilisateur français.

1. **Les accents.** Le fichier est écrit en UTF-8, l'**encodage** moderne qui gère tous les caractères. Mais Excel sous Windows ne le reconnaît pas toujours, et affiche « Ã‰volution » au lieu de « Évolution ». La parade : ajouter au début du fichier une **marque d'ordre des octets**, trois octets invisibles qui annoncent l'UTF-8. D'où l'encodage `utf-8-sig`.
2. **Le séparateur de colonnes.** Excel en français attend un point-virgule. Avec une virgule, tout s'entasse dans la première colonne.
3. **Le séparateur décimal.** En français, on écrit `0,81` et non `0.81`. Avec un point, Excel risque de lire le nombre comme du texte.

Ces trois réglages viennent du fichier de configuration. La configuration refuse d'ailleurs un séparateur décimal identique au séparateur de colonnes : un nombre serait coupé en deux.

> **Dans les coulisses.** Le critère d'acceptation exigeait une vérification dans le vrai logiciel. Le fichier KKBox a donc été ouvert dans Excel, sous Windows en français, comme par un double-clic : 12 colonnes, 5 094 lignes avec l'en-tête, des revenus et des scores reconnus comme des nombres, et « Évolution récente des annulations d'abonnement » correctement accentué.

> **Attention.** Ces réglages visent un Excel en français. Sur un ordinateur réglé en anglais, un double-clic entasserait tout dans une colonne. Il faudrait alors importer le fichier en précisant le séparateur, ou adapter la configuration. C'est une limite connue, pas un oubli.

## 7. Ajouter une destination sans rien casser

Parquet, CSV et JSON sont trois **destinations**. Demain, on voudra peut-être envoyer la liste par courriel, ou la déposer dans un logiciel de gestion client.

Pensez à une prise USB. L'ordinateur ne sait pas s'il y branche une souris, une clé ou un clavier : il sait seulement que l'appareil respecte la norme USB. Ici, la norme s'appelle `Sink` et tient en une ligne : une destination sait **écrire une liste dans un dossier**. Le pipeline accepte n'importe quelle destination qui respecte cette norme.

Un test le prouve : il définit une destination fictive, qui n'existe que dans le test, et la passe au pipeline. Rien d'autre dans le code n'a besoin de changer. Et chaque destination a une règle stricte : elle **écrit**, elle ne **transforme** jamais une valeur. Tout le calcul, rangs, déciles et motifs, a lieu avant.

---

## À vous de jouer

**Contexte.** Une petite équipe appelle **2 abonnés** par semaine. Voici les scores de cinq abonnés un lundi.

| Abonné | Score | Revenu |
| :--- | ---: | ---: |
| A | 0,62 | 99 |
| B | 0,80 | 149 |
| C | 0,62 | 149 |
| D | 0,15 | 180 |
| E | 0,62 | 149 |

**Questions.**

1. Classez les abonnés selon la règle : score décroissant, puis revenu décroissant, puis identifiant croissant. Donnez leur rang, et dites lesquels sont appelés cette semaine.
2. Avec la formule du projet, le décile d'un rang vaut `rang × 10 ÷ nombre d'abonnés`, arrondi à l'entier supérieur. Calculez le décile de chacun. Que remarquez-vous ?
3. Pour l'abonné B, les contributions significatives, au-dessus du seuil de 0,20, sont : ancienneté +0,90, renouvellement automatique +0,50, fréquence d'usage +0,30, revenu +0,25. Quels motifs affiche l'export ?
4. Un collègue propose de tirer `batch_run_id` au hasard, « pour être sûr qu'il soit unique ». Quel critère du projet cela casse-t-il ?

<details>
<summary>Voir la correction</summary>

1. **B est premier**, avec le meilleur score. Viennent ensuite les trois abonnés à 0,62, départagés par le revenu : C et E à 149, puis A à 99. C et E sont encore à égalité, l'identifiant les départage : C avant E. **D est dernier.** Rangs : B 1, C 2, E 3, A 4, D 5. **B et C sont appelés.**

2. **Déciles : B 2, C 4, E 6, A 8, D 10.** Avec seulement cinq abonnés, chaque abonné occupe deux déciles à lui seul, et certains déciles restent vides. Les déciles n'ont de sens que sur un nombre suffisant d'abonnés. Sur KKBox, chacun en compte environ 509.

3. **« Renouvellement automatique » puis « Fréquence d'usage », et une troisième case vide.** L'ancienneté et le revenu sont des variables structurelles, sans levier d'action : ils comptent dans le score, mais n'occupent pas de case, décision D19. Il ne reste que deux motifs actionnables au-dessus du seuil, et la troisième case reste vide plutôt que d'afficher un motif inutile.

4. **La reproductibilité.** Deux exécutions sur les mêmes données donneraient deux identifiants différents, donc deux fichiers différents. Un identifiant dérivé des entrées reste unique pour chaque lot réel, puisque la moindre différence de modèle, de date ou de données en change la valeur, tout en restant identique quand rien n'a changé.

</details>

---

## En résumé

- Le scoring est un **traitement par lots** : une commande hebdomadaire qui recharge le dernier modèle, classe les abonnés éligibles et écrit la liste.
- Le jour du scoring, l'issue est inconnue : les règles d'**éligibilité** et le calcul des **variables** sont partagés avec l'apprentissage, seule la règle d'issue connue en est retirée.
- La liste porte le **rang**, le **décile**, les **50 appels** de la semaine, jusqu'à **trois motifs**, et de quoi **retrouver** l'exécution et le modèle.
- Seuls les **motifs actionnables** occupent une case, décision D19.
- L'export est **déterministe** : un identifiant dérivé des entrées, des égalités et des fins de ligne fixées. Vérifié par empreintes identiques sur KKBox.
- **Parquet** est la source de vérité, **CSV** sert le tableur, **JSON** prépare une interface dédiée. Le CSV est réglé pour **Excel en français**, et vérifié dans Excel.
- Une nouvelle **destination** s'ajoute sans modifier le reste du pipeline.

**Chapitre précédent :** [9. Expliquer chaque prédiction](09-expliquer-les-predictions.md) · **Retour au** [sommaire du cours](README.md)
