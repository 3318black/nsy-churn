# Quiz de la partie 2. Préparer les données

> Dix questions pour vérifier vos acquis sur les chapitres 4 à 6. Une seule bonne réponse par question.

---

**1. Que se passe-t-il quand une source de données ne respecte pas le contrat ?**

- A. On assouplit le contrat pour l'accepter
- B. On corrige l'adaptateur de la source, le contrat ne change pas
- C. On ignore les lignes fautives sans rien dire
- D. On change de langage de programmation

**2. La colonne `date_resiliation` est vide pour un compte. Qu'est-ce que cela signifie ?**

- A. La source est non conforme
- B. Le compte est toujours actif, c'est une valeur manquante autorisée
- C. Le compte doit être supprimé
- D. La date est inconnue et il faut la deviner

**3. Pourquoi le générateur de données fictives produit-il des événements et jamais des variables toutes faites ?**

- A. Parce que c'est plus rapide
- B. Pour ne pas supprimer l'étape la plus risquée du projet : calculer ces variables sans regarder le futur
- C. Parce que les variables prennent trop de place
- D. Parce que pandas ne sait pas lire les variables

**4. Un modèle obtient un excellent score sur les données fictives. Que peut-on en conclure ?**

- A. Qu'il sera excellent sur les données réelles
- B. Qu'il faut le mettre en production
- C. Rien sur sa qualité réelle : le générateur contient les relations que le modèle retrouve
- D. Que les données réelles sont inutiles

**5. Pourquoi le projet utilise-t-il KKBox plutôt que le jeu de données de l'opérateur téléphonique d'IBM ?**

- A. Parce que KKBox est plus petit
- B. Parce que KKBox possède une vraie dimension temporelle, indispensable pour prédire honnêtement dans le temps
- C. Parce que le jeu d'IBM est payant
- D. Parce que KKBox contient l'âge fiable des abonnés

**6. Où faut-il tirer l'échantillon d'abonnés ?**

- A. Dans le fichier des comptes, qui est le plus complet
- B. Parmi les abonnés présents dans les transactions, sinon beaucoup n'auraient aucune cible calculable
- C. Dans le fichier d'écoute uniquement
- D. N'importe où, le hasard corrige tout

**7. Pourquoi la cible a-t-elle été reconstruite plutôt que prise dans `train_v2.csv` ?**

- A. Parce que ce fichier ne porte que sur un seul mois, alors que la grille couvre deux ans de semaines
- B. Parce que ce fichier est corrompu
- C. Parce que la cible officielle est fausse
- D. Parce que le fichier est trop volumineux

**8. Pour une ligne dont les 30 jours suivants dépassent la fin des données, que fait-on ?**

- A. On met la cible à 0, l'abonné est resté
- B. On met la cible à 1 par prudence
- C. On écarte la ligne, car sa réponse est inconnue
- D. On la garde et on laisse le modèle deviner

**9. Une variable est calculée pour la ligne (abonné, lundi 14 mars). Quels événements a-t-elle le droit d'utiliser ?**

- A. Tous ceux de mars
- B. Ceux jusqu'au 14 mars inclus
- C. Uniquement ceux strictement antérieurs au 14 mars à 00:00
- D. Ceux des 30 jours suivants

**10. Que vérifie la sentinelle anti-fuite ?**

- A. Que le calcul des variables est rapide
- B. Que supprimer tous les événements à partir de `T0` ne change aucune variable
- C. Que les données sont bien compressées
- D. Que le modèle a un bon score

---

<details>
<summary>Voir les réponses et les explications</summary>

1. **B.** Le contrat ne se plie jamais à une source. Chapitre 4, section 2.
2. **B.** Une valeur manquante n'est pas une colonne manquante. Chapitre 4, section 4.
3. **B.** C'est la décision D3. Chapitre 4, section 6.
4. **C.** C'est la décision D2 : jamais de performance sur données fictives. Chapitre 4, section 6.
5. **B.** Sans dates, impossible de se placer dans le passé. Chapitre 5, section 1.
6. **B.** Sur 6,77 millions de comptes, seuls 2,36 millions ont des transactions. Chapitre 5, section 3.
7. **A.** D'où la reconstruction, vérifiée à 97,03 %. Chapitre 5, section 5.
8. **C.** Compter à 0 biaiserait les semaines les plus récentes. Chapitre 6, section 4.
9. **C.** Strictement avant `T0`, pas le jour même. Chapitre 6, section 6.
10. **B.** Si une valeur change, elle dépendait du futur. Chapitre 6, section 8.

**Votre score :** 8 bonnes réponses ou plus, vous pouvez passer à la partie 3.

</details>

**Suite :** [7. Évaluer honnêtement : le protocole et les lignes de base](07-evaluer-honnetement.md)
