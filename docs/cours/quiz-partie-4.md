# Quiz de la partie 4. Restituer les résultats

> Dix questions pour vérifier vos acquis sur les chapitres 10 à 12. Une seule bonne réponse par question.

---

**1. Pourquoi le scoring du lundi ne peut-il pas réutiliser tel quel le tableau d'apprentissage ?**

- A. Parce que ce tableau est trop volumineux
- B. Parce qu'il écarte les dates dont on ne connaît pas encore les 30 jours suivants, précisément celles qu'on veut scorer
- C. Parce que le modèle change chaque semaine
- D. Parce que les variables du scoring se calculent d'une autre façon

**2. Deux exécutions du scoring sur les mêmes données produisaient deux fichiers différents. Quelle cause le projet a-t-il corrigée ?**

- A. Le modèle tirait ses scores au hasard
- B. L'identifiant d'exécution était tiré au hasard
- C. Le disque était trop lent
- D. Le CSV était trop gros

**3. Pourquoi le CSV est-il écrit en `utf-8-sig`, avec un point-virgule comme séparateur ?**

- A. Pour réduire la taille du fichier
- B. Pour qu'Excel en français affiche les accents et sépare correctement les colonnes
- C. Pour que Python le lise plus vite
- D. Parce que le format Parquet l'exige

**4. L'ancienneté d'un abonné contribue fortement à son score. Apparaît-elle dans ses motifs ?**

- A. Oui, toujours en premier
- B. Oui, dès qu'elle dépasse le seuil de signification
- C. Non : elle compte dans le score, mais n'offre aucun levier d'action
- D. Non, car elle est retirée du modèle

**5. Pourquoi l'interface web ne recalcule-t-elle aucun score ?**

- A. Parce que Streamlit ne sait pas faire de calcul
- B. Pour garder une seule vérité, rester rapide et ne contenir aucun code d'entraînement : elle lit les fichiers du pipeline
- C. Parce que le modèle est confidentiel
- D. Pour que la page se charge sans connexion

**6. Pourquoi le type de contrat n'apparaît-il pas dans le profil de l'abonné ?**

- A. Parce que la colonne est vide
- B. Parce qu'il décrit l'abonné à la date d'extraction : l'afficher au lundi du scoring montrerait le futur
- C. Parce qu'il est confidentiel
- D. Parce qu'il prendrait trop de place à l'écran

**7. Comment les tests désignent-ils à l'interface le dossier temporaire à lire ?**

- A. En modifiant le code de l'application avant chaque test
- B. Par une variable d'environnement, `NSY_CHURN_ROOT`
- C. En copiant les vraies données KKBox
- D. En ouvrant un navigateur

**8. D'après les critères du README, où un lecteur non technique doit-il comprendre le problème et le résultat ?**

- A. Dans les deux premières sections
- B. Dans la section des limites
- C. Dans le code
- D. Dans le glossaire du cours

**9. Quelle phrase respecte les règles d'écriture du README ?**

- A. « Le modèle est 3,3 fois meilleur. »
- B. « Sur KKBox, en moyenne sur quatre plis chronologiques, le modèle trouve environ 14 départs sur 50 appels, contre 4 pour le tri par revenu. »
- C. « Le modèle atteint 97 % de précision. »
- D. « Le journal d'écoute améliore nettement le modèle. »

**10. Une limite relevée au lot 4 doit être reprise dans le README. Que faut-il faire d'abord ?**

- A. La recopier telle quelle
- B. La supprimer, pour ne pas inquiéter le lecteur
- C. La vérifier sur la mesure de référence, comme on vérifierait un résultat
- D. La déplacer en fin de document

---

<details>
<summary>Voir les réponses et les explications</summary>

1. **B.** Les règles d'éligibilité et le calcul des variables sont partagés, seule la règle d'issue connue est retirée. Chapitre 10, section 2.
2. **B.** L'identifiant est désormais dérivé des entrées du calcul, décision D20. Chapitre 10, section 5.
3. **B.** La marque d'ordre des octets annonce l'UTF-8, et le point-virgule est le séparateur attendu en français. Chapitre 10, section 6.
4. **C.** Seuls les motifs actionnables occupent une case, décision D19. Chapitre 10, section 4.
5. **B.** La cuisine prépare, la salle sert. Chapitre 11, section 3.
6. **B.** Une information n'est affichée que si l'on sait à quelle date elle est vraie, décision D18. Chapitre 11, section 2.
7. **B.** Un réglage transmis par le système, sans modifier le code. Chapitre 11, section 4.
8. **A.** C'est le premier critère d'acceptation du README. Chapitre 12, section 2.
9. **B.** Elle nomme la source, les conditions et une comparaison concrète. Chapitre 12, sections 3 et 4.
10. **C.** Recomptée, la limite des semaines à précision nulle ne concernait plus le modèle retenu. Chapitre 12, section 5.

**Votre score :** 8 bonnes réponses ou plus, vous maîtrisez l'essentiel du projet.

</details>

**Retour au** [sommaire du cours](README.md)
