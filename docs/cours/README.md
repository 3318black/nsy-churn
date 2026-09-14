# Cours : construire un moteur de prédiction du churn, de A à Z

Ce cours raconte la construction complète d'une application de data science réelle, depuis l'idée de départ jusqu'au modèle qui explique ses prédictions. Il ne se contente pas de montrer le code : il explique **pourquoi** chaque choix a été fait, **comment** il a été réalisé, et **quelles erreurs** ont été commises en chemin.

## Pour qui ?

Pour un débutant. Vous n'avez pas besoin de savoir programmer ni de connaître le machine learning. Il suffit de savoir ce qu'est un tableau, comme une feuille Excel. Chaque terme technique est expliqué la première fois qu'il apparaît, et le [glossaire](glossaire.md) les rassemble tous.

Si vous connaissez déjà un peu Python, vous pourrez aller plus loin en ouvrant les fichiers de code cités. Ce n'est jamais obligatoire pour suivre.

## Ce que vous allez apprendre

À la fin du cours, vous saurez :

- expliquer ce qu'est le churn et comment une entreprise peut le prévoir ;
- décrire la méthode qui permet de mener un projet de data science de façon rigoureuse ;
- préparer des données réelles pour qu'un modèle puisse en apprendre ;
- reconnaître les pièges qui font croire à un bon modèle alors qu'il ne l'est pas ;
- évaluer honnêtement un modèle et le comparer à des méthodes simples ;
- expliquer une prédiction à quelqu'un qui n'est pas technicien.

## Comment suivre ce cours

Lisez les chapitres dans l'ordre : chacun s'appuie sur le précédent.

Chaque chapitre suit la même structure :

1. **Ce que vous allez apprendre** : les objectifs du chapitre.
2. **Le contenu**, découpé en sections courtes, avec des exemples et des chiffres réels tirés du projet.
3. **À vous de jouer** : un exercice court, avec sa correction à déplier.
4. **En résumé** : l'essentiel à retenir.

Chaque partie se termine par un **quiz** pour vérifier vos acquis.

Trois types d'encadrés ponctuent le texte :

- **À retenir** : une idée essentielle ;
- **Attention** : un piège fréquent ;
- **Dans les coulisses** : ce qui s'est réellement passé pendant le projet, erreurs comprises.

Durée totale estimée des parties écrites : environ 5 heures.

## Plan du cours

### Partie 1. Découvrir le projet

| Chapitre | Durée |
| :--- | ---: |
| [1. L'application : ce qu'elle fait et pourquoi elle existe](01-application.md) | 20 min |
| [2. La méthode : construire un projet de data science pas à pas](02-methode.md) | 30 min |
| [3. Les outils : les choix technologiques expliqués](03-outils.md) | 30 min |
| [Quiz de la partie 1](quiz-partie-1.md) | 10 min |

### Partie 2. Préparer les données

| Chapitre | Durée |
| :--- | ---: |
| [4. Le contrat de données et les données d'entraînement fictives](04-contrat-de-donnees.md) | 30 min |
| [5. Les vraies données et la reconstruction de la cible](05-donnees-kkbox-et-cible.md) | 35 min |
| [6. Construire le tableau d'apprentissage sans tricher avec le temps](06-tableau-apprentissage.md) | 35 min |
| [Quiz de la partie 2](quiz-partie-2.md) | 10 min |

### Partie 3. Mesurer et prédire

| Chapitre | Durée |
| :--- | ---: |
| [7. Évaluer honnêtement : le protocole et les lignes de base](07-evaluer-honnetement.md) | 35 min |
| [8. Entraîner le modèle sans se tromper soi-même](08-entrainer-le-modele.md) | 35 min |
| [9. Expliquer chaque prédiction](09-expliquer-les-predictions.md) | 30 min |
| [Quiz de la partie 3](quiz-partie-3.md) | 10 min |

### Partie 4. Restituer les résultats

| Chapitre | Durée |
| :--- | ---: |
| [10. Livrer la liste du lundi : l'export](10-livrer-la-liste.md) | 30 min |
| [11. Montrer les résultats : l'interface web](11-interface-web.md) | 30 min |

Chapitre à venir avec le lot 8 : la présentation du projet, puis le quiz de la partie 4.

### Annexe

- [Glossaire](glossaire.md)

## Méthode pédagogique

La structure du cours s'inspire de la méthode d'OpenClassrooms : un cours découpé en parties de trois à cinq chapitres, des objectifs annoncés par des verbes d'action, des activités d'application corrigées, et un quiz en fin de partie.

- [Structurez votre cours avec un plan détaillé](https://openclassrooms.com/fr/courses/4669216-realisez-un-cours-en-ligne/5174161-structurez-votre-cours-avec-un-plan-detaille)
- [Structurez votre plan, créer un cours sur OpenClassrooms](https://openclassrooms.com/fr/courses/2067781-creez-un-cours-sur-openclassrooms/2724353-structurez-votre-plan)
- [Concevez un exercice d'application](https://openclassrooms.com/en/courses/4669166-concevez-des-activites-pedagogiques-engageantes/5275531-concevez-un-exercice-d-application)

## Règles d'écriture, pour qui complète ce cours

- Un chapitre par avancement significatif du projet, ajouté à la partie qui lui correspond, et livré dans la même pull request que le code.
- Partir du problème concret avant la technique, et définir chaque terme à sa première apparition. Ajouter tout nouveau terme au glossaire.
- N'utiliser que des chiffres réellement mesurés sur le projet. Un exemple inventé est présenté comme tel.
- Raconter les erreurs et leur détection : c'est souvent là que se trouve la leçon.
- Garder la structure commune : objectifs, contenu, exercice corrigé, résumé.
