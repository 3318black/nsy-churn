# Glossaire

Les termes du cours, par ordre alphabétique. Le numéro renvoie au chapitre où le terme est expliqué en détail.

| Terme | Définition | Chapitre |
| :--- | :--- | ---: |
| **Ablation** | Mesure qui retire un ingrédient à la fois, un modèle ou une famille de données, pour isoler son apport. | 8 |
| **Adaptateur** | Code qui convertit une source de données particulière au format du contrat de données. | 4 |
| **Apprentissage supervisé** | Apprendre à partir d'exemples dont on connaît déjà la réponse. | 1 |
| **Arbre de décision** | Modèle qui pose une suite de questions sur les variables pour aboutir à un score. | 8 |
| **Batch** | Traitement par lots : un calcul lancé à intervalle régulier sur toutes les données d'un coup, plutôt qu'à la demande. | 10 |
| **CSV** | Format texte où chaque ligne est un enregistrement et les colonnes sont séparées par un caractère, ici le point-virgule. | 10 |
| **Biais** | Dans les contributions d'un modèle, le score moyen commun à tous, qui n'appartient à aucune variable. | 9 |
| **Bibliothèque** | Ensemble de fonctions prêtes à l'emploi, écrites par d'autres. | 3 |
| **Branche** | Copie de travail parallèle du code, dans Git. | 2 |
| **Churn** | Départ d'un abonné qui arrête son abonnement. Aussi appelé attrition ou résiliation. | 1 |
| **Cible** | La réponse que le modèle doit apprendre à prédire. Ici, 1 si l'abonné part dans les 30 jours, 0 sinon. | 5 |
| **Commit** | Enregistrement d'une version du code dans Git, accompagné d'un message. | 2 |
| **Contrat de données** | Description fixe de la forme des données acceptées : tables, colonnes, types et règles. | 4 |
| **Contrôle par force brute** | Test qui recalcule les variables de la façon la plus naïve pour vérifier le calcul rapide. | 6 |
| **Critère d'acceptation** | Condition précise et vérifiable qui doit être remplie pour qu'une étape soit terminée. | 2 |
| **Décile de risque** | Rang d'un abonné parmi dix groupes de taille égale, du plus risqué, 1, au moins risqué, 10. | 1 |
| **Destination** | Composant qui écrit la liste dans un format donné : Parquet, CSV ou JSON. On en ajoute une sans toucher au reste. | 10 |
| **Déterministe** | Se dit d'un calcul qui donne exactement le même résultat chaque fois qu'on le relance sur les mêmes données. | 10 |
| **Embargo** | Intervalle vide laissé entre l'apprentissage et le test, au moins égal à l'horizon de prédiction. | 7 |
| **Empreinte** | Signature calculée à partir de données ou d'un fichier, qui change si une seule valeur change. SHA-256 en est un algorithme courant. | 9, 10 |
| **Encodage** | Façon de représenter les caractères en octets. UTF-8 gère tous les caractères, accents compris. | 10 |
| **État** | Événement qui enregistre une valeur en vigueur, comme un revenu mensuel. Il se lit à une date, sans se sommer. | 8 |
| **Exactitude** | Part de bonnes réponses d'un modèle. Trompeuse quand l'événement à prédire est rare. | 1, 7 |
| **Export** | Fichier qui livre les résultats du pipeline à ceux qui s'en servent. Ici, la liste du lundi. | 10 |
| **Fenêtre** | Période de temps sur laquelle on résume le passé d'un abonné : 7, 30 ou 90 jours avant la date d'observation. | 6 |
| **Flux** | Événement qui arrive et se compte ou s'additionne sur une période, comme une journée d'écoute. | 8 |
| **Fuite d'information** | Situation où un modèle apprend avec une information qu'il n'aurait pas eue au moment de décider. | 6 |
| **Gradient boosting** | Technique qui enchaîne de nombreux arbres de décision, chacun corrigeant les erreurs des précédents. | 8 |
| **Graine** | Nombre qui fixe le hasard d'un programme, pour obtenir exactement le même résultat à chaque exécution. | 4 |
| **Grille d'observation** | Tableau d'apprentissage formé des couples (abonné, lundi), chaque ligne étant une photo de l'abonné ce jour-là. | 6 |
| **Horizon de prédiction** | Durée sur laquelle porte la prédiction. Ici, 30 jours. | 5 |
| **Hyperparamètre** | Réglage d'un modèle choisi avant l'apprentissage, comme le nombre d'arbres. | 8 |
| **Intégration continue** | Exécution automatique des tests et contrôles à chaque envoi de code, sur une machine neutre. | 2 |
| **JSON** | Format texte structuré, natif du web, qui range des données en paires nom et valeur. | 10 |
| **Ligne de base** | Méthode simple qui sert de point de comparaison : hasard, tri par revenu, régression logistique. | 7 |
| **Lift** | Nombre de fois qu'une méthode fait mieux qu'une méthode de référence. | 7 |
| **Lot** | Étape cohérente du projet, livrée et vérifiée avant de passer à la suivante. | 2 |
| **Marque d'ordre des octets** | Trois octets invisibles placés au début d'un fichier pour annoncer l'encodage UTF-8. Sans elle, Excel sous Windows casse les accents. | 10 |
| **Modèle** | Programme qui a appris, à partir d'exemples passés, à reconnaître une situation. | 1 |
| **Normalisation** | Mise à la même échelle des variables avant l'entraînement d'un modèle comme la régression logistique. | 7 |
| **Parquet** | Format de fichier qui range les données par colonne, conserve leur type et les compresse. | 3 |
| **Pli** | Découpage de l'historique en une période d'apprentissage et une période de test qui la suit. | 7 |
| **Precision@K** | Parmi les K premiers abonnés d'une liste, part de ceux qui sont réellement partis. | 7 |
| **Pull request** | Demande d'intégration d'une branche dans la version principale, relue avant d'être fusionnée. | 2 |
| **Purge** | Retrait des lignes d'apprentissage dont la cible se résout après le début du test. | 7 |
| **Rappel au rang K** | Parmi tous les abonnés partis, part de ceux qui figuraient dans les listes des K premiers. | 7 |
| **Registre des décisions** | Fichier qui consigne chaque choix important avec sa date, son statut et son motif. | 2 |
| **Régression logistique** | Modèle simple qui pondère les variables, les additionne et transforme la somme en score entre 0 et 1. | 7 |
| **ROC-AUC** | Mesure de la capacité à placer les abonnés qui partent au-dessus de ceux qui restent. 0,5 correspond au hasard, 1 à un classement parfait. | 7 |
| **Sentinelle anti-fuite** | Test qui supprime les événements à partir de la date d'observation et vérifie qu'aucune variable ne change. | 6 |
| **Seuil de signification** | Valeur qu'une contribution doit dépasser pour devenir un motif affiché. | 9 |
| **Taux de base** | Proportion d'exemples positifs dans les données. Ici, environ 2 % des lignes de la grille. | 7 |
| **Tendance** | Variable qui compare une fenêtre récente à la précédente, pour capter une rupture. | 6 |
| **Test** | Petit programme qui vérifie qu'un morceau de code donne le bon résultat. | 2 |
| **T0** | Date d'observation d'une ligne de la grille : le lundi où l'on se place, sans rien savoir de ce qui suit. | 6 |
| **UUID** | Identifiant de 36 caractères conçu pour ne pas se répéter. Ici, il est dérivé des entrées du calcul plutôt que tiré au hasard. | 10 |
| **Validation** | Période découpée dans les données d'apprentissage pour choisir les réglages, sans toucher au test. | 8 |
| **Valeurs de Shapley** | Répartition équitable, entre les variables, de l'écart entre le score d'un abonné et le score moyen. | 9 |
| **Variable** | Colonne qui décrit la situation d'un exemple, comme le nombre de jours d'écoute sur 30 jours. | 6 |
| **Variable d'origine** | Variable métier dont dérivent plusieurs colonnes, par exemple les fenêtres d'un même type d'événement. | 9 |

**Retour au** [sommaire du cours](README.md)
