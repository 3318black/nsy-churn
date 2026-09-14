# Quiz de la partie 1. Découvrir le projet

> Dix questions pour vérifier vos acquis sur les chapitres 1 à 3. Une seule bonne réponse par question. Notez vos réponses, puis dépliez la correction.

---

**1. Qu'appelle-t-on le churn ?**

- A. Le nombre de nouveaux abonnés chaque mois
- B. Le départ d'un abonné qui arrête son abonnement
- C. Le chiffre d'affaires moyen par abonné
- D. Le temps passé par un abonné sur le service

**2. Que produit l'application chaque lundi ?**

- A. Le pourcentage global d'abonnés qui vont partir
- B. Un tableau de bord des ventes de la semaine
- C. Une liste d'abonnés classés par risque de départ, avec jusqu'à trois motifs chacun
- D. Un appel automatique vers les abonnés à risque

**3. Pourquoi l'application n'affiche-t-elle pas « 87 % de chances de partir » ?**

- A. Parce que le calcul d'un pourcentage est trop lent
- B. Parce que le score du modèle ne se lit pas comme une probabilité fiable, et qu'un rang suffit pour prioriser
- C. Parce que les pourcentages sont interdits par la loi
- D. Parce que le modèle ne produit aucun score

**4. Pourquoi une exactitude de 95 % peut-elle tromper sur un problème de churn ?**

- A. Parce que les départs sont rares : prédire « personne ne part » donne déjà une exactitude élevée
- B. Parce que l'exactitude ne se calcule pas sur des données réelles
- C. Parce qu'elle est toujours inférieure à 50 %
- D. Parce qu'elle mesure la vitesse du modèle

**5. Quelle est la principale faiblesse des projets de churn habituels ?**

- A. Ils utilisent Python
- B. Ils mélangent passé et futur, si bien que le modèle apprend des informations qu'il n'aurait pas eues au moment de décider
- C. Ils ont trop peu de colonnes
- D. Ils affichent des graphiques

**6. À quoi sert le registre des décisions ?**

- A. À lister les bugs du projet
- B. À noter les heures de travail
- C. À consigner chaque choix important avec sa date et son motif, pour ne pas le rediscuter sans fin et pouvoir l'expliquer
- D. À stocker les données du projet

**7. Qu'est-ce qu'un critère d'acceptation ?**

- A. Une condition précise et vérifiable qui doit être remplie pour considérer une étape terminée
- B. L'avis du recruteur sur le projet
- C. Le nom d'une branche Git
- D. Une bibliothèque Python

**8. Pourquoi la façon d'évaluer le modèle est-elle fixée avant d'entraîner le modèle ?**

- A. Parce que c'est plus rapide
- B. Parce qu'une méthode d'évaluation construite après avoir vu les résultats tend à se plier à ces résultats
- C. Parce que le modèle ne peut pas être évalué
- D. Parce que GitHub l'impose

**9. À quoi sert le fichier `uv.lock` ?**

- A. À protéger le projet par un mot de passe
- B. À noter la version exacte de chaque bibliothèque, pour que tout le monde obtienne le même résultat
- C. À empêcher les modifications du code
- D. À stocker le modèle entraîné

**10. Pourquoi la bibliothèque shap n'est-elle pas utilisée dans l'application finale ?**

- A. Parce qu'elle donne des résultats faux
- B. Parce qu'elle est payante
- C. Parce que XGBoost calcule exactement les mêmes contributions lui-même, sans ses dépendances supplémentaires
- D. Parce qu'elle ne fonctionne pas sous Windows

---

<details>
<summary>Voir les réponses et les explications</summary>

1. **B.** Le churn est le départ d'un abonné. Chapitre 1, section 1.
2. **C.** Une liste classée par risque, avec jusqu'à trois motifs par abonné. L'application ne décide et n'appelle rien. Chapitre 1, section 2.
3. **B.** Le besoin est un ordre de priorité ; un pourcentage inviterait à un contresens. Chapitre 1, section 2.
4. **A.** Avec 2 % de départs, prédire « personne ne part » donne 98 % d'exactitude, sans détecter un seul départ. Chapitre 1, section 5.
5. **B.** Le mélange du passé et du futur rend l'évaluation trompeuse. Chapitre 1, section 5.
6. **C.** Chaque décision porte un motif, et se révise par écrit. Chapitre 2, section 2.
7. **A.** Un critère d'acceptation se vérifie. « Le modèle doit être bon » n'en est pas un. Chapitre 2, section 4.
8. **B.** C'est pourquoi le lot 4, l'évaluation, précède le lot 5, le modèle. Chapitre 2, section 4.
9. **B.** Le fichier de verrouillage fixe les 94 versions exactes. Chapitre 3, section 3.
10. **C.** Mesure faite, les valeurs sont identiques. Chapitre 3, section 7.

**Votre score :** 8 bonnes réponses ou plus, vous pouvez passer à la partie 2. Moins de 8, relisez les sections indiquées.

</details>

**Suite :** [4. Le contrat de données et les données d'entraînement fictives](04-contrat-de-donnees.md)
