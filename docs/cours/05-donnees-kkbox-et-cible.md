# Chapitre 5. Les vraies données et la reconstruction de la cible

> **Partie 2, préparer les données** · Lecture : 35 minutes · Prérequis : chapitre 4

## Ce que vous allez apprendre

À la fin de ce chapitre, vous saurez :

- expliquer pourquoi le choix du jeu de données conditionne tout le projet ;
- décrire les fichiers KKBox et les pièges rencontrés en les lisant ;
- tirer un échantillon correct dans un grand jeu de données ;
- définir la **cible** d'un modèle et expliquer pourquoi elle a été reconstruite, puis vérifiée.

---

## 1. Choisir ses données : la décision la plus lourde

### Pourquoi pas le jeu de données le plus connu ?

La plupart des projets de churn publics utilisent un jeu de données d'un opérateur téléphonique, publié par IBM. Il est propre, petit, facile à utiliser. Mais c'est une **photographie** : une ligne par client, à un instant donné, sans aucune date.

Avec une photographie, impossible de se placer « un lundi du passé » et de ne regarder que ce qui s'était produit avant. Or tout le projet repose sur cette capacité : fixer un horizon de prédiction, séparer passé et futur, calculer des évolutions sur 7, 30 ou 90 jours.

### Pourquoi KKBox ?

Les données de **KKBox**, service de musique en streaming, ont été publiées pour une compétition sur Kaggle. Elles possèdent ce qui manque aux jeux habituels : **une vraie dimension temporelle**.

- un historique de transactions daté ;
- un journal d'écoute quotidien ;
- une définition officielle et précise du départ d'un abonné.

> **À retenir.** Un modèle ne peut pas apprendre ce que les données ne contiennent pas. Sans dates, pas de prédiction honnête dans le temps.

## 2. Découvrir les fichiers

### Six fichiers, et des volumes impressionnants

| Fichier | Contenu | Taille décompressée |
| :--- | :--- | ---: |
| `members_v3.csv` | Informations sur les comptes | 428 Mo |
| `transactions.csv` | Historique des abonnements, première période | 1,73 Go |
| `transactions_v2.csv` | Abonnements, période récente | 115 Mo |
| `user_logs.csv` | Écoute quotidienne, première période | 30,51 Go |
| `user_logs_v2.csv` | Écoute quotidienne, période récente | 1,43 Go |
| `train_v2.csv` | Étiquette officielle de départ | 46 Mo |

Le fichier d'écoute pèse à lui seul plus de 30 Go. Impossible de le charger d'un bloc dans la mémoire d'un ordinateur ordinaire.

### Premier piège : deux générations de fichiers

On pourrait croire que les fichiers `_v2` remplacent les autres. C'est faux. La mesure montre que **74,8 %** des lignes de `transactions_v2.csv` tombent en mars 2017 : ce fichier ne contient presque que la période récente. Ne prendre que lui réduirait l'historique à un mois. Les deux générations sont donc lues et assemblées.

### Deuxième piège : des archives rangées différemment

Les fichiers arrivent compressés au format 7z. Une fois décompressés, certains se trouvent à la racine du dossier, d'autres dans un sous-dossier `data/churn_comp_refresh/`. Le code cherche donc chaque fichier là où il se trouve, plutôt que de supposer un chemin fixe.

### Troisième piège : des colonnes inutilisables

- **L'âge**, colonne `bd`, prend des valeurs allant de -7168 à 2016. **67 %** des valeurs sont hors d'un intervalle plausible. La colonne est rejetée, et ce rejet est **écrit dans le journal d'exécution**, pour que la décision reste visible.
- **Les dates d'expiration** montent jusqu'en 2036. Laissées telles quelles, elles rendraient certains abonnés éternellement actifs. Elles sont écartées explicitement.

## 3. Tirer un bon échantillon

Le projet ne travaille pas sur les millions d'abonnés, mais sur un échantillon : c'est plus rapide et suffisant pour démontrer la méthode.

Encore faut-il tirer cet échantillon au bon endroit. Le fichier des comptes contient **6,77 millions** d'abonnés, mais seuls **2,36 millions** apparaissent dans les transactions. Tirer au hasard dans le fichier des comptes donnerait environ deux tiers d'abonnés sans aucune transaction : impossible de savoir s'ils sont partis, et aucune information de paiement.

**Règle retenue :** on tire l'échantillon parmi les abonnés présents dans les transactions, puis on filtre les autres fichiers sur cet échantillon.

Le projet tire 10 000 abonnés. Après conversion au format du contrat, **8 150** sont conservés. Le code en écarte trois sortes : les abonnés absents du fichier des comptes, ceux dont la date d'inscription est illisible, et ceux dont le départ calculé précéderait l'inscription. La répartition entre ces trois causes n'a pas été mesurée.

### Lire un fichier de 30 Go avec 0,55 Go de mémoire

Le journal d'écoute est lu **par morceaux** d'un million de lignes. Dans chaque morceau, on ne garde que les lignes des abonnés de l'échantillon, puis on passe au suivant. La lecture complète prend environ 18 minutes et n'utilise jamais plus de 0,55 Go de mémoire.

## 4. Convertir au format du contrat

L'**adaptateur KKBox**, `src/churn/data/kkbox.py`, traduit chaque information vers les tables du chapitre 4. Quelques exemples :

| Donnée KKBox | Devient dans le contrat |
| :--- | :--- |
| Une transaction avec son prix affiché | un événement `facture_emise`, valeur : le prix |
| Un montant payé inférieur au prix affiché | un événement `echec_prelevement`, valeur : l'écart |
| Une transaction marquée comme annulation | un événement `annulation_abonnement` |
| Un renouvellement automatique désactivé | un événement `desactivation_renouvellement` |
| Le prix ramené à 30 jours | un événement `revenu_mensuel` |
| Une journée d'écoute | trois événements : nombre de morceaux, minutes d'écoute, taux de morceaux écoutés en entier |

Le résultat pour l'échantillon : **4 329 107 événements**, qui passent tous les contrôles de validation du chapitre 4.

Attention à une subtilité : un forfait de 410 jours payé 1 788 n'est pas un revenu mensuel de 1 788. Le prix est ramené à une base de 30 jours, soit environ 131 par mois.

## 5. La cible : ce que le modèle doit apprendre à prédire

### Définir la cible

La **cible** est la réponse que le modèle doit apprendre à deviner. Ici : *cet abonné va-t-il partir dans les 30 jours ?* Elle vaut 1 pour « oui » et 0 pour « non ».

La définition officielle de KKBox est la suivante : **un abonné est parti s'il ne renouvelle pas son abonnement dans les 30 jours qui suivent son expiration.** L'horizon de prédiction du projet est donc fixé à 30 jours pour cette source.

### Pourquoi ne pas utiliser l'étiquette fournie ?

KKBox fournit une étiquette toute faite, `train_v2.csv`. Mais elle ne porte que sur **un seul mois**, mars 2017. Or le projet a besoin de savoir, pour chaque semaine de 2015 à 2017, qui est parti ensuite. L'étiquette fournie ne suffit pas : il faut **reconstruire** la cible depuis les transactions, pour chaque période.

### Ne pas deviner la règle

Reconstruire la cible semble simple : « l'abonnement expire, et aucun renouvellement n'arrive dans les 30 jours ». En réalité, la compétition fournissait le programme officiel qui calcule l'étiquette. Le projet l'a lu et recopié plutôt que de deviner. Et cinq subtilités auraient été ratées par n'importe quelle hypothèse raisonnable, par exemple :

- seules les transactions **du mois précédent** fixent la date d'expiration prise en compte, pas tout l'historique ;
- une **annulation** peut avancer la date d'expiration ;
- quand plusieurs transactions tombent le **même jour**, elles sont traitées dans un ordre précis.

### Vérifier la reconstruction

Une cible reconstruite doit être vérifiée. Sur un échantillon de 30 000 abonnés, la cible recalculée pour mars 2017 a été comparée à l'étiquette officielle : elles concordent pour **97,03 %** des 25 702 abonnés présents dans les deux.

Un second contrôle, par l'absurde, confirme le choix de la période. Appliquée à février, la même reconstruction donne 0,03 % de départs, contre 4,52 % dans l'étiquette officielle. L'explication : nos données vont jusqu'au 31 mars, donc tous les renouvellements de février y sont visibles. Une période mal choisie se voit tout de suite.

> **Dans les coulisses.** Les 3 % d'écart restants concernent 764 abonnés : 227 pour lesquels aucun renouvellement n'est trouvé alors que l'étiquette officielle en suppose un, et 537 pour lesquels un renouvellement est trouvé mais que l'étiquette compte comme partis. L'écart n'est pas expliqué à ce jour. Il n'est pas caché pour autant : il est écrit dans `docs/dataset-kkbox.md`.

> **À retenir.** Une cible fausse rend tout le reste faux, même avec le meilleur modèle du monde. Reconstruire la cible, puis prouver la reconstruction contre une référence, est l'un des points les plus solides du projet.

## 6. Préparer le téléchargement avec soin

Deux précautions très pratiques sont nées de cette étape.

- **Le volume.** Les fichiers d'écoute pèsent près de 8 Go compressés. Sur une connexion limitée, un tel téléchargement se prévoit et se décide. Le script sépare donc un socle d'environ 1 Go, suffisant pour la cible et les données de paiement, des fichiers d'écoute, récupérés à part.
- **La reprise.** Chaque étape du script vérifie ce qui existe déjà. Un fichier déjà téléchargé n'est pas retéléchargé. Et depuis le lot 5, un fichier décompressé n'est considéré comme complet que si sa taille correspond à celle annoncée par l'archive : une décompression interrompue laisse un fichier tronqué sur le disque.

---

## À vous de jouer

**Contexte.** Voici l'historique simplifié de trois abonnés. Chaque abonnement dure 30 jours. On applique la règle : un abonné est parti s'il ne renouvelle pas dans les 30 jours suivant l'expiration.

| Abonné | Expiration | Transaction suivante |
| :--- | :--- | :--- |
| Alice | 10 mars | renouvellement le 20 mars |
| Bruno | 10 mars | renouvellement le 25 avril |
| Chloé | 10 mars | aucune transaction jusqu'à la fin des données, le 31 mars |

**Questions.**

1. Pour Alice et Bruno, la cible vaut-elle 1 ou 0 ?
2. Pour Chloé, peut-on conclure ? Que se passe-t-il si les données s'arrêtent le 31 mars ?
3. Pourquoi cette situation montre-t-elle qu'il faut faire attention à la fin de l'historique ?

<details>
<summary>Voir la correction</summary>

1. **Alice : 0.** Elle renouvelle 10 jours après l'expiration, dans le délai de 30 jours. **Bruno : 1.** Il renouvelle 46 jours après l'expiration, hors délai : selon la règle, il est parti, même s'il est revenu ensuite.

2. **On ne peut pas conclure pour Chloé.** Son délai de 30 jours court jusqu'au 9 avril, mais les données s'arrêtent le 31 mars. Elle a peut-être renouvelé le 5 avril. Sa cible n'est pas 0, elle est **inconnue**.

3. **La fin de l'historique cache des réponses.** Si l'on comptait Chloé comme « restée », on se tromperait sans le savoir. Et cette erreur toucherait toujours les périodes les plus récentes, justement celles sur lesquelles on juge un modèle. Le chapitre 6 montre comment le projet écarte ces cas plutôt que de les compter à 0.

</details>

---

## En résumé

- Le choix des données conditionne tout : sans **dimension temporelle**, pas de prédiction honnête dans le temps. D'où KKBox plutôt qu'un jeu de données sans dates.
- Les fichiers KKBox cachent plusieurs pièges : **deux générations** de fichiers à assembler, des **chemins** différents, des **colonnes aberrantes** rejetées explicitement.
- L'**échantillon** se tire parmi les abonnés qui ont des transactions. Les gros fichiers se lisent **par morceaux**.
- L'**adaptateur** convertit chaque donnée KKBox au format du contrat : 4 329 107 événements pour 8 150 abonnés.
- La **cible** est reconstruite depuis les transactions, en recopiant la règle officielle, puis **vérifiée** : 97,03 % de concordance avec l'étiquette officielle.

**Chapitre précédent :** [4. Le contrat de données](04-contrat-de-donnees.md) · **Chapitre suivant :** [6. Construire le tableau d'apprentissage sans tricher avec le temps](06-tableau-apprentissage.md)
