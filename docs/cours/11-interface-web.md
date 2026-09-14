# Chapitre 11. Montrer les résultats : l'interface web

> **Partie 4, restituer les résultats** · Lecture : 35 minutes · Prérequis : chapitre 10

## Ce que vous allez apprendre

À la fin de ce chapitre, vous saurez :

- expliquer à quoi sert une interface dans un projet de data science ;
- décrire les quatre écrans de l'application et le bandeau qui les accompagne ;
- justifier pourquoi l'interface ne calcule rien, et ce que cela impose au reste du projet ;
- choisir quelles informations sur un abonné on peut afficher sans tromper le lecteur ;
- tester une interface web sans ouvrir de navigateur ;
- identifier les questions à trancher avant de mettre des données en ligne.

---

## 1. Pourquoi une interface

Les fichiers du chapitre 10 contiennent tout. Mais personne n'a envie d'ouvrir un fichier Parquet, et un recruteur ne consacre que quelques minutes à un projet. Une interface rend le travail **visible** : on voit la liste, on clique sur un abonné, on comprend pourquoi il est là et quoi lui dire.

Le projet utilise **Streamlit**, présenté au chapitre 3 : une bibliothèque qui construit une page web entièrement en Python. Pas de HTML à écrire, pas de serveur à configurer.

Pour la lancer sur son ordinateur, une fois les données préparées :

```bash
uv run python scripts/train_model.py --source kkbox
uv run python -m churn.pipeline.run_scoring --source kkbox
uv run streamlit run app/streamlit_app.py
```

La troisième commande ouvre l'application dans le navigateur, à l'adresse `http://localhost:8501`. Le mot `localhost` désigne votre propre ordinateur : l'application n'est pas encore en ligne.

## 2. Les quatre écrans et le bandeau

Une barre latérale permet de choisir la **source des données**, l'**écran**, et la **date de scoring** parmi les exports disponibles.

### Le bandeau de source

En haut de chaque écran, un bandeau rappelle d'où viennent les chiffres :

- sur KKBox, un encadré bleu : *« Source : KKBox WSDM Churn Prediction Challenge. Capacité de 50 appels par semaine, hypothèse de démonstration fixée dans la configuration. »* ;
- sur les données fictives, un encadré orange : *« Données simulées. Aucun chiffre affiché ici ne vaut performance. »*

Le bandeau est placé **avant** tout écran, dans le code. Il ne peut donc pas être oublié sur l'un d'eux.

### Écran 1 : le projet

C'est la page d'accueil, pensée pour quelqu'un qui découvre le projet en deux minutes.

- **Le problème**, en trois phrases : une équipe ne peut appeler que 50 abonnés par semaine, lesquels choisir, et que leur dire ?
- **Les chiffres clés**, lus dans le rapport d'évaluation : combien de départs réels se trouvent parmi les 50 appelés, pour le meilleur modèle, pour la plus forte des régressions logistiques et pour le tri par revenu. Sur KKBox : **16 départs** pour XGBoost, **7** pour la régression logistique, **5** pour le tri par revenu.
- **Comment ça marche**, en quatre étapes : les données, un tableau construit sans tricher, un modèle évalué honnêtement, une liste expliquée.
- **Pourquoi s'y fier** et les **limites assumées**, puis les liens vers le code, ce cours et les résultats détaillés.

Les chiffres ne sont pas écrits dans le code de la page. Ils sont multipliés à partir de la précision du rapport : 0,3228 × 50 donne environ 16. Si le rapport change, la page change avec lui.

### Écran 2 : la liste du lundi

- En tête, quatre indicateurs : la date, le nombre d'abonnés scorés, le nombre d'appels de la semaine et la version du modèle.
- Un tableau des abonnés : rang, décile, revenu et trois motifs. Un clic sur un en-tête **trie** la colonne.
- Des filtres : seulement les 50 appels de la semaine, certains déciles, ou la recherche d'un abonné.
- Le score technique est **masqué par défaut**, puisqu'il ne se lit pas comme un pourcentage. Une case permet de l'afficher pour un diagnostic.
- Un bouton télécharge le CSV du chapitre 10, prêt pour Excel.

### Écran 3 : la fiche d'un abonné

C'est l'écran qu'un conseiller ouvre avant de décrocher son téléphone. Il répond à trois questions, dans cet ordre.

**Que lui dire ?** Sous le rang, le décile et le revenu, une section « Que dire au téléphone » reprend ses motifs, et sous chacun, l'**action conseillée**. Par exemple :

> **1. [PRODUIT] Fréquence d'usage**
> Action conseillée : Vérifier si l'usage du service a changé

Ces actions ne sont pas inventées par l'application. Elles viennent du même dictionnaire que les libellés des motifs, `config/feature_mapping.yaml`, présenté au chapitre 9. Un motif structurel, comme l'ancienneté, n'a pas d'action : il n'est de toute façon jamais affiché.

**Qui est-ce ?** Un **profil de l'abonné** en huit indicateurs : sa date d'inscription et son ancienneté, son dernier usage et son nombre de jours actifs sur les 30 derniers jours, sa dernière facture et son montant, le nombre de ses annulations passées et de ses renouvellements automatiques désactivés.

**Pourquoi le modèle l'a-t-il classé là ?** Un **graphique en barres** des contributions de chaque variable, en trois couleurs : les motifs affichés, les variables actionnables non retenues, et les variables structurelles, qui ne sont jamais affichées. Une ligne en pointillés marque le seuil de signification. Enfin, son **historique** : un graphique des jours d'usage par semaine et la liste de ses derniers événements de paiement.

> **Attention.** Le profil et l'historique s'arrêtent **strictement avant la date de scoring**. Afficher ce qui s'est passé ensuite montrerait des informations que le modèle ne pouvait pas connaître, et pousserait à juger le classement avec le recul du futur. C'est la règle d'or du chapitre 6, appliquée jusqu'à l'affichage.

### Choisir ce qu'on montre d'un abonné

Le référentiel des comptes contient d'autres colonnes. Trois ont été **volontairement écartées** du profil.

| Information | Pourquoi elle n'est pas affichée |
| :--- | :--- |
| Type de contrat | Il décrit l'abonné **à la date d'extraction** des données, pas à la date de scoring. Au chapitre 9, cette même colonne avait causé une fuite, la décision D18 |
| Segment et canal d'acquisition | Sur KKBox, ce ne sont que des **codes** sans signification connue. Un conseiller ne peut rien en faire |
| Date de résiliation | C'est un **fait du futur**, justement ce que le modèle cherche à prédire |

Seule la date d'inscription est gardée : c'est un fait figé du passé, vrai à n'importe quelle date.

> **Dans les coulisses.** La première version du profil affichait « Dernier paiement ». Or le calcul lit le dernier événement *facture émise*, et une facture émise n'est pas forcément payée. Le libellé est devenu « Dernière facture ». Un libellé est une affirmation : il doit dire exactement ce que le chiffre mesure.

### Écran 4 : la performance du modèle

- Trois indicateurs : le meilleur classement, le nombre de départs qu'il trouve sur 50 appels, et combien de fois il fait mieux que le tri par revenu.
- Le tableau des huit classements du chapitre 8 : précision, écart type, rappel, ROC-AUC, lift.
- La **courbe** de précision semaine par semaine, pour les classements choisis. Sur KKBox, on y voit XGBoost au-dessus à la fois de la régression logistique et du tri par revenu sur 75 des 80 semaines de test.

C'est l'argument technique central du projet, présenté de façon que chacun puisse le vérifier.

## 3. Lecture seule : séparer le calcul et l'affichage

### Le principe

L'interface **n'entraîne aucun modèle, ne score aucun abonné et ne recalcule aucune mesure**. Elle affiche des fichiers produits par le pipeline. On parle d'interface **en lecture seule**. C'est la décision D21.

Pensez à un restaurant. La cuisine prépare les plats, la salle les sert. Si les serveurs se mettaient à cuisiner en salle, chacun à sa façon, deux clients commandant le même plat recevraient deux plats différents. Ici, la cuisine est le pipeline, la salle est l'interface.

Trois raisons concrètes :

- **Une seule vérité.** Le chiffre affiché est exactement celui du fichier. Aucune formule parallèle ne peut diverger.
- **La rapidité.** Lire un fichier prend un instant. Le scoring complet des 5 093 abonnés KKBox prend 25 secondes : le refaire à chaque clic rendrait l'application inutilisable.
- **La sécurité.** Une interface publique qui ne contient aucun code d'entraînement ne peut pas, par erreur, modifier un modèle.

Le profil de l'abonné n'enfreint pas la règle. Compter des jours actifs ou retrouver une dernière facture, c'est **lire** le journal, comme le fait l'historique. Aucun modèle n'intervient, et aucune mesure de performance n'est recalculée.

### Ce que cela a imposé au pipeline

Deux écrans demandaient des informations absentes des fichiers :

| Écran | Besoin | Ajout au pipeline |
| :--- | :--- | :--- |
| Fiche d'un abonné | La contribution de chaque variable | Un fichier de contributions à côté de l'export : une ligne par abonné et par variable d'origine |
| Performance | La précision de chaque semaine | Deux fichiers de données à côté du rapport : le résumé et la précision par semaine |

Plutôt que de faire recalculer ces valeurs par l'interface, on les a fait **écrire par le pipeline**. C'est plus de travail au départ, et c'est ce qui garantit la règle.

### Un code en couches

- `src/churn/interface/readers.py` sait **où** sont les fichiers et **comment** les lire.
- `src/churn/interface/accounts.py` construit le **profil** d'un abonné et retrouve l'**action conseillée** de chaque motif.
- `app/streamlit_app.py` **affiche**. Il ne contient aucune logique de lecture complexe.

Les deux premiers se testent comme n'importe quel module Python, sans Streamlit. Le test du profil place volontairement un événement le jour même de la date de scoring et un autre après, et vérifie qu'aucun des deux n'est compté.

## 4. Tester une interface sans navigateur

### L'outil

Tester une page web à la main, en cliquant, est lent et s'oublie. Streamlit fournit un outil, **AppTest**, qui exécute l'application sans navigateur et permet d'inspecter ce qu'elle afficherait : les encadrés, les tableaux, les indicateurs. On peut aussi simuler un clic, par exemple choisir un autre écran.

### Tester sur des fichiers temporaires

Les tests ne doivent pas dépendre des vrais fichiers de votre ordinateur, absents de la machine d'intégration continue. L'application lit donc une **variable d'environnement**, `NSY_CHURN_ROOT`. Une variable d'environnement est un réglage transmis à un programme par le système, sans modifier son code. Les tests y placent un dossier temporaire, qu'ils remplissent avec des données fictives, un export et un rapport.

### Ce que les tests vérifient

| Test | Critère de la roadmap |
| :--- | :--- |
| L'application démarre sans erreur sur chacun des quatre écrans quand aucun export n'existe | Démarrer sur un export vide |
| Le bandeau de données simulées apparaît sur chacun des quatre écrans | Bandeau visible partout |
| Avec une capacité de 7 dans la configuration, le bandeau annonce 7 appels | Aucune valeur métier en dur |
| L'application n'importe aucun code d'entraînement ni de scoring | Ne recalcule rien |
| L'accueil affiche les chiffres clés du rapport, la liste, la fiche et la performance s'affichent à partir des fichiers | Les quatre écrans |
| La fiche montre une action conseillée et le profil de l'abonné | Enrichissements de la fiche |

> **Dans les coulisses.** La première version du test « n'importe aucun code de scoring » cherchait simplement le texte `churn.pipeline.run_scoring` dans le fichier de l'application. Il a échoué : le texte apparaissait bien, mais dans la phrase qui indique à l'utilisateur quelle commande lancer, pas dans un import. Le test a été réécrit pour analyser les vrais imports, grâce à l'**arbre syntaxique** du fichier, la structure que Python construit en lisant le code. Un test trop naïf crie au loup, et un test qui crie au loup finit ignoré.

Un autre test protège le lien entre les motifs et les actions. L'export écrit un motif sous la forme `[PRODUIT] Fréquence d'usage`, et l'interface cherche l'action sous exactement la même forme. Si l'un des deux changeait d'écriture, les actions disparaîtraient en silence. Le test fabrique un libellé avec la fonction de l'export et vérifie que l'interface lui trouve son action.

## 5. Mettre en ligne : une question de données, pas de technique

Sur le plan technique, la mise en ligne est simple. Streamlit Community Cloud, un service d'hébergement gratuit, installe l'application directement depuis le dépôt GitHub, en lisant le fichier `uv.lock`.

La vraie question est ailleurs. **Une application en ligne lit des fichiers publiés avec elle.** Ici, ces fichiers seraient dérivés des données KKBox : identifiants d'abonnés, scores, motifs et, pour la fiche, le journal d'écoute. Or les données d'une compétition Kaggle sont soumises à des **règles d'utilisation**, qui encadrent en général leur redistribution.

Plusieurs options existent :

- publier l'interface avec les **données fictives** seulement, sans risque, mais moins démonstratif ;
- publier un **extrait réduit** des résultats KKBox, sans le journal d'écoute, après avoir vérifié ce que les règles autorisent ;
- ne pas publier, et présenter l'interface par des **captures d'écran** dans le README.

Ce choix engage la personne qui publie. Il a donc été laissé au propriétaire du projet, qui a retenu une solution intermédiaire, la décision D22 :

- l'**accueil** et l'écran de **performance** montrent les vrais résultats KKBox, qui ne sont que des moyennes et ne décrivent aucun abonné ;
- la **liste** et la **fiche**, profil compris, tournent sur une chaîne complète de **données simulées**, sous leur bandeau orange ;
- sur la source KKBox, un message remplace la liste et explique pourquoi elle n'est pas publiée.

Ces fichiers vivent dans un dossier `demo/`, construit par un script. Le script refuse de copier un fichier qui contiendrait un identifiant d'abonné, et deux tests vérifient qu'aucune donnée individuelle KKBox ne s'y glisse jamais.

> **À retenir.** Mettre des données en ligne est une décision, pas un détail technique. Avant de publier, on vérifie ce que la licence ou les règles d'utilisation des données permettent.

---

## À vous de jouer

**Contexte.** Un collègue fait cinq propositions pour l'interface.

- **A.** Ajouter sur la fiche d'un abonné un bouton « Recalculer le score » qui relance le modèle.
- **B.** Afficher dans l'historique les événements des 30 jours qui suivent la date de scoring, « pour voir si le modèle avait raison ».
- **C.** N'afficher le bandeau de source que sur la page d'accueil, « pour alléger les autres écrans ».
- **D.** Vérifier que l'application n'utilise pas XGBoost en cherchant le mot `xgboost` dans son fichier.
- **E.** Ajouter au profil de l'abonné son type de contrat, « puisque la colonne existe déjà ».

**Question.** Pour chaque proposition, dites ce qui ne va pas et proposez une alternative.

<details>
<summary>Voir la correction</summary>

**A.** L'interface deviendrait une seconde cuisine : le score affiché pourrait différer de celui de l'export, et il faudrait embarquer le code d'entraînement dans une page publique. L'alternative est de relancer le pipeline, puis de laisser l'interface lire le nouvel export.

**B.** Sur la fiche utilisée pour préparer un appel, ce serait afficher le futur : le conseiller jugerait l'abonné avec des informations que personne n'avait le lundi. Vérifier si le modèle avait raison est une vraie question, mais elle a déjà sa réponse : l'écran de performance, calculé sur des semaines que le modèle n'a jamais vues.

**C.** Un écran copié dans une présentation ou une capture d'écran perd le contexte de la page d'accueil. Un chiffre simulé pourrait alors être pris pour un chiffre réel. Le bandeau reste sur chaque écran, et il est placé dans le code avant tout écran pour ne jamais être oublié.

**D.** La recherche d'un mot échoue dès que ce mot apparaît dans un commentaire ou un message, et elle passe à côté d'un import détourné. L'alternative est d'analyser les imports réels du fichier, par son arbre syntaxique, comme le fait le test du projet.

**E.** Que la colonne existe ne dit pas **à quelle date** elle est vraie. Le type de contrat décrit l'abonné à la date d'extraction : un abonné passé en résiliation manuelle après le lundi apparaîtrait ainsi dès le lundi, ce qui revient à montrer le futur. C'est la fuite de la décision D18. L'alternative est de reconstruire l'information à partir du journal, daté : le nombre de renouvellements automatiques désactivés **avant** la date de scoring, que le profil affiche déjà.

</details>

---

## En résumé

- L'interface **rend le projet visible** : accueil, liste du lundi, fiche d'un abonné, performance du modèle, avec un **bandeau de source** sur chaque écran.
- L'**accueil** donne le problème, les chiffres clés lus dans le rapport et les limites, en deux minutes de lecture.
- La **fiche** dit quoi dire au téléphone, avec l'**action conseillée** de chaque motif, et qui est l'abonné, avec un **profil** limité à ce qui était connu avant la date de scoring.
- Elle est **en lecture seule** : elle n'entraîne, ne score et ne recalcule rien. Le pipeline écrit tout ce qu'elle affiche, y compris les **contributions** et la **précision par semaine**.
- Une information n'est affichée que si l'on sait **à quelle date** elle est vraie.
- L'interface se **teste sans navigateur** avec AppTest, sur un dossier temporaire désigné par une **variable d'environnement**.
- La **mise en ligne** est simple techniquement, mais la publication de données dérivées de KKBox est une **décision** qui dépend des règles de la compétition.

**Chapitre précédent :** [10. Livrer la liste du lundi](10-livrer-la-liste.md) · **Retour au** [sommaire du cours](README.md)
