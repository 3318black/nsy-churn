# Adaptation du contrat de données au jeu KKBox

Source : `WSDM - KKBox's Churn Prediction Challenge`, Kaggle, 2017. Deux ans d'observation continue sur un service de streaming musical par abonnement.

Ce document décrit comment KKBox se projette sur le contrat de données défini dans `data-contract.md`. Le contrat ne change pas : c'est la source qui s'y conforme, par un adaptateur. Voir décision D14.

## 1. Pourquoi ce jeu et pas un autre

Il possède ce qui manque à tous les jeux de churn courants : une dimension temporelle réelle. Des logs d'écoute quotidiens, un historique de transactions daté, des attributs de compte, et un churn défini contractuellement. Le déséquilibre observé, de 6 à 7 % de churn, correspond à un cas réel et non à un jeu rééquilibré artificiellement.

Le jeu Telco d'IBM, sur lequel repose la quasi-totalité des projets de churn publics, est une photographie sans axe temporel. Il rend impossible tout ce qui fait la valeur de ce projet : l'horizon de prédiction, l'embargo, la construction de fenêtres glissantes et la Precision@K par période.

## 2. Fichiers sources et volumétrie

Tailles relevées par l'API le 7 septembre 2026. **Tous les fichiers sont livrés au format `.7z`**, et non en CSV brut ni en ZIP.

| Fichier livré | Contenu | Compressé | Décompressé |
| :--- | :--- | ---: | ---: |
| `members_v3.csv.7z` | Attributs de compte | 231 Mo | 428 Mo |
| `transactions.csv.7z` | Historique d'abonnement, première phase | 675 Mo | 1,73 Go |
| `transactions_v2.csv.7z` | Abonnements, seconde phase | 47 Mo | 115 Mo |
| `user_logs.csv.7z` | Écoute quotidienne, première phase | 6,8 Go | 30,51 Go |
| `user_logs_v2.csv.7z` | Écoute quotidienne, seconde phase | 654 Mo | 1,43 Go |
| `train_v2.csv.7z` | Étiquette officielle de churn | 31 Mo | 46 Mo |

Les six archives ont été téléchargées et leur intégrité vérifiée le 8 septembre 2026. Tailles décompressées relevées dans les métadonnées des archives.

**Le journal complet occupe 30,5 Go une fois décompressé.** Il ne doit être extrait qu'une seule fois, filtré immédiatement sur l'échantillon de comptes, écrit en Parquet, puis le CSV supprimé. Conserver 30 Go de texte brut à côté d'un Parquet filtré n'apporte rien et complique les relances.

### 2.1 Deux générations de fichiers, et pourquoi les deux sont nécessaires

La compétition s'est déroulée en deux phases. Les fichiers suffixés `_v2` ne remplacent pas les autres, ils les complètent sur la période récente.

Mesure faite sur `transactions_v2.csv` le 7 septembre 2026 : le fichier couvre bien 2015 à 2017, mais **74,8 % de ses 1 431 009 lignes tombent en mars 2017**, et seules 361 187 transactions lui sont antérieures. Il ne porte donc pas l'historique.

Conséquence : construire une grille d'observation sur deux ans exige `transactions.csv` **et** `transactions_v2.csv`. La même logique vaut pour les journaux d'écoute. Ne prendre que les fichiers `_v2` réduirait l'historique à un mois et viderait le protocole de son sens.

### 2.2 Décompression

Aucun décompresseur 7z n'est installé sur le poste, et Python n'en gère pas nativement. La dépendance `py7zr` est ajoutée au groupe de développement.

Mesure de référence : `train_v2.csv.7z`, 33 Mo compressés vers 45,6 Mo, décompressé en 3,1 secondes.

**Piège d'arborescence, et il n'est pas uniforme.** Les archives des fichiers suffixés `_v2` portent un chemin interne `data/churn_comp_refresh/`, les autres non. Après extraction vers `data/raw`, on obtient donc :

```text
data/raw/members_v3.csv                              <- racine
data/raw/transactions.csv                            <- racine
data/raw/data/churn_comp_refresh/transactions_v2.csv <- sous-dossier
data/raw/data/churn_comp_refresh/train_v2.csv        <- sous-dossier
```

Le script de téléchargement doit aplatir cette arborescence. Coder en dur `data/raw/<fichier>.csv` fonctionnerait pour la moitié des fichiers seulement.

Temps de décompression mesurés : `members_v3` de 242 Mo vers 428 Mo en 22 secondes, `transactions` de 708 Mo vers 1 729 Mo en 70 secondes.

### 2.3 Chiffres de référence mesurés le 7 septembre 2026

Ces valeurs servent de contrôle : un écart important lors du chargement signale une erreur de lecture, et non une variation des données.

| Table | Lignes | Comptes uniques | Période |
| :--- | ---: | ---: | :--- |
| `members_v3.csv` | 6 769 473 | 6 769 473 | inscriptions du 2004-03-26 au 2017-04-29 |
| `transactions.csv` | 21 547 746 | 2 363 626 | 2015-01-01 au 2017-02-28 |
| `transactions_v2.csv` | 1 431 009 | 1 197 050 | 2015-01-01 au 2017-03-31 |
| `train_v2.csv` | 970 960 | 970 960 | étiquette de mars 2017, churn à 8,99 % |

**Les deux fichiers ne se recouvrent pas par des doublons.** Vérification faite sur un échantillon de 8 000 comptes : les 1 315 lignes de `transactions_v2.csv` antérieures au 28 février 2017 ne sont identiques à aucune ligne de `transactions.csv`. Ce sont des transactions que le premier fichier ne contient pas. La concaténation est donc obligatoire, et le dédoublonnage doit rester strictement exact.

**L'union des deux fichiers de transactions couvre 27 mois**, de janvier 2015 à mars 2017. C'est la profondeur réelle disponible pour la grille d'observation. `transactions.csv` s'arrête au 28 février 2017 et `transactions_v2.csv` prend le relais : les deux sont complémentaires, avec un recouvrement de 361 187 lignes antérieures à mars 2017 qu'il faut dédupliquer.

### Conséquence sur l'échantillonnage

Le référentiel compte 6,77 millions de comptes, mais **seuls 2,36 millions apparaissent dans les transactions**. Tirer l'échantillon dans `members_v3.csv` produirait donc environ deux tiers de comptes sans aucune transaction, donc sans cible calculable et sans variable financière.

**Règle** : l'échantillon se tire parmi les comptes présents dans les transactions, puis le référentiel est filtré sur cet échantillon. Jamais l'inverse.

### La colonne `bd` est confirmée inutilisable

Mesure sur les 6 769 473 lignes : valeurs allant de -7168 à 2016, et **4 546 765 valeurs hors de l'intervalle [10, 100], soit 67 % du fichier**. Elle est rejetée, avec une trace dans le journal.

À noter également, `registered_via` contient la valeur `-1`, qui encode une modalité inconnue et doit être traitée comme telle plutôt que comme un code de canal.

### 2.4 Ordre de récupération recommandé

Le débit observé est d'environ 5 Mo par seconde.

**Socle, environ 1 Go et quatre minutes** : `train_v2.csv.7z`, `transactions.csv.7z`, `transactions_v2.csv.7z`, `members_v3.csv.7z`.

Ce socle suffit à reconstruire la cible sur toute la période, à la valider contre l'étiquette officielle, à construire l'intégralité des variables `FINANCE` et à entraîner un premier modèle complet. Autrement dit, il couvre le critère central du lot 2 et permet d'aller jusqu'au lot 6.

**Enrichissement, environ 7,8 Go et une demi-heure** : `user_logs_v2.csv.7z` puis `user_logs.csv.7z`. Ils apportent les variables `PRODUCT`, dont le taux de complétion qui porte le signal le plus intéressant du jeu. Ils ne conditionnent aucun critère d'acceptation antérieur au lot 3.

**Échantillonnage obligatoire.** Un tirage aléatoire de comptes est effectué en premier, parmi les comptes présents dans les transactions comme expliqué en 2.3, puis les fichiers sont filtrés sur cet échantillon. Les journaux d'écoute se lisent par morceaux, jamais en une fois. La taille d'échantillon par défaut est fixée dans `config.yaml`, à 50 000 comptes.

**Les données ne sont jamais versionnées.** Elles restent sous `data/raw/`, exclu par `.gitignore`. Les règles de la compétition encadrent leur usage et n'autorisent pas la redistribution.

## 3. Projection sur la table `accounts`

| Colonne du contrat | Source KKBox | Transformation |
| :--- | :--- | :--- |
| `client_id` | `msno` | Reprise directe, identifiant déjà anonymisé |
| `date_debut_contrat` | `registration_init_time` | Entier `AAAAMMJJ` à convertir en date |
| `date_resiliation` | dérivée des transactions | Voir section 5 |
| `type_contrat` | `payment_plan_days` | 30 jours donne `mensuel`, 90 donne `trimestriel`, 365 et plus donne `annuel` |
| `mrr` | `plan_list_price`, `payment_plan_days` | Ramené à une base de 30 jours |
| `segment` | `city` | Codes de ville traités comme catégorie, sans interprétation géographique |
| `canal_acquisition` | `registered_via` | Codes de canal repris tels quels |
| `nb_licences` | absent | Colonne optionnelle, non renseignée pour cette source |

**Le contrat distingue désormais un noyau obligatoire et des colonnes optionnelles.** `nb_licences` devient optionnelle. Une source qui ne la fournit pas reste conforme, et les variables qui en dépendent sont simplement absentes de la matrice.

**Piège à traiter :** la colonne `bd`, censée porter l'âge, contient des valeurs aberrantes notoires, négatives ou supérieures à 1000. Elle n'est pas reprise. La rejeter explicitement, plutôt que l'ignorer en silence, fait partie du travail attendu.

**Second piège, mesuré :** `membership_expire_date` monte jusqu'à `20361015`. Sur le seul fichier `transactions_v2.csv`, 9 718 lignes portent une expiration postérieure à fin 2018. Ces valeurs doivent être bornées ou écartées explicitement, faute de quoi elles rendraient les comptes concernés éternellement actifs et fausseraient la cible.

## 4. Projection sur la table `events`

| `event_type` | Source | `event_value` |
| :--- | :--- | :--- |
| `connexion` | `user_logs`, une ligne par jour actif | `num_unq`, morceaux uniques écoutés |
| `usage_module_cle` | `user_logs` | `total_secs`, durée d'écoute du jour |
| `taux_completion` | `user_logs` | `num_100 / (num_25 + num_50 + num_75 + num_985 + num_100)` |
| `facture_emise` | `transactions` | `plan_list_price` |
| `echec_prelevement` | `transactions`, lignes où `actual_amount_paid < plan_list_price` | Montant de l'écart |
| `annulation_abonnement` | `transactions`, lignes où `is_cancel = 1` | 1 |
| `desactivation_renouvellement` | `transactions`, passage de `is_auto_renew` de 1 à 0 | 1 |

**Absence assumée :** ce jeu ne comporte ni tickets support ni contact commercial. Les catégories `SUPPORT` et `COMMERCIAL` du fichier de correspondance disparaissent pour cette source. Le pipeline doit fonctionner avec un sous-ensemble de catégories, sans code conditionnel dispersé.

Le taux de complétion est le signal le plus intéressant du jeu. Un utilisateur qui passe d'une majorité de morceaux écoutés en entier à une majorité de morceaux abandonnés avant 25 % se désengage, même si son temps d'écoute total ne bouge pas. C'est exactement le type de variable de tendance que le lot 3 doit produire.

## 5. Construction de la cible, et pourquoi on ne prend pas l'étiquette fournie

La définition officielle est la suivante : un utilisateur a churné s'il n'a aucun abonnement valide dans les 30 jours suivant l'expiration de son abonnement en cours.

**L'horizon passe donc de 60 à 30 jours pour cette source.** L'embargo suit, à 30 jours. Ce sont des paramètres de configuration, aucun code ne change.

Le fichier `train_v2.csv` fournit l'étiquette pour un unique mois de référence. Il ne permet donc pas de construire une grille d'observation multi-dates, qui est la base de tout le protocole.

**La cible est donc reconstruite depuis `transactions`**, pour chaque date d'observation `T0` : le compte est en churn si son abonnement expire après `T0` et qu'aucune transaction de renouvellement n'intervient dans les 30 jours suivant cette expiration.

**Référence mesurée le 7 septembre 2026 :** `train_v2.csv` contient 970 960 comptes, dont 87 330 en churn, soit un taux de 8,99 %.

**La règle n'est pas devinable, et elle n'a pas été devinée.** La compétition livre son propre labelleur, `WSDMChurnLabeller.scala`. Cinq de ses points auraient été faux sous n'importe quelle hypothèse raisonnable.

1. L'historique de référence est **un mois**, pas tout le passé. Seules les transactions de ce mois fixent l'expiration en vigueur.
2. Les candidats sont les comptes dont l'expiration tombe le **mois suivant**. Un compte dont l'abonnement court plus loin n'est pas candidat du tout.
3. Le délai se mesure entre l'expiration et la **date de transaction** du renouvellement, jamais entre deux expirations.
4. Une annulation peut **avancer** la date d'expiration, et des annulations successives continuent de l'avancer.
5. Les transactions d'une même journée suivent un ordre précis : signature de plan décroissante, souscription avant annulation, puis expiration croissante pour un renouvellement et décroissante pour une annulation.

Le labelleur fourni porte `historyCutoff = 20170131` et retient les expirations de février : c'est celui de `train.csv`, la première phase, et non celui de `train_v2.csv`. La transposition à la seconde phase, historique de février et expirations de mars, a été vérifiée par la mesure.

**Contrôle de validation, mesuré le 8 septembre 2026 :** sur un échantillon de 30 000 comptes, la cible reconstruite pour mars 2017 concorde avec `train_v2.csv` sur **97,03 %** des 25 702 comptes communs.

Le contrôle par l'absurde confirme le choix de la fenêtre. Appliquée à février, la même reconstruction produit un taux de churn de 0,03 % là où l'étiquette officielle donne 4,52 % : nos données allant jusqu'au 31 mars, tous les renouvellements de février y sont visibles et presque personne ne churne. Une fenêtre mal placée se voit donc immédiatement.

Les 3 % d'écart restants se répartissent en 227 comptes pour lesquels aucun renouvellement n'est trouvé alors que l'étiquette officielle en suppose un, et 537 comptes pour lesquels un renouvellement est trouvé avec un délai médian de moins un jour. L'écart n'est pas expliqué à ce jour et n'est pas masqué.

Ce contrôle est le point technique le plus démonstratif du projet. Reconstruire une cible temporelle depuis des transactions brutes, puis prouver la reconstruction contre une référence, est exactement ce que demande la mise en production d'un modèle de churn.

## 6. Filtres d'éligibilité adaptés

| Règle du contrat | Adaptation KKBox |
| :--- | :--- |
| Ancienneté minimale de 60 jours | Conservée, calculée depuis `registration_init_time` |
| Historique minimal de 90 jours | Conservée |
| Compte actif à `T0` | Abonnement en cours non expiré depuis plus de 30 jours |
| Purge des identifiants manquants | `msno` absent des trois fichiers après jointure |

## 7. Mise en place de l'accès Kaggle

Dépendance externe sur le chemin critique. Aucun élément n'était présent sur le poste de développement au 7 septembre 2026.

### 7.1 Étapes à réaliser une seule fois

1. **Créer un compte** sur `kaggle.com`, si ce n'est pas déjà fait.
2. **Accepter les règles de la compétition.** Ouvrir `kaggle.com/c/kkbox-churn-prediction-challenge/rules` et cliquer sur le bouton d'acceptation. Sans cette étape, l'API renvoie une erreur d'autorisation même avec un jeton valide. C'est la cause d'échec la plus fréquente.
3. **Créer un jeton**, sur `kaggle.com/settings/api`. Deux mécanismes coexistent, décrits ci-dessous.
4. **Déposer le jeton** dans le dossier `.kaggle` du répertoire personnel, soit `C:/Users/<utilisateur>/.kaggle/` sous Windows. Le dossier est à créer s'il n'existe pas.

### 7.2 Les deux mécanismes d'authentification

Le client `kaggle 2.2.4` accepte les deux, dans cet ordre de priorité, vérifié dans `kagglesdk/kaggle_env.py` :

1. la variable d'environnement `KAGGLE_API_TOKEN`, qui peut contenir soit le jeton lui-même, soit un chemin de fichier
2. le fichier `~/.kaggle/access_token`, jeton d'accès de la forme `KGAT_...`
3. le fichier `~/.kaggle/access_token.txt`, variante prévue pour les éditeurs Windows qui ajoutent l'extension
4. le fichier `~/.kaggle/kaggle.json`, mécanisme historique associant un nom d'utilisateur et une clé

Le contenu du fichier est nettoyé par un `strip`, donc un retour à la ligne final ne pose pas de problème.

Le jeton d'accès est le mécanisme actuel et le plus simple : un seul fichier, une seule ligne. Le format `kaggle.json` reste accepté.

### 7.3 Manipulation du secret

Un jeton d'accès ouvre le compte Kaggle. Trois règles.

- **Il ne s'écrit jamais en clair dans un message, un ticket, une conversation ou un fichier du dépôt.** Un jeton qui a transité par un canal de ce type est compromis et doit être révoqué, même s'il n'a jamais servi.
- **Il ne se tape pas dans une ligne de commande complète**, car il resterait dans l'historique du shell, soit `ConsoleHost_history.txt` pour PowerShell.
- **`chmod 600` n'a pas d'effet réel sous Windows.** Les permissions POSIX sont émulées par Git Bash sur NTFS et ne protègent rien. La protection repose sur les droits du compte utilisateur Windows.

**Piège d'encodage, vérifié le 2026-09-07.** Sous Windows PowerShell 5.1, la redirection `>`, `Out-File` et `Set-Content -Encoding utf8` écrivent tous une marque d'ordre d'octets UTF-8 en tête de fichier. Le client Kaggle lit le fichier puis lui applique un `strip`, qui retire les espaces mais pas cette marque. Le jeton devient alors invalide, et le message d'erreur renvoyé ne mentionne pas l'encodage.

Mesure : `Set-Content -Encoding ascii` produit 37 octets commençant par le jeton. `Out-File` en produit 40, précédés de `EF BB BF`, et la lecture côté client renvoie une valeur qui ne commence pas par `KGAT_`.

**Commande de dépôt du jeton, sous PowerShell**, testée de bout en bout. La saisie est masquée, rien n'entre dans l'historique, et l'encodage est imposé.

```powershell
$dir = Join-Path $env:USERPROFILE ".kaggle"
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
$sec = Read-Host -AsSecureString "Colle ton token Kaggle puis Entree"
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
$plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
Set-Content -Path (Join-Path $dir "access_token") -Value $plain -NoNewline -Encoding ascii
Remove-Variable plain, sec, bstr
```

**Équivalent sous Git Bash**, où l'encodage ne pose pas de problème :

```bash
mkdir -p ~/.kaggle
read -rs TOKEN && printf '%s' "$TOKEN" > ~/.kaggle/access_token && unset TOKEN
```

Les deux shells ne sont pas interchangeables. Windows PowerShell 5.1 ne connaît ni `&&` ni `||`, qui provoquent une erreur d'analyse.

La révocation se fait sur `kaggle.com/settings/api`, en supprimant le jeton puis en en générant un autre.

### 7.4 Vérification

```bash
uv run kaggle competitions files -c kkbox-churn-prediction-challenge
```

La commande doit lister les fichiers avec leur taille. Un échec pour cause d'autorisation signifie que l'étape 2 n'a pas été faite.

### 7.5 Téléchargement

Les fichiers se récupèrent séparément, jamais en une seule commande, afin de ne pas rapatrier l'intégralité du jeu d'un coup.

Les noms portent bien l'extension `.7z`. Sans elle, l'API renvoie une erreur de fichier introuvable.

```bash
mkdir -p data/raw
# Socle, environ 1 Go
uv run kaggle competitions download -c kkbox-churn-prediction-challenge -f train_v2.csv.7z -p data/raw
uv run kaggle competitions download -c kkbox-churn-prediction-challenge -f members_v3.csv.7z -p data/raw
uv run kaggle competitions download -c kkbox-churn-prediction-challenge -f transactions.csv.7z -p data/raw
uv run kaggle competitions download -c kkbox-churn-prediction-challenge -f transactions_v2.csv.7z -p data/raw
# Enrichissement, environ 7,8 Go
uv run kaggle competitions download -c kkbox-churn-prediction-challenge -f user_logs_v2.csv.7z -p data/raw
uv run kaggle competitions download -c kkbox-churn-prediction-challenge -f user_logs.csv.7z -p data/raw
```

Le script `scripts/download_kkbox.py` du lot 2 automatise cette séquence, aplatit l'arborescence interne des archives et procède à l'échantillonnage. Le détail de l'ordre et des volumes est en section 2.3.

### 7.6 Si l'accès tarde

Les lots 0 et 1 se construisent sur le générateur synthétique, dont c'est précisément le rôle. Le chemin critique n'est donc pas bloqué immédiatement, mais le lot 2 et toute la démonstration finale le sont.
