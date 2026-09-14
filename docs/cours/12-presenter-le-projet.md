# Chapitre 12. Présenter le projet : le README et la mise en ligne

> **Partie 4, restituer les résultats** · Lecture : 30 minutes · Prérequis : chapitre 11

## Ce que vous allez apprendre

À la fin de ce chapitre, vous saurez :

- expliquer pourquoi le README est le document le plus important d'un projet publié ;
- construire un README qui répond d'abord au lecteur non technique, puis au lecteur technique ;
- accompagner chaque chiffre de sa source et de son incertitude ;
- écrire des limites vérifiées, et pas seulement recopiées ;
- donner à quelqu'un d'autre les moyens de reproduire les résultats et de publier l'application.

---

## 1. Le document le plus lu du projet

Ouvrez n'importe quel dépôt sur GitHub : la page affiche la liste des fichiers, puis, juste en dessous, le contenu d'un fichier nommé `README.md`. Ce fichier est la **vitrine** du projet. C'est souvent le seul qu'un visiteur lira.

Ce projet est destiné à un portfolio. Son visiteur type est un recruteur ou un data scientist qui dispose de quelques minutes. Il ne lira pas le code qui construit les variables. S'il ne comprend ni le problème ni le résultat en lisant le haut du README, le reste du travail n'existe pas pour lui.

C'est pourquoi la décision D16 en fait un **livrable de première classe** : écrit en dernier, quand les résultats sont connus, mais prévu dès le premier jour.

> **À retenir.** Un projet de data science n'est terminé que lorsqu'il est **expliqué**. Un bon modèle mal présenté ne convainc personne.

## 2. Un plan fixé avant de connaître les résultats

Le plan du README a été écrit dans la roadmap dès le cadrage, bien avant la première mesure. Il compte sept sections, et chacune répond à une question du lecteur.

| Section | Question du lecteur |
| :--- | :--- |
| 1. Le problème et la cible | De quoi parle-t-on, et que prédit-on exactement ? |
| 2. Les données | D'où viennent-elles, et pourquoi celles-là ? |
| 3. Le protocole de validation | Comment savoir que le résultat n'est pas une illusion ? |
| 4. Les résultats | Le modèle fait-il mieux que des méthodes simples ? |
| 5. L'explicabilité | Pourquoi tel abonné est-il en tête de liste ? |
| 6. Les limites | Qu'est-ce qui n'est pas démontré ? |
| 7. L'application et la reproduction | Où voir le résultat, et comment le refaire ? |

Fixer le plan à l'avance protège l'honnêteté du document. Si le modèle avait déçu, la section 4 aurait dû le dire quand même, et la section 6 était prévue avant qu'on sache quoi y mettre. On ne choisit pas après coup de ne parler que de ce qui arrange.

Quatre critères d'acceptation accompagnent ce plan :

1. un lecteur non technique comprend le problème et le résultat en lisant les deux premières sections ;
2. un lecteur technique trouve l'embargo, la définition de la Precision@K et les lignes de base sans ouvrir le code ;
3. aucune affirmation de performance n'est faite sans indiquer la source des données ;
4. les limites sont écrites, pas éludées.

## 3. Écrire pour deux lecteurs

### Le lecteur non technique

Il veut savoir ce que fait l'application et si elle marche. On lui parle donc en **appels téléphoniques**, pas en métriques :

> Sur 50 appels par semaine, le modèle désigne en moyenne 14 abonnés qui partiront réellement dans les 30 jours, contre 7 pour une régression logistique et 4 pour un tri par revenu.

La même information, écrite « Precision@50 de 0,2737 », est exacte mais ne dit rien à ce lecteur. Les deux formes figurent dans le README : la phrase en haut, le tableau plus bas.

### Le lecteur technique

Il cherche les endroits où un projet de churn se trompe habituellement : le découpage des données, la métrique, la comparaison. Il doit les trouver **sans ouvrir le code**. L'embargo du chapitre 7, par exemple, tient en trois phrases :

> Chaque ligne d'apprentissage porte une réponse qui n'est connue que 60 jours après sa date : 30 jours d'horizon, puis 30 jours pour constater que l'abonné n'a pas renouvelé. Si l'apprentissage s'arrêtait la veille du test, les réponses de ses dernières lignes se joueraient pendant la période de test, et le modèle apprendrait des départs qu'il doit justement prédire. On laisse donc 60 jours vides entre apprentissage et test, et on retire toute ligne d'apprentissage dont la réponse est constatée après le début du test.

Aucune formule, et un lecteur technique sait exactement ce qui a été fait.

> **Dans les coulisses.** Ce paragraphe a d'abord été écrit avec « 30 jours ». Pour donner la définition exacte de la cible, le code a été relu ligne à ligne, et une erreur est apparue : sur KKBox, un départ est daté à l'expiration de l'abonnement, mais il n'est constaté que 30 jours plus tard. L'embargo était trop court, et la grille écartait des abonnés encore libres de renouveler. L'écriture du README s'est arrêtée là : correction, nouvelle mesure, décision D24. La Precision@50 de XGBoost est passée de 0,323 à 0,274. Le chiffre publié est moins flatteur, et il ne repose plus sur cette erreur. Expliquer précisément ce qu'on a fait est souvent le meilleur moyen de découvrir ce qu'on a mal fait.

## 4. Chaque chiffre porte sa source

Le projet utilise deux sources : les vraies données KKBox et un générateur de données fictives. La décision D2 interdit de présenter un chiffre obtenu sur données fictives comme une performance. Dans le README, **chaque résultat nomme donc sa source**, sa date et ses conditions : KKBox, mesure du 14 septembre 2026, quatre plis chronologiques, 76 semaines de test.

Un chiffre porte aussi son **incertitude**. Le README ne se contente pas d'une moyenne :

| Affirmation | Ce qui la soutient |
| :--- | :--- |
| Le modèle bat la régression logistique | +0,133 de Precision@50 à variables égales, positif sur les 4 plis, écart type de 0,070 |
| Il bat les lignes de base la plupart des semaines | Au-dessus du hasard, du tri par revenu et des deux régressions logistiques sur 64 des 76 semaines de test |
| Le journal d'écoute améliore le modèle | **Non établi** : +0,008 en moyenne, positif sur 2 plis sur 4 |

La troisième ligne compte autant que les deux premières. Écrire « le journal d'écoute améliore les prédictions » serait flatteur, et démenti par la mesure.

> **Attention.** Un pourcentage sans contexte est dangereux. Le projet contient un « 97,03 % » : c'est la concordance entre la cible reconstruite et l'étiquette officielle de KKBox, au chapitre 5. Sorti de son contexte, il passerait pour la précision du modèle.

## 5. Écrire les limites, et les remesurer

Une section de limites n'est pas un aveu de faiblesse. Pour un lecteur expérimenté, c'est le signe que l'auteur sait où son travail s'arrête. Celles du projet : une capacité de 50 appels hypothétique, un échantillon de 8 150 abonnés sur 2,36 millions, un écart de 3 % inexpliqué sur la cible, des scores qui ne sont pas des probabilités, des motifs qui ne disent pas dans quel sens un signal a bougé.

Mais une limite est aussi une affirmation. Elle se **vérifie** comme un résultat.

> **Dans les coulisses.** La liste des dettes du projet mentionnait des « semaines à précision nulle, inexpliquées ». La remarque venait du lot 4, où les trois lignes de base tombaient à zéro certaines semaines de 2016. Avant de la recopier dans le README, elle a été recomptée sur la mesure de référence : **XGBoost n'a aucune semaine à zéro**, même si sa pire semaine ne vaut que 0,02. Le tri par revenu tombe à zéro deux semaines, la régression logistique une semaine. La limite existe toujours, mais elle ne concerne pas le modèle retenu. Recopiée telle quelle, elle aurait été fausse.

> **Dans les coulisses.** Au lot 5, les limites affirmaient qu'« une ligne de base linéaire mieux préparée ferait probablement mieux que 0,149 ». Plutôt que de laisser ce « probablement » dans le README, la mesure complémentaire du chapitre 8 l'a testé. Résultat : la régression logistique réglée fait **moins bien** en tête de liste, 0,126. Une hypothèse écrite dans les limites est une invitation à mesurer.

## 6. Des documents qui restent vrais

Le code est surveillé par des tests. Les documents ne le sont pas : ils peuvent devenir faux sans que rien ne le signale. On parle de **dérive documentaire**.

> **Dans les coulisses.** En préparant le README, deux dérives ont été trouvées. La première : trois fichiers annonçaient les décisions « de D1 à D20 », et un chapitre « de D1 à D18 », alors que le registre en compte vingt-trois. La seconde, plus gênante : le chapitre 11 montrait un motif écrit `[PRODUIT] Fréquence d'usage`, alors que l'export écrit `[PRODUCT] Fréquence d'usage`. Un lecteur qui aurait cherché ce libellé dans la liste ne l'aurait pas trouvé. Les deux ont été repérées par une recherche dans tout le dépôt, puis corrigées.

La parade tient en deux habitudes :

- **copier plutôt que retaper** : un libellé ou un chiffre cité vient du fichier ou de la sortie qui le produit ;
- **rechercher avant de publier** : chercher l'ancienne formulation, par exemple `D1 à D`, dans tout le dépôt ne coûte que quelques secondes.

## 7. Reproduire et mettre en ligne

### Reproduire

Un résultat qu'on ne peut pas refaire ne prouve pas grand-chose. La section 7 du README donne les commandes, dans l'ordre :

```bash
uv sync                                                    # installe les versions exactes
uv run pytest                                              # vérifie la chaîne
uv run python scripts/download_kkbox.py --with-logs --sample-size 10000
uv run python scripts/train_model.py --source kkbox        # évaluation et modèle
uv run python -m churn.pipeline.run_scoring --source kkbox  # liste du lundi
uv run streamlit run app/streamlit_app.py                  # interface
```

Trois éléments rendent ces commandes fiables : le fichier `uv.lock`, qui fige la version de chaque bibliothèque ; la **graine** du fichier de configuration, qui fixe le hasard ; et l'export déterministe du chapitre 10. Le README prévient aussi du coût : près de 9 Go à télécharger avec le journal d'écoute, et un quart d'heure pour l'évaluation et le modèle final.

### Mettre en ligne

Publier une application sur un serveur accessible à tous s'appelle un **déploiement**. Le projet utilise **Streamlit Community Cloud**, un hébergement gratuit relié au dépôt GitHub. Les étapes :

1. se connecter avec le compte GitHub propriétaire du dépôt ;
2. choisir le dépôt, la branche `main` et le fichier `app/streamlit_app.py` ;
3. choisir Python 3.12, l'une des deux versions vérifiées par l'intégration continue ;
4. déclarer un **secret** : `NSY_CHURN_ROOT = "demo"`.

Un secret est un réglage transmis à l'application par l'hébergeur, sans être écrit dans le code. Il sert d'ordinaire à protéger un mot de passe. Celui-ci n'a rien de confidentiel : il indique à l'application de lire le dossier `demo/`, puisque les données locales n'existent pas sur le serveur. L'adresse obtenue est reportée dans la section 7 du README.

> **Dans les coulisses.** Trois détails ont demandé une correction avant la mise en ligne. D'abord, la documentation de Streamlit ne dit pas clairement si un secret devient une variable d'environnement : l'application lit donc les deux. Ensuite, le chemin `demo` est relatif, et le serveur ne démarre pas forcément dans le dossier du dépôt : l'application le résout à partir de son propre emplacement. Enfin, le script qui construit `demo/` copiait d'abord le rapport d'évaluation au format texte, qui contient sa date de génération : deux constructions donnaient deux dossiers différents. Seuls les fichiers de données du rapport sont désormais publiés, et le dossier est identique à chaque construction.

---

## À vous de jouer

**Contexte.** Un collègue propose quatre phrases pour le README.

- **A.** « Notre modèle atteint 97 % de précision. »
- **B.** « XGBoost est 3,3 fois meilleur. »
- **C.** « Grâce au journal d'écoute, le modèle détecte mieux les départs. »
- **D.** « Limites : aucune limite majeure identifiée. »

**Question.** Pour chaque phrase, dites ce qui ne va pas et proposez une réécriture fidèle aux mesures du projet.

<details>
<summary>Voir la correction</summary>

**A.** Le chiffre ne vient pas du modèle : 97,03 % est la concordance de la cible reconstruite avec l'étiquette officielle. Le mot « précision » est ambigu, et une exactitude globale ne veut rien dire quand l'événement est rare : avec environ 2 % de départs par ligne, un modèle qui annonce « personne ne part » a raison environ 98 fois sur 100. La source manque aussi. Réécriture : « Sur KKBox, parmi les 50 abonnés classés en tête chaque semaine, 27 % partent réellement dans les 30 jours, soit environ 14 appels utiles sur 50, en moyenne sur quatre plis chronologiques. »

**B.** Meilleur que quoi, sur quelles données ? 3,3 ressemble au lift contre le tri par revenu, qui vaut d'ailleurs 3,1 sur la mesure de référence. Contre la régression logistique, le rapport n'est que d'environ 2. Réécriture : « Sur KKBox, XGBoost trouve 3,1 fois plus de départs que le tri par revenu en tête de liste, et gagne 0,133 de Precision@50 sur la régression logistique à variables égales, sur chacun des quatre plis. »

**C.** La mesure ne soutient pas cette phrase. Réécriture : « L'apport du journal d'écoute n'est pas établi : +0,008 de Precision@50 en moyenne, positif sur deux plis sur quatre. »

**D.** C'est éluder les limites, ce que le quatrième critère interdit. Réécriture : une liste courte et vérifiée, par exemple « capacité de 50 appels hypothétique ; échantillon de 8 150 abonnés ; écart de 3 % inexpliqué entre la cible reconstruite et l'étiquette officielle ; scores qui ne sont pas des probabilités ».

</details>

---

## En résumé

- Le **README** est la vitrine du projet, souvent le seul document lu. Il est écrit en dernier et prévu dès le début.
- Son **plan est fixé avant les résultats**, pour qu'un résultat décevant ou une limite gênante ne puissent pas disparaître.
- Il s'adresse d'abord au **lecteur non technique**, en appels utiles, puis au **lecteur technique**, qui trouve l'embargo, la métrique et les lignes de base sans ouvrir le code.
- **Chaque chiffre porte sa source** et son incertitude, et un gain non établi est écrit comme tel.
- Les **limites se vérifient** comme des résultats. Les documents dérivent : on copie les chiffres depuis leur source et on **recherche** les anciennes formulations avant de publier.
- La **reproduction** repose sur `uv.lock`, la graine et l'export déterministe. Le **déploiement** sur Streamlit Community Cloud se règle par un **secret** qui désigne le dossier `demo/`.

**Chapitre précédent :** [11. Montrer les résultats : l'interface web](11-interface-web.md) · **Retour au** [sommaire du cours](README.md)
