# Chapitre 9. Expliquer chaque prédiction

> **Partie 3, mesurer et prédire** · Lecture : 30 minutes · Prérequis : chapitre 8

## Ce que vous allez apprendre

À la fin de ce chapitre, vous saurez :

- expliquer l'idée des **valeurs de Shapley** avec une analogie simple ;
- transformer les contributions d'un modèle en trois motifs lisibles par abonné ;
- expliquer pourquoi un motif peut rester vide, et pourquoi c'est une bonne chose ;
- décrire comment un modèle est sauvegardé pour pouvoir être retrouvé à l'identique.

---

## 1. Pourquoi expliquer

Un score dit **qui** appeler. Il ne dit pas **quoi dire**. Imaginez un conseiller qui appelle un abonné classé premier, sans savoir pourquoi : il improvise, et l'appel risque d'être inutile.

Deux sortes d'explications existent :

- l'**explication globale** : quelles variables comptent le plus en général, pour tous les abonnés ;
- l'**explication locale** : pourquoi **cet abonné-là** est jugé à risque.

Pour un conseiller, seule la seconde est utile. Savoir que « l'ancienneté compte beaucoup en général » ne l'aide en rien face au client X. Le projet produit donc des explications **locales**, jusqu'à trois motifs par abonné.

## 2. L'idée des valeurs de Shapley

### Le partage de l'addition

Pensez à un repas entre amis. L'addition totale dépasse le prix moyen d'un repas, parce que certains ont pris un dessert, d'autres une bouteille. Pour partager équitablement, on cherche ce que chacun a ajouté.

Le modèle fonctionne de la même façon.

- Il part d'un **score moyen**, identique pour tout le monde.
- Pour un abonné donné, chaque variable pousse le score **vers le haut** ou **vers le bas**.
- Les **valeurs de Shapley** répartissent l'écart entre le score de l'abonné et le score moyen, de façon équitable, entre toutes les variables.

Leur somme, ajoutée au score moyen, redonne exactement le score de l'abonné.

Exemple simplifié :

| | Contribution |
| :--- | ---: |
| Score moyen de départ | -3,9 |
| Renouvellement automatique désactivé | +1,2 |
| Peu de jours d'écoute ce mois-ci | +0,8 |
| Ancienneté élevée | -0,3 |
| **Score de l'abonné** | **-2,2** |

Ici, deux variables poussent le risque vers le haut, une le fait baisser. Les valeurs sont exprimées sur l'échelle interne du modèle, ce qui explique les nombres négatifs : seul leur signe et leur taille comptent pour notre usage.

### Le calcul dans le projet

XGBoost calcule ces contributions lui-même, grâce à l'option `pred_contribs=True`. Le tableau obtenu contient une colonne de plus que le nombre de variables : la dernière est le **biais**, c'est-à-dire le score moyen commun à tous.

Le biais n'appartient à aucune variable. S'il restait dans le classement, le même « motif » apparaîtrait chez tout le monde. Il est donc **retiré**, et un test vérifie deux choses : que cette colonne est bien identique sur toutes les lignes, et que la somme des contributions retombe exactement sur le score brut du modèle.

## 3. Des contributions aux motifs

### Étape 1 : additionner par variable d'origine

Le nombre de jours d'écoute existe en plusieurs exemplaires : sur 7, 30 et 90 jours, en comptage et en somme. Ce sont plusieurs colonnes, mais **une seule raison**. Si on les classait séparément, le conseiller lirait trois fois « fréquence d'usage ».

Les contributions sont donc additionnées par **variable d'origine** avant tout classement. C'est la décision D7.

| Colonne | Contribution | Variable d'origine |
| :--- | ---: | :--- |
| `count_connexion_7j` | +0,10 | `connexion` |
| `sum_connexion_30j` | +0,05 | `connexion` |
| `trend_count_connexion_30j` | +0,20 | `trend_connexion` |

Résultat : `connexion` contribue +0,15, et `trend_connexion` +0,20. Une tendance reste à part, parce qu'un niveau bas et une chute récente sont deux motifs d'appel différents.

### Étape 2 : ne garder que ce qui pousse vers le risque

Seules les contributions **positives**, celles qui augmentent le risque, peuvent devenir un motif. Une variable qui rassure n'est pas une raison d'appeler.

### Étape 3 : ne garder que ce qui est significatif

Une contribution minuscule n'est pas un motif sérieux. Elle doit dépasser un **seuil de signification**.

Ce seuil est calculé pendant l'entraînement : c'est le **75e centile** des contributions en valeur absolue, c'est-à-dire la valeur en dessous de laquelle se trouvent les trois quarts des contributions. Sur KKBox, il vaut 0,1627. Il est enregistré avec le modèle, et **jamais écrit à la main dans le code**.

### Étape 4 : garder les trois plus fortes

Parmi les contributions positives et significatives, on garde les trois plus fortes. En cas d'égalité, l'ordre alphabétique départage, pour que deux exécutions donnent toujours les mêmes motifs.

## 4. Quand il n'y a rien à dire

Un abonné sans aucune contribution au-dessus du seuil reçoit des motifs **vides**.

> **À retenir.** Un motif inventé est pire qu'un motif absent. Un conseiller qui lit une fausse raison peut orienter tout son appel dans la mauvaise direction.

Sur les 5 074 abonnés de la dernière semaine observée :

| Motifs significatifs | Part des abonnés |
| :--- | ---: |
| Aucun | 26 % |
| Un | 48 % |
| Deux | 18 % |
| Trois | 8 % |

Les abonnés les plus à risque ont presque toujours un motif net : **aucun** des 50 premiers n'en manque. Parmi les 50 derniers de la liste, 36 % n'en ont pas. C'est logique : rien ne les pousse vers le risque.

## 5. Des libellés qui ne mentent pas

### Un dictionnaire, pas un modèle de langage

Chaque variable d'origine a un libellé métier, écrit dans `config/feature_mapping.yaml` :

```yaml
connexion:
  label: "Fréquence d'usage"
  source: "PRODUCT"
  action: "Vérifier si l'usage du service a changé"
```

Le motif affiché devient `[PRODUCT] Fréquence d'usage`. Ce dictionnaire donne toujours le même libellé, et un test vérifie qu'aucune variable du modèle n'en manque. Si une variable n'a pas de libellé, l'**entraînement échoue** : un motif ne s'affiche jamais sous un nom technique comme `trend_count_connexion_30j`.

### Nommer le signal, pas deviner son sens

Les libellés sont **neutres**. On écrit « Fréquence d'usage », pas « Chute de l'usage ».

Pourquoi ? Une contribution positive dit que la **valeur** de la variable pousse le risque vers le haut. Elle ne dit pas si cette valeur est haute ou basse. Pour un abonné, c'est peut-être une écoute en baisse ; pour un autre, une écoute inhabituelle. Écrire « chute » serait une supposition. Déduire le sens à partir de la valeur elle-même est une amélioration prévue plus tard.

### Un exemple réel

Voici les motifs de trois des premiers abonnés de la dernière semaine observée :

| Rang | Motif 1 | Motif 2 | Motif 3 |
| ---: | :--- | :--- | :--- |
| 1 | [GENERAL] Revenu mensuel en vigueur | [FINANCE] Statut du renouvellement automatique | [FINANCE] Évolution récente du renouvellement automatique |
| 2 | [FINANCE] Évolution récente de la facturation | [FINANCE] Statut du renouvellement automatique | [FINANCE] Facturation |
| 4 | [FINANCE] Annulations d'abonnement | [FINANCE] Évolution récente de la facturation | [GENERAL] Ancienneté du compte |

Deux remarques honnêtes.

- **Cette liste est « en échantillon ».** Le modèle final a été entraîné sur toute la grille, y compris ces lignes. Elle montre la **forme** de l'explication, elle ne mesure pas la performance. La performance se lit dans les plis du chapitre 8.
- **Les motifs `[GENERAL]` n'offrent aucun levier.** On ne peut rien faire contre l'ancienneté ou le revenu d'un abonné. La prochaine étape, l'export des listes, n'affichera que des motifs sur lesquels un conseiller peut agir.

## 6. Sauvegarder un modèle qu'on peut retrouver

Un fichier de résultats voyage sans le modèle qui l'a produit. Des mois plus tard, quelqu'un demandera : « avec quel modèle cette liste a-t-elle été faite ? ». Le projet enregistre donc chaque modèle avec une **fiche d'identité**, `metadata.json` :

- une **version**, calculée à partir des données, des réglages et de la graine. Deux entraînements identiques donnent la même version. Sur KKBox : `0.1.0-b8f55da1e566` ;
- l'**empreinte** des données d'entraînement : une signature, calculée à partir de toutes les valeurs, qui change si une seule d'entre elles change ;
- les réglages retenus, la graine, le seuil de signification et la source des données.

Un test recharge le modèle et vérifie que ses scores sont **identiques au bit près**. C'est ce qui permettra de reproduire une liste des mois plus tard.

## 7. Les tests qui protègent les chapitres 8 et 9

| Test | Ce qu'il empêche |
| :--- | :--- |
| La table des comptes réécrite ne change rien | Qu'une valeur décrivant l'abonné aujourd'hui serve à apprendre |
| La sentinelle appliquée au revenu | Que le revenu lu à `T0` regarde le futur |
| Le revenu comparé à une lecture naïve | Une erreur de calcul silencieuse |
| La cible du test n'atteint aucun classement | Qu'un modèle lise la réponse |
| La sélection a lieu dans chaque pli | Que les réglages soient choisis sur le test |
| Les contributions d'une même variable s'additionnent | Qu'un motif apparaisse plusieurs fois |
| La colonne de biais est écartée | Qu'un même motif s'affiche chez tout le monde |
| Un abonné sans contribution significative reçoit des motifs vides | Un motif inventé |
| Une variable sans libellé fait échouer l'entraînement | Un nom technique affiché au métier |
| Le modèle rechargé donne les mêmes scores | Une liste impossible à reproduire |

---

## À vous de jouer

**Contexte.** Le seuil de signification vaut **0,20**. Voici les contributions déjà additionnées par variable d'origine pour deux abonnés.

| Variable d'origine | Abonné A | Abonné B |
| :--- | ---: | ---: |
| `annulation_abonnement` | +0,35 | +0,05 |
| `connexion` | +0,22 | -0,40 |
| `desactivation_renouvellement` | +0,60 | +0,12 |
| `facture_emise` | -0,10 | +0,18 |
| `trend_connexion` | +0,22 | +0,02 |

**Questions.**

1. Quels sont les motifs 1, 2 et 3 de l'abonné A ? Attention aux égalités.
2. Quels sont les motifs de l'abonné B ?
3. Pour B, un collègue propose d'afficher quand même `facture_emise`, « la plus forte des contributions positives ». Que lui répondez-vous ?
4. Pourquoi ne pas écrire « Baisse de la fréquence d'usage » comme libellé de `connexion` ?

<details>
<summary>Voir la correction</summary>

1. **A : `desactivation_renouvellement` (0,60), `annulation_abonnement` (0,35), puis `connexion` (0,22).** `connexion` et `trend_connexion` sont à égalité à 0,22 : l'ordre alphabétique départage, et `connexion` passe devant. Les trois dépassent le seuil de 0,20.

2. **B : aucun motif.** Aucune contribution ne dépasse 0,20. La plus forte, `facture_emise`, vaut 0,18. Les trois cases restent vides.

3. **Qu'afficher un motif sous le seuil, c'est en inventer un.** Une contribution de 0,18 est trop faible pour justifier un argument d'appel. Le seuil a été calculé à l'entraînement précisément pour éviter ces motifs peu fiables. Mieux vaut une case vide qu'une fausse piste.

4. **Parce que le sens n'est pas connu.** Une contribution positive dit que la valeur de `connexion` augmente le risque de cet abonné, pas qu'elle a baissé. Le libellé « Fréquence d'usage » nomme le signal sans prétendre en connaître le sens.

</details>

---

## En résumé

- Le conseiller a besoin d'une explication **locale** : pourquoi **cet** abonné est à risque.
- Les **valeurs de Shapley** répartissent équitablement l'écart entre le score d'un abonné et le score moyen entre ses variables. XGBoost les calcule lui-même ; la colonne de **biais** est retirée.
- Les contributions sont **additionnées par variable d'origine**, puis seules les **positives** et **significatives** sont gardées, trois au plus.
- Un abonné sans contribution significative reçoit des **motifs vides** : un motif inventé est pire qu'un motif absent.
- Les libellés viennent d'un **dictionnaire testé**, et restent **neutres** sur le sens du signal.
- Chaque modèle est sauvegardé avec sa **version**, l'**empreinte** de ses données et son **seuil**, et se recharge à l'identique.

**Chapitre précédent :** [8. Entraîner le modèle](08-entrainer-le-modele.md) · **Suite :** [Quiz de la partie 3](quiz-partie-3.md)
