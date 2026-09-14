# Chapitre 2. La méthode : construire un projet de data science pas à pas

> **Partie 1, découvrir le projet** · Lecture : 30 minutes · Prérequis : chapitre 1

## Ce que vous allez apprendre

À la fin de ce chapitre, vous saurez :

- expliquer pourquoi on cadre un projet avant d'écrire du code ;
- tenir un registre de décisions et en comprendre l'intérêt ;
- découper un projet en étapes vérifiables, avec des critères d'acceptation ;
- décrire le rôle des tests, de l'intégration continue et des pull requests ;
- appliquer le principe « mesurer plutôt que supposer ».

---

## 1. Cadrer avant de coder

### L'idée de départ

Tout a commencé par une phrase : *« Modèle de classification identifiant les clients à risque de résiliation, avec les trois variables les plus prédictives isolées pour l'équipe commerciale. Python, scikit-learn, Seaborn. »*

Une phrase comme celle-ci paraît claire. Elle cache pourtant des dizaines de questions. Qu'appelle-t-on « résiliation » ? À quel horizon ? Comment mesure-t-on qu'un modèle est bon ? Les « trois variables » sont-elles les mêmes pour tous les clients ? A-t-on seulement des données ?

**Cadrer**, c'est répondre à ces questions avant de construire. Un projet mal cadré produit souvent un outil techniquement correct, mais inutile.

### Une table ronde, puis une relecture critique

Pour cadrer, une discussion a d'abord été organisée entre six rôles simulés par des assistants d'intelligence artificielle : un chef de projet, un responsable produit, un développeur, un designer, un responsable technique et un responsable qualité. Cette table ronde a produit de bonnes idées, conservées dans le projet :

- mesurer la qualité des **premiers noms de la liste** plutôt que la capacité à détecter tous les départs, parce qu'une équipe saturée de fausses alertes finit par ignorer l'outil ;
- donner des motifs **propres à chaque client**, et non les variables importantes en général.

Mais sa conclusion, un cahier des charges technique, a ensuite été **relue de façon critique**. Cette relecture a trouvé sept défauts sérieux. En voici quatre, formulés simplement :

1. **Aucune séparation nette entre passé et futur** lors de l'évaluation, ce qui aurait donné un modèle excellent en test et médiocre en réalité.
2. **Aucune méthode simple de comparaison.** Sans point de repère, impossible de savoir si le modèle vaut son coût.
3. **Un score présenté comme un pourcentage**, alors qu'il ne s'interprète pas ainsi.
4. **Des versions de logiciels vieilles de deux ans.**

Et surtout, une question posée par le développeur dès le premier tour n'avait jamais reçu de réponse : **dispose-t-on de données ?** La réponse était non. Tout le plan de travail reposait donc sur un préalable inexistant.

> **À retenir.** Un cahier des charges se relit avec un œil critique. Une question restée sans réponse est un risque, même quand tout le monde semble d'accord.

## 2. Écrire les décisions

### Le registre des décisions

Chaque choix important du projet est consigné dans un fichier, `docs/decisions.md`. Chaque décision porte un numéro, une date, un statut et surtout un **motif**. Le projet en compte vingt-quatre à ce jour, de D1 à D24.

Par exemple, la décision D4 dit : *« Le découpage entre apprentissage et test est strictement chronologique, avec une période tampon au moins égale à l'horizon de prédiction. »* Suit l'explication de ce qui arriverait sans elle.

### Pourquoi c'est utile

- **On ne rediscute pas sans fin.** Une décision close s'applique. Pour la changer, on la révise explicitement, par écrit.
- **On se souvient du pourquoi.** Trois semaines plus tard, un choix qui paraît étrange a toujours sa justification sous les yeux.
- **On peut l'expliquer à d'autres.** En entretien, dire « j'ai choisi pandas plutôt que polars après avoir mesuré les deux, et voici les chiffres » vaut bien plus que « j'utilise pandas ».

Une décision peut être révisée. La décision D1 prévoyait de tout construire sur des données fictives. Quand le projet est devenu un projet de portfolio, la décision D14 l'a révisée : les données réelles de KKBox portent la démonstration, les données fictives ne servent plus qu'aux tests. La trace des deux reste visible.

## 3. Commencer par le format des données

Avant d'écrire le moindre calcul, le projet a défini le **contrat de données** : la forme exacte que doivent avoir les données en entrée. Quelles tables, quelles colonnes, quels types, quelles règles.

Pensez aux plans d'une maison : on ne coule pas les fondations avant d'avoir décidé où passent les murs. Ici, grâce au contrat, peu importe d'où viennent les données. Les données fictives et les données KKBox sont toutes deux converties dans ce même format, et tout le reste de l'application fonctionne sans savoir laquelle des deux il traite. Le chapitre 4 détaille ce contrat.

## 4. Découper en lots

### Des étapes qui s'enchaînent

Le projet est découpé en neuf **lots**. Un lot est une étape cohérente, livrée et vérifiée avant de passer à la suivante. Chaque lot utilise le résultat du précédent.

| Lot | Objectif |
| ---: | :--- |
| 0 | Poser le socle : environnement, configuration, contrôles automatiques |
| 1 | Définir le format des données et générer des données fictives de test |
| 2 | Convertir les données KKBox et reconstruire l'étiquette « parti ou resté » |
| 3 | Construire le tableau d'apprentissage sans fuite d'information |
| 4 | Fixer la façon d'évaluer, et mesurer des méthodes simples |
| 5 | Entraîner le modèle et expliquer ses prédictions |
| 6 | Exporter les listes dans des fichiers |
| 7 | Construire l'interface web |
| 8 | Rédiger la présentation du projet |

L'ordre compte. Par exemple, la façon d'évaluer est fixée au lot 4, **avant** le modèle du lot 5. Une méthode d'évaluation construite après avoir vu les résultats d'un modèle a tendance à se plier à ces résultats.

### Des critères d'acceptation

Un lot n'est terminé que si ses **critères d'acceptation** sont tous vérifiés. Ce sont des conditions précises et vérifiables, écrites à l'avance dans `docs/roadmap.md`. Deux exemples réels :

- lot 2 : *« la cible reconstruite est comparée à l'étiquette officielle, et le taux de concordance est consigné »* ;
- lot 5 : *« le rechargement d'un modèle sauvegardé produit exactement les mêmes scores »*.

Un critère vague comme « le modèle doit être bon » ne se vérifie pas. Un critère précis, si.

## 5. Des filets de sécurité automatiques

### Les tests

Un **test** est un petit programme qui vérifie qu'un morceau du code donne le bon résultat. Par exemple, pour la fonction qui calcule la précision d'une liste, on construit à la main un cas dont on connaît la réponse :

```python
def test_precision_sur_un_cas_calcule_a_la_main():
    # 4 abonnés en tête de liste, dont 3 sont réellement partis : 3 / 4 = 0,75
    assert precision_at_k(liste, k=4, frequency="W-MON") == 0.75
```

Si quelqu'un modifie la fonction et la casse, ce test échoue immédiatement. Le projet compte 180 tests, lancés en quelques minutes. Certains sont très particuliers, comme la *sentinelle anti-fuite* du chapitre 6, qui vérifie que le modèle n'utilise jamais d'information venue du futur.

### Les contrôles de style et de types

Deux outils relisent le code sans l'exécuter :

- **ruff** repère les erreurs courantes et impose une présentation uniforme ;
- **mypy** vérifie la cohérence des **types**, par exemple qu'on ne passe pas un texte là où un nombre est attendu.

### L'intégration continue

L'**intégration continue** consiste à relancer automatiquement tous ces contrôles à chaque envoi de code sur GitHub, sur une machine neutre. Dans ce projet, ils tournent sur deux versions de Python, 3.12 et 3.14.

> **Dans les coulisses.** Au lot 5, les contrôles passaient sur l'ordinateur de développement, mais l'intégration continue a signalé une ligne de code trop longue. Un cache local avait masqué l'erreur. C'est précisément à cela que sert une machine neutre.

## 6. Git, branches et pull requests

**Git** enregistre l'historique complet du code, comme une machine à remonter le temps : chaque enregistrement, appelé *commit*, est une photo du projet accompagnée d'un message qui explique ce qui a changé.

Une **branche** est une copie de travail parallèle. On y développe un lot sans toucher à la version principale, appelée `main`.

Une **pull request** est une demande d'intégration : « voici le travail du lot, merci de le relire avant de l'ajouter à la version principale ». Elle présente les changements, les résultats et les points d'attention. Elle n'est fusionnée qu'une fois relue et une fois les contrôles automatiques au vert.

La règle du projet est simple : **jamais d'enregistrement direct sur `main`**. Chaque lot passe par sa branche et sa pull request.

## 7. Travailler avec une intelligence artificielle

Ce projet est construit avec l'aide d'un assistant d'intelligence artificielle qui écrit du code. Les rôles sont clairement répartis :

- le **propriétaire du projet** fixe le cap, arbitre les choix et fusionne les pull requests ;
- l'**assistant** cadre, écrit le code, lance les contrôles et rédige la documentation.

Pour qu'un assistant travaille bien, il lui faut des consignes écrites. Le fichier `AGENTS.md` joue ce rôle : c'est le manuel du projet, avec le périmètre, les règles, les outils autorisés et interdits, et les erreurs à ne pas commettre.

L'essentiel est ailleurs : **tout ce qui est produit est vérifié**, par des tests, par des mesures, et par la relecture. Un assistant peut se tromper avec aplomb. Dans ce projet, plusieurs de ses affirmations ont été démenties par la mesure, puis corrigées par écrit. Le chapitre 8 en raconte deux.

## 8. Mesurer plutôt que supposer

C'est probablement le principe le plus important du projet. Chaque fois que c'est possible, un choix repose sur une mesure, pas sur une intuition ou une réputation. Quatre exemples :

- **pandas ou polars ?** Ce sont deux bibliothèques de manipulation de tableaux. Polars s'est révélé 4,5 fois plus rapide sur le calcul clé du projet, mais le gain réel n'était que de 1,6 seconde. Pandas a été conservé, pour ne pas faire cohabiter deux outils. Et surtout, cette mesure a révélé que la première version du calcul produisait **10,5 % de lignes fausses sans aucun message d'erreur**. Ce défaut a été corrigé et un test le surveille désormais.
- **Faut-il la bibliothèque shap ?** Elle sert à expliquer les prédictions. Mesure faite, le modèle retenu calcule exactement les mêmes valeurs lui-même, sans les 138 Mo de dépendances supplémentaires. Elle a été écartée du produit final.
- **Comment KKBox définit-il un départ ?** Plutôt que de deviner, le projet a recopié la règle officielle fournie avec les données. Cinq de ses subtilités auraient été ratées par n'importe quelle hypothèse raisonnable.
- **Le taux d'écoute complète est-il le meilleur signal ?** C'était l'hypothèse de départ. La mesure ne l'a pas confirmée, et c'est écrit tel quel.

> **À retenir.** Une supposition non vérifiée s'écrit comme une supposition. Quand la mesure contredit l'intuition, c'est la mesure qui gagne, et on corrige la documentation.

---

## À vous de jouer

**Contexte.** Vous lancez un petit projet : prédire quels clients d'une boulangerie en ligne ne recommanderont pas le mois prochain. Un collègue propose le plan suivant.

> « On prend le fichier des commandes, on entraîne directement un modèle, et si le score est bon on le met en production. Le critère de réussite : le modèle doit être performant. »

**Questions.**

1. Citez deux questions de cadrage à poser avant de commencer.
2. Réécrivez le critère « le modèle doit être performant » en un critère d'acceptation vérifiable.
3. Votre collègue affirme qu'une bibliothèque récente « est beaucoup plus rapide ». Que faites-vous avant de l'adopter ?

<details>
<summary>Voir la correction</summary>

1. **Exemples de bonnes questions :** qu'appelle-t-on « ne pas recommander » : aucune commande dans le mois, ou dans les 60 jours ? Combien de clients l'équipe peut-elle contacter, et par quel moyen ? Dispose-t-on de l'historique daté des commandes, ou seulement d'un résumé ? Quelle méthode simple utilise-t-on aujourd'hui, et que faut-il battre ?

2. **Exemple de critère vérifiable :** « Sur les trois derniers mois de données, jamais vus pendant l'apprentissage, parmi les 30 clients classés en tête chaque semaine, la part de clients qui n'ont effectivement pas recommandé est supérieure à celle obtenue en classant simplement les clients par date de dernière commande. »

3. **On mesure.** On compare les deux bibliothèques sur le vrai calcul du projet, avec les vrais volumes. On vérifie que les résultats sont identiques, et pas seulement plus rapides. On pèse le gain réel face au coût d'un outil supplémentaire. Et on consigne la décision avec ses chiffres.

</details>

---

## En résumé

- **Cadrer** consiste à répondre aux questions cachées derrière la demande initiale, avant de construire. Un cahier des charges se relit de façon critique.
- Le **registre des décisions** consigne chaque choix avec son motif. Une décision se révise par écrit, jamais en silence.
- Le **contrat de données** fixe le format des données avant tout calcul.
- Le projet avance par **lots**, chacun terminé seulement quand ses **critères d'acceptation** sont vérifiés.
- **Tests**, **contrôles automatiques** et **intégration continue** détectent les erreurs au plus tôt.
- Le travail passe par des **branches** et des **pull requests** relues, jamais directement sur la version principale.
- Le principe directeur : **mesurer plutôt que supposer**, et corriger par écrit quand la mesure contredit l'intuition.

**Chapitre précédent :** [1. L'application](01-application.md) · **Chapitre suivant :** [3. Les outils : les choix technologiques expliqués](03-outils.md)
