# Adaptation du contrat de données au jeu KKBox

Source : `WSDM - KKBox's Churn Prediction Challenge`, Kaggle, 2017. Deux ans d'observation continue sur un service de streaming musical par abonnement.

Ce document décrit comment KKBox se projette sur le contrat de données défini dans `data-contract.md`. Le contrat ne change pas : c'est la source qui s'y conforme, par un adaptateur. Voir décision D14.

## 1. Pourquoi ce jeu et pas un autre

Il possède ce qui manque à tous les jeux de churn courants : une dimension temporelle réelle. Des logs d'écoute quotidiens, un historique de transactions daté, des attributs de compte, et un churn défini contractuellement. Le déséquilibre observé, de 6 à 7 % de churn, correspond à un cas réel et non à un jeu rééquilibré artificiellement.

Le jeu Telco d'IBM, sur lequel repose la quasi-totalité des projets de churn publics, est une photographie sans axe temporel. Il rend impossible tout ce qui fait la valeur de ce projet : l'horizon de prédiction, l'embargo, la construction de fenêtres glissantes et la Precision@K par période.

## 2. Fichiers sources et volumétrie

| Fichier | Contenu | Ordre de grandeur |
| :--- | :--- | :--- |
| `members_v3.csv` | Attributs de compte | 6,7 millions d'utilisateurs |
| `transactions_v2.csv` | Abonnements et facturation | 21,5 millions de lignes |
| `user_logs_v2.csv` | Écoute quotidienne par utilisateur | environ 30 Go |
| `train_v2.csv` | Étiquette officielle de churn | pour un mois de référence |

**Échantillonnage obligatoire.** Un tirage aléatoire de comptes est effectué en premier, puis les trois fichiers sont filtrés sur cet échantillon. `user_logs_v2.csv` se lit par morceaux, jamais en une fois. La taille d'échantillon par défaut est fixée dans `config.yaml`, à 50 000 comptes.

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

**Contrôle de validation obligatoire :** la cible reconstruite est comparée à `train_v2.csv` sur le mois de référence. Le taux de concordance est mesuré et consigné dans le rapport. Un écart important signale une erreur de reconstruction, pas une imprécision de l'étiquette officielle.

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

```bash
mkdir -p data/raw
uv run kaggle competitions download -c kkbox-churn-prediction-challenge -f members_v3.csv -p data/raw
uv run kaggle competitions download -c kkbox-churn-prediction-challenge -f transactions_v2.csv -p data/raw
uv run kaggle competitions download -c kkbox-churn-prediction-challenge -f train_v2.csv -p data/raw
uv run kaggle competitions download -c kkbox-churn-prediction-challenge -f user_logs_v2.csv -p data/raw
```

Le format d'archive livré par l'API est à confirmer au premier téléchargement. Le script `scripts/download_kkbox.py` du lot 2 prend en charge la décompression et l'échantillonnage.

**Ordre recommandé** : commencer par les trois premiers fichiers, qui sont légers. Ils suffisent à construire la table `accounts`, à reconstruire la cible et à valider cette reconstruction contre l'étiquette officielle, ce qui est le critère central du lot 2. Le fichier `user_logs_v2.csv`, d'environ 30 Go, n'est nécessaire qu'aux variables d'usage produit et peut se télécharger pendant que le reste avance.

### 7.6 Si l'accès tarde

Les lots 0 et 1 se construisent sur le générateur synthétique, dont c'est précisément le rôle. Le chemin critique n'est donc pas bloqué immédiatement, mais le lot 2 et toute la démonstration finale le sont.
