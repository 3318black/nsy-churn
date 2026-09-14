# Chapitre 4. Le contrat de données et les données d'entraînement fictives

> **Partie 2, préparer les données** · Lecture : 30 minutes · Prérequis : partie 1

## Ce que vous allez apprendre

À la fin de ce chapitre, vous saurez :

- expliquer ce qu'est un contrat de données et pourquoi on l'écrit en premier ;
- décrire les deux tables que l'application attend en entrée ;
- distinguer une colonne obligatoire, une colonne facultative et une valeur manquante ;
- expliquer à quoi servent des données fictives, et pourquoi elles ne mesurent jamais la qualité d'un modèle.

---

## 1. Le problème : des données qui arrivent sous mille formes

Une entreprise stocke ses données comme elle peut : un fichier d'abonnements ici, un journal d'utilisation là, des noms de colonnes en anglais, des dates au format américain, des identifiants différents d'un fichier à l'autre.

Si chaque calcul de l'application devait s'adapter à ces particularités, le code deviendrait vite illisible. Et le jour où les données changent de source, il faudrait tout réécrire.

## 2. La solution : un contrat de données

Un **contrat de données** fixe, une fois pour toutes, la forme exacte des données que l'application accepte : quelles tables, quelles colonnes, quels types, et quelles règles doivent toujours être respectées.

Pensez à une prise électrique. Un appareil fabriqué au Japon ou en Allemagne se branche sur la même prise grâce à un adaptateur. Ici, c'est pareil : chaque source de données passe par un **adaptateur** qui la convertit au format du contrat. Le reste de l'application ne connaît que ce format.

> **À retenir.** Le contrat ne se plie jamais à une source. C'est la source qui s'adapte au contrat. Une source qui ne parvient pas à le respecter a un adaptateur incomplet, et on corrige l'adaptateur, pas le contrat.

Le contrat est écrit dans `docs/data-contract.md`, puis traduit en code dans `src/churn/data/schemas.py`.

## 3. Les deux tables du contrat

### La table `accounts` : un compte par ligne

Elle décrit chaque abonné.

| Colonne | Contenu | Exemple |
| :--- | :--- | :--- |
| `client_id` | Identifiant unique du compte | `C000317` |
| `date_debut_contrat` | Date d'entrée du compte | 2015-03-01 |
| `date_resiliation` | Date de départ, vide si le compte est toujours actif | 2016-09-15, ou vide |
| `type_contrat` | Rythme de facturation | `mensuel` |
| `mrr` | Revenu mensuel du compte, en euros | 149,00 |
| `segment` | Catégorie de compte | `PME` |
| `canal_acquisition` | Canal par lequel le compte est arrivé | `direct` |
| `nb_licences` | Nombre de places souscrites | 3 |

La colonne `date_resiliation` est la source de l'étiquette « parti ou resté ».

### La table `events` : un événement daté par ligne

Elle raconte tout ce qui arrive aux abonnés, dans l'ordre du temps.

| Colonne | Contenu | Exemple |
| :--- | :--- | :--- |
| `client_id` | Le compte concerné | `C000317` |
| `event_ts` | Date et heure précises, avec fuseau horaire | 2016-05-12 14:03 UTC |
| `event_type` | Nature de l'événement | `facture_emise` |
| `event_value` | Valeur associée | 149,00 |

Pourquoi un journal d'événements plutôt qu'un tableau déjà résumé ? Parce qu'un journal permet de répondre à n'importe quelle question du type « que s'est-il passé avant telle date ? ». Un résumé figé, comme « nombre de factures au total », ne le permet pas. Le chapitre 6 montre à quel point c'est essentiel.

### La liste fermée des types d'événements

Le champ `event_type` n'accepte que des valeurs prévues à l'avance. Il y en a treize, réparties en familles :

| Famille | Types d'événements |
| :--- | :--- |
| Utilisation du service, `PRODUCT` | connexion, usage d'une fonction clé, taux de complétion, désactivation d'une fonctionnalité |
| Assistance, `SUPPORT` | ticket ouvert, ticket résolu |
| Paiement, `FINANCE` | facture émise, facture payée, échec de prélèvement, annulation, désactivation du renouvellement, revenu mensuel |
| Relation commerciale, `COMMERCIAL` | contact commercial |

Une valeur inconnue est une **erreur**, jamais un rejet silencieux. Ajouter un type est une modification du contrat, décidée et documentée.

Aucune source ne remplit toute la liste. KKBox n'a ni tickets d'assistance ni contacts commerciaux ; une entreprise de logiciel n'aurait pas de taux d'écoute complète. Ce n'est pas un problème : une famille absente produit simplement moins de variables.

## 4. Trois notions à ne pas confondre

Le contrat distingue trois situations qui se ressemblent.

- **Une colonne obligatoire** doit exister dans la table. Si `client_id` manque, la source est refusée.
- **Une colonne facultative** peut ne pas exister. La seule du contrat est `nb_licences` : KKBox ne la fournit pas, et reste pourtant conforme.
- **Une valeur manquante** est une case vide dans une colonne qui existe. `date_resiliation` est vide pour un compte actif, et c'est normal. `client_id`, en revanche, ne peut jamais être vide.

## 5. Contrôler les données : la validation

Écrire des règles ne suffit pas, il faut les vérifier. Le module `src/churn/data/validate.py` contrôle chaque règle du contrat, par exemple :

- chaque `client_id` est unique dans `accounts` ;
- tout compte cité dans `events` existe dans `accounts` ;
- aucun événement n'est daté avant l'entrée du compte, ni après son départ ;
- une date de départ est toujours postérieure à la date d'entrée ;
- chaque date porte un fuseau horaire.

Trois principes guident ce contrôle.

1. **Un échec est bloquant et jamais silencieux.** Une ligne fautive est signalée, jamais corrigée en douce. Corriger en silence cacherait un adaptateur défectueux derrière un calcul qui a l'air propre.
2. **Toutes les erreurs sont rapportées d'un coup.** S'arrêter à la première obligerait à relancer une fois par défaut, ce qui est impraticable sur des millions de lignes.
3. **Le rapport est lisible.** Il indique la table, la règle violée, le nombre de lignes fautives et quelques identifiants en exemple.

> **Attention.** Pourquoi exiger un fuseau horaire ? Une date sans fuseau est ambiguë : midi à Paris n'est pas midi à Taipei. Et le chapitre 6 montre qu'une seule heure de décalage suffit à laisser passer une information du futur.

## 6. Des données fictives pour tester

### Pourquoi en fabriquer ?

Pour tester le code, il faut des données. Les données réelles sont lourdes, absentes de la machine d'intégration continue, et ne contiennent pas forcément les cas difficiles qu'on veut vérifier. Le projet possède donc un **générateur de données fictives**, `src/churn/data/synthetic.py`.

Ses avantages :

- **rapide** : quelques secondes pour quelques centaines de comptes ;
- **reproductible** : avec la même **graine**, un nombre qui fixe le hasard, il produit exactement les mêmes données à chaque fois ;
- **exigeant** : il fabrique volontairement les cas qui piègent le code.

### Il produit des événements, pas des résumés

Le générateur écrit les deux tables du contrat, rien d'autre. Il ne produit jamais une colonne toute faite comme « nombre de tickets sur 30 jours ». Sinon, il supprimerait précisément l'étape la plus risquée du projet : calculer ces résumés sans regarder dans le futur. C'est la décision D3.

### Un monde volontairement difficile

Un générateur trop simple fabrique un problème trop facile, et un modèle qui paraît brillant. Celui-ci introduit exprès des difficultés, réglées dans `config/config.yaml` :

| Difficulté | Réglage | Pourquoi |
| :--- | :--- | :--- |
| Départs sans aucun signe avant-coureur | 25 % des départs | Aucun modèle ne peut les prévoir. Ils fixent un plafond réaliste. |
| Faux signaux | 12 % des comptes qui restent | Ils montrent des signes inquiétants, mais ne partent pas. |
| Horodatages en double | 10 % des événements | Plusieurs événements au même instant. Ce cas a provoqué 10,5 % de lignes fausses lors d'une mesure, chapitre 6. |
| Valeurs manquantes et trous | 5 % | Aucune source réelle n'est complète. |

Les comptes qui partent suivent l'un de trois profils : dégradation de l'assistance, baisse d'utilisation, ou incidents de paiement.

### La règle d'or : jamais une mesure de performance

> **À retenir.** Un résultat obtenu sur des données fictives ne dit **rien** de la qualité réelle d'un modèle. C'est la décision D2.

Pourquoi ? Parce que le générateur est écrit par la même personne que le modèle. Il contient les relations que le modèle va retrouver. Un bon score mesure alors la cohérence du générateur, pas la capacité à prédire.

Chaque rapport produit sur ces données porte donc en première ligne la mention *SIMULATED DATA, No performance figure holds here*.

> **Dans les coulisses.** Un graphique du lot 3 a révélé une faiblesse du générateur : les échecs de prélèvement n'étaient émis que chez les comptes sur le point de partir. Sur ces données, la famille paiement sépare presque parfaitement ceux qui partent et ceux qui restent. C'est documenté dans le code, et c'est une raison de plus de ne jamais y lire une performance.

---

## À vous de jouer

**Contexte.** Voici un petit extrait converti par un adaptateur. Les dates sont en UTC sauf mention contraire.

Table `accounts` :

| client_id | date_debut_contrat | date_resiliation |
| :--- | :--- | :--- |
| A1 | 2016-01-10 | vide |
| A2 | 2016-02-01 | 2016-01-15 |
| A1 | 2016-03-05 | vide |

Table `events` :

| client_id | event_ts | event_type |
| :--- | :--- | :--- |
| A1 | 2016-02-01 10:00 UTC | connexion |
| A3 | 2016-02-03 09:00 UTC | facture_emise |
| A1 | 2016-02-04 11:00, sans fuseau | connexion |
| A1 | 2016-02-05 12:00 UTC | promotion_envoyee |

**Question.** Trouvez les cinq violations du contrat.

<details>
<summary>Voir la correction</summary>

1. **`client_id` en double** : A1 apparaît deux fois dans `accounts`.
2. **Départ avant l'entrée** : A2 part le 15 janvier alors qu'il est entré le 1er février.
3. **Compte inconnu** : A3 apparaît dans `events` mais pas dans `accounts`.
4. **Date sans fuseau horaire** : l'événement du 4 février de A1.
5. **Type d'événement inconnu** : `promotion_envoyee` ne fait pas partie de la liste fermée.

Remarquez que la validation doit rapporter les cinq d'un coup, avec les identifiants concernés, et ne corriger aucune ligne elle-même.

</details>

---

## En résumé

- Un **contrat de données** fixe la forme exacte des données acceptées. Chaque source s'y conforme grâce à un **adaptateur**.
- Le contrat définit deux tables : **`accounts`**, un compte par ligne, et **`events`**, un journal d'événements datés.
- Les **types d'événements** forment une liste fermée de treize valeurs, répartie en familles.
- **Colonne obligatoire**, **colonne facultative** et **valeur manquante** sont trois notions différentes.
- La **validation** est bloquante, exhaustive et lisible. Elle ne corrige jamais en silence.
- Les **données fictives** servent à tester le code, avec des difficultés volontaires. Elles ne mesurent **jamais** la qualité d'un modèle.

**Chapitre précédent :** [3. Les outils](03-outils.md) · **Chapitre suivant :** [5. Les vraies données et la reconstruction de la cible](05-donnees-kkbox-et-cible.md)
