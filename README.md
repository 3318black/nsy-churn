# nsy-churn

Moteur de priorisation des appels de rétention pour un service par abonnement. Chaque lundi, il classe les abonnés selon leur risque de partir dans les 30 jours, et donne pour chacun jusqu'à trois motifs sur lesquels un conseiller peut agir.

> **En bref.** Une équipe peut appeler 50 abonnés par semaine. Sur des semaines passées de KKBox, un service de musique en streaming, le modèle en désigne en moyenne **14 qui partent réellement dans les 30 jours**, contre 7 pour une régression logistique et 4 pour un tri par revenu. Mesure sur quatre périodes de test que le modèle n'a jamais vues.
>
> [Application en ligne](#7-application-en-ligne-et-reproduction) · [Cours pour débutant](docs/cours/README.md) · [Résultats détaillés](docs/resultats.md)

## 1. Le problème et la cible

### Le problème

Un service par abonnement perd chaque mois une partie de ses abonnés. Une équipe de rétention peut en appeler quelques dizaines par semaine, pas tous. La question métier est donc un **ordre de priorité** : lesquels appeler d'abord, et que leur dire ?

Le projet livre chaque lundi :

- la **liste des abonnés classés** par risque, avec leur rang et leur décile, les 50 premiers étant ceux de la semaine ;
- jusqu'à **trois motifs** par abonné, choisis parmi les signaux sur lesquels on peut agir, avec l'**action conseillée** ;
- une **interface web** en lecture seule pour parcourir la liste, la fiche d'un abonné et la performance du modèle.

La capacité de 50 appels par semaine est une hypothèse de démonstration, fixée dans la configuration.

### La cible, exactement

Chaque ligne d'apprentissage est un couple `(abonné, T0)`, où `T0` est un lundi. Tout ce qui décrit l'abonné est calculé avec les seuls événements strictement antérieurs à `T0`.

- **`y = 1`** si l'abonnement de l'abonné expire dans les 30 jours qui suivent `T0`, soit dans `]T0, T0 + 30 jours]`, et qu'il n'est pas renouvelé dans les 30 jours suivant cette expiration. C'est la définition officielle du churn KKBox, reconstruite depuis les transactions à partir du programme d'étiquetage fourni par la compétition. **`y = 0`** sinon.
- **Éligibilité.** Un couple n'existe que si, à `T0`, le départ de l'abonné n'est pas encore constaté, son ancienneté atteint 60 jours, il a au moins une transaction antérieure et le journal couvre 90 jours d'historique.
- **Réponse connue.** La réponse d'un couple n'est constatée qu'à `T0 + 60 jours` : 30 jours d'horizon, puis 30 jours pour vérifier l'absence de renouvellement. Un couple dont la réponse n'est pas encore constatée à la fin des données est écarté, jamais compté à zéro.

## 2. Les données

La démonstration repose sur le jeu **KKBox WSDM Churn Prediction Challenge**, publié sur Kaggle.

**Pourquoi ce jeu.** La plupart des projets de churn publics utilisent le jeu Telco d'IBM : une photographie sans axe temporel, qui rend impossibles l'horizon de prédiction, l'embargo et la mesure semaine par semaine. KKBox offre ce qui manque : deux ans de transactions datées, des journaux d'écoute quotidiens et un churn défini contractuellement.

**Ce qui est utilisé.** Le référentiel compte 6,77 millions de comptes, dont 2,36 millions apparaissent dans les transactions. Un échantillon de 10 000 comptes est tiré parmi ces derniers, dont 8 150 sont projetés sur le contrat de données, avec leurs transactions et leur journal d'écoute complet : 4 329 107 événements de janvier 2015 à mars 2017.

**La cible est vérifiée.** Reconstruite pour mars 2017, elle concorde avec l'étiquette officielle de la compétition pour 97,03 % des 25 702 comptes communs. Les 3 % d'écart restants ne sont pas expliqués, et ils sont documentés.

**Deux sources, deux rôles.** Un générateur de données simulées alimente les tests automatisés. Aucun chiffre de performance n'est tiré de ces données, décisions D2 et D14.

Les données brutes ne sont pas versionnées, et l'application en ligne ne publie aucune donnée individuelle KKBox, décision D22.

## 3. Le protocole de validation

**Sans fuite d'information.** Trois tests protègent la règle « strictement avant `T0` » :

- une **sentinelle** supprime tous les événements à partir de `T0` et vérifie qu'aucune variable ne change ;
- un **contrôle par force brute** recalcule les variables de fenêtre de la façon la plus naïve et les compare au calcul rapide. Il a détecté 10,5 % de lignes fausses lors d'une mesure préparatoire ;
- un test réécrit les colonnes du référentiel que la grille n'utilise pas, et vérifie que rien ne bouge. Le revenu d'un couple est lu dans le journal à `T0`, jamais dans le référentiel, décision D18.

**Un découpage dans le temps.** Les dates sont coupées en quatre plis chronologiques, avec une fenêtre d'apprentissage qui s'agrandit, soit 76 semaines de test au total.

**L'embargo, en trois phrases.** Chaque ligne d'apprentissage porte une réponse qui n'est connue que 60 jours après sa date. Si l'apprentissage s'arrêtait la veille du test, les réponses de ses dernières lignes se joueraient pendant la période de test, et le modèle apprendrait des départs qu'il doit justement prédire. On laisse donc 60 jours vides entre apprentissage et test, et on retire toute ligne d'apprentissage dont la réponse est constatée après le début du test.

**La métrique : Precision@50 par semaine.** Pour chaque lundi de test, on prend les 50 abonnés éligibles les mieux classés, et on mesure la part de ceux qui partent réellement dans les 30 jours. Cette précision est moyennée sur les semaines de test de chaque pli, puis sur les quatre plis, avec son écart type entre plis. Un top 50 calculé sur toute l'année ne correspondrait à aucune décision réelle. Métriques secondaires : le rappel au rang 50, le lift contre le tri par revenu, et le ROC-AUC, pour information seulement, décision D5.

**Les lignes de base**, mesurées sur les mêmes semaines :

| Ligne de base | Question |
| :--- | :--- |
| Hasard | La métrique se comporte-t-elle normalement ? Elle doit retomber sur le taux de départ, 1,9 %. |
| Tri par revenu en vigueur | Fait-on mieux qu'un conseiller sans outil, qui appelle d'abord les abonnés qui paient le plus ? |
| Régression logistique | Un modèle à arbres fait-il mieux qu'un modèle linéaire classique ? |
| Régression logistique réglée | Et mieux qu'un modèle linéaire bien préparé : compression logarithmique des variables et régularisation choisie ? |

**Le choix des réglages ne voit jamais le test.** Les réglages d'XGBoost, parmi 24 combinaisons, et la force de régularisation de la régression logistique réglée sont choisis sur une validation découpée à l'intérieur des seules lignes d'apprentissage, avec le même embargo. Quand cette validation est impossible, le premier réglage est gardé, et le rapport le dit.

## 4. Les résultats

**Source : KKBox WSDM Churn Prediction Challenge.** Mesure du 14 septembre 2026, 8 150 comptes, 400 059 couples et 8 881 départs, 4 plis chronologiques. Décision D24.

| Classement | Precision@50 | Départs sur 50 appels | ROC-AUC | Lift contre le revenu |
| :--- | ---: | ---: | ---: | ---: |
| Hasard | 0,019 | 1 | 0,500 | 0,21 |
| Tri par revenu en vigueur | 0,089 | 4 | 0,683 | 1,00 |
| Régression logistique réglée | 0,118 | 6 | 0,736 | 1,33 |
| Régression logistique | 0,135 | 7 | 0,715 | 1,51 |
| **XGBoost** | **0,274** | **14** | **0,815** | **3,08** |

Ce qu'il faut en retenir :

- **XGBoost bat toutes les lignes de base sur chacun des quatre plis.** Par pli, sa Precision@50 vaut 0,165, 0,316, 0,341 et 0,273. Il dépasse à la fois le hasard, le tri par revenu et les deux régressions logistiques sur 64 des 76 semaines de test.
- **Le gain du modèle est établi.** À variables financières égales, il gagne +0,133 sur la régression logistique, positif sur les quatre plis, avec un écart type de 0,070.
- **Le premier pli est le plus faible, et on sait pourquoi.** Son apprentissage est trop court pour la validation interne une fois l'embargo de 60 jours appliqué. Le modèle y garde donc le réglage le plus simple de sa grille, et y vaut 0,165. Sur les trois plis suivants, il vaut 0,310 en moyenne.
- **La régression logistique réglée ne fait pas mieux en tête de liste.** Son ROC-AUC est meilleur, mais elle trouve moins de départs parmi les 50 premiers.
- **L'apport du journal d'écoute n'est pas établi** : +0,008 de Precision@50, positif sur deux plis sur quatre.

**Une correction avant publication.** En écrivant la définition exacte de la cible pour ce README, un défaut est apparu. Une résiliation KKBox était comptée à sa date d'expiration, alors qu'elle n'est constatée que 30 jours plus tard. L'embargo était donc trop court, et la grille écartait des abonnés encore libres de renouveler. Après correction, la Precision@50 d'XGBoost est passée de 0,323 à 0,274. C'est le chiffre corrigé qui est publié, décision D24.

## 5. L'explicabilité

**D'où viennent les motifs.** XGBoost calcule nativement la contribution de chaque variable au score d'un abonné, selon la méthode des valeurs de Shapley pour les arbres. Ces contributions sont additionnées par **variable d'origine** : les fenêtres de 7, 30 et 90 jours d'un même signal et leur tendance ne forment qu'un seul motif. Un motif n'est retenu que si sa contribution dépasse un **seuil de signification**, fixé à l'entraînement au 75e centile des contributions en valeur absolue, soit 0,1538 pour le modèle actuel.

**Seulement ce sur quoi on peut agir.** L'ancienneté et le revenu comptent dans le score, mais n'occupent jamais une case de motif : on ne retient pas un abonné en changeant son ancienneté, décision D19. Un abonné sans motif significatif n'en reçoit aucun, plutôt qu'un motif inventé.

**Des libellés écrits à l'avance.** Le nom de chaque motif et l'action conseillée viennent d'un dictionnaire statique, `config/feature_mapping.yaml`. Aucun texte n'est généré.

**Exemple réel** : l'abonné classé premier sur la liste KKBox du lundi 27 mars 2017, sans son identifiant.

| Motif | Action conseillée |
| :--- | :--- |
| [FINANCE] Évolution récente de la facturation | Vérifier un changement de formule ou une interruption de facturation |
| [FINANCE] Annulations d'abonnement | Reprendre l'historique des annulations |
| [FINANCE] Évolution récente des annulations d'abonnement | Reprendre l'historique des annulations |

Sur les 5 165 abonnés de cette liste, 36,2 % n'ont aucun motif significatif, et chacun des 50 premiers en a trois.

## 6. Les limites assumées

- **La capacité de 50 appels est hypothétique.** KKBox n'a pas d'équipe de rétention.
- **L'échantillon est modeste** : 8 150 comptes sur les 2,36 millions disponibles.
- **Quatre plis seulement.** Les petits écarts, comme l'apport du journal d'écoute, ne se distinguent pas du bruit. Le premier pli tourne sans sélection des réglages.
- **3 % d'écart inexpliqué** entre la cible reconstruite et l'étiquette officielle.
- **Les scores ne sont pas des probabilités.** La liste se lit par rang et par décile, et aucun étage de calibration n'existe, décision D6.
- **Les motifs nomment un signal sans en donner le sens** : « Évolution récente de la facturation » ne dit pas si elle monte ou baisse.
- **Un revenu inconnu vaut zéro** pour 23,5 % des abonnés de la liste, l'extrait ne remontant pas avant 2015.
- **Une trace de la date de résiliation brute demeure.** L'adaptateur KKBox retire du journal les événements postérieurs à l'expiration d'un abonné qui ne renouvelle pas, y compris pendant les 30 jours où personne ne le sait encore. L'effet n'est pas mesuré.
- **Des semaines difficiles** : la pire semaine d'XGBoost vaut 0,02, et le tri par revenu tombe à zéro deux semaines. Ces écarts ne sont pas expliqués.
- **Le CSV est réglé pour un Excel en français** : point-virgule et virgule décimale.
- **Hors périmètre** : suivi de la performance en production, réentraînement planifié, synchronisation avec un outil de gestion client, API.

## 7. Application en ligne et reproduction

### Application en ligne

Adresse : publication en cours.

L'application compte quatre écrans : la présentation du projet, la liste du lundi, la fiche d'un abonné et la performance du modèle. En ligne, l'accueil et l'écran de performance montrent les vrais résultats KKBox, qui ne sont que des moyennes. La liste et la fiche tournent sur des données simulées, sous un bandeau qui le signale. L'application lit le dossier `demo/`, reconstruit par `uv run python scripts/build_demo.py`.

### Le cours en ligne

Le cours pour débutant a sa propre application, `app/cours_app.py` : un menu qui garde la progression, des quiz corrigés avec l'explication de chaque réponse, et un glossaire où chercher un terme. Elle lit directement les fichiers de `docs/cours`, décision D25.

Adresse : publication en cours.

### Reproduire

```bash
uv sync                                                    # versions exactes de uv.lock
uv run pytest                                              # tests automatisés
uv run python scripts/download_kkbox.py --with-logs --sample-size 10000
uv run python scripts/train_model.py --source kkbox        # évaluation et modèle
uv run python -m churn.pipeline.run_scoring --source kkbox  # liste du lundi
uv run streamlit run app/streamlit_app.py                  # interface, sur http://localhost:8501
uv run streamlit run app/cours_app.py                      # le cours, sans aucune donnée
```

Le téléchargement demande un compte Kaggle, l'acceptation des règles de la compétition et un jeton d'API, détaillés dans `docs/dataset-kkbox.md`. Comptez près de 9 Go d'archives avec le journal d'écoute, une vingtaine de minutes pour préparer l'échantillon, et un quart d'heure pour l'évaluation et le modèle final. La graine du fichier de configuration fixe le hasard, et l'export est déterministe : deux exécutions produisent les mêmes fichiers.

### Publier l'application

Sur Streamlit Community Cloud, avec le compte GitHub propriétaire du dépôt :

1. sur `share.streamlit.io`, choisir « Create app » ;
2. dépôt `3318black/nsy-churn`, branche `main`, fichier `app/streamlit_app.py` ;
3. dans « Advanced settings », garder Python 3.12 et saisir le secret suivant :

   ```toml
   NSY_CHURN_ROOT = "demo"
   ```

4. déployer, puis reporter l'adresse obtenue en tête de cette section ;
5. pour le cours, recommencer avec le fichier `app/cours_app.py`, sans aucun secret, et reporter son adresse sous « Le cours en ligne ».

## Documentation

| Fichier | Contenu |
| :--- | :--- |
| `docs/cours/` | Cours pour débutant : l'application, la méthode, les outils, puis chaque étape de construction, avec exercices et quiz. |
| `docs/resultats.md` | Mesures qui engagent le projet, datées, avec leur source et leurs limites. |
| `docs/decisions.md` | Décisions closes, de D1 à D24, et points ouverts. |
| `docs/data-contract.md` | Tables d'entrée, construction du jeu d'apprentissage, règle de non-fuite, schéma de sortie. |
| `docs/dataset-kkbox.md` | Projection du jeu KKBox sur le contrat et reconstruction de la cible. |
| `docs/roadmap.md` | Les lots du projet, avec leurs critères d'acceptation. |
| `docs/revue-spec-v3.md` | Revue critique du cadrage initial et motifs des corrections. |
| `docs/stack.md` | Stack complète, versions vérifiées, pièges connus. |
| `AGENTS.md` | Manuel opératoire pour contribuer au code. |

Le guide de rédaction d'`AGENTS.md` qui a servi de modèle est un support de cours externe. Il n'est pas redistribué ici.
