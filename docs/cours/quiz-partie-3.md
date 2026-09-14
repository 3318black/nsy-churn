# Quiz de la partie 3. Mesurer et prédire

> Dix questions pour vérifier vos acquis sur les chapitres 7 à 9. Une seule bonne réponse par question.

---

**1. Pourquoi la Precision@50 se calcule-t-elle semaine par semaine ?**

- A. Parce que c'est plus rapide à calculer
- B. Parce que l'équipe appelle 50 abonnés chaque semaine, et qu'un top 50 sur toute l'année ne correspond à aucune situation réelle
- C. Parce que les données n'existent que par semaine
- D. Parce que le ROC-AUC l'impose

**2. Sur une liste tirée au hasard, que doit valoir la Precision@50 ?**

- A. Environ 0,5
- B. Environ le taux de base, ici 2 %
- C. Exactement 0
- D. Environ 1

**3. Pourquoi ne mélange-t-on pas les lignes au hasard pour séparer apprentissage et test ?**

- A. Parce qu'un même abonné apparaît chaque semaine : ses lignes voisines, qui contiennent presque la réponse, se retrouveraient des deux côtés
- B. Parce que le hasard est interdit en data science
- C. Parce que les lignes sont trop nombreuses
- D. Parce que pandas ne sait pas mélanger

**4. À quoi sert l'embargo ?**

- A. À accélérer l'apprentissage
- B. À empêcher que la cible des dernières lignes d'apprentissage se résolve pendant la période de test
- C. À supprimer les abonnés inactifs
- D. À réduire la taille du modèle

**5. Quel est le rôle du tri par revenu comme ligne de base ?**

- A. Il sert de modèle final
- B. Il représente ce que ferait un conseiller sans outil, en appelant d'abord les clients qui paient le plus
- C. Il mesure la vitesse du calcul
- D. Il sert à choisir les hyperparamètres

**6. Pourquoi la fuite du revenu n'a-t-elle pas été détectée par la sentinelle anti-fuite ?**

- A. Parce que la sentinelle était désactivée
- B. Parce que la sentinelle coupe le journal d'événements, alors que le revenu venait de la table des comptes
- C. Parce que la fuite était trop petite
- D. Parce que le revenu n'était pas utilisé

**7. Où faut-il choisir les hyperparamètres du modèle ?**

- A. Sur la période de test, en gardant le meilleur résultat
- B. Sur une validation découpée à l'intérieur des seules données d'apprentissage
- C. Sur les données fictives
- D. Au hasard

**8. XGBoost avec le journal d'écoute gagne +0,019 sur XGBoost sans ce journal, avec un écart par pli de -0,025, +0,030, +0,033 et +0,038. Que conclure ?**

- A. Le journal d'écoute est indispensable
- B. Le journal d'écoute dégrade le modèle
- C. Le gain n'est pas établi : il est négatif sur un pli, et sa dispersion dépasse sa moyenne
- D. Il faut supprimer XGBoost

**9. Pourquoi retire-t-on la dernière colonne du tableau `pred_contribs` ?**

- A. Parce qu'elle est toujours nulle
- B. Parce que c'est le biais, commun à tous les abonnés, qui n'appartient à aucune variable
- C. Parce qu'elle contient la cible
- D. Parce qu'elle est trop grande

**10. Un abonné n'a aucune contribution au-dessus du seuil de signification. Que contient sa liste de motifs ?**

- A. Les trois plus fortes contributions, même faibles
- B. Un motif générique, « Risque élevé »
- C. Rien : ses motifs restent vides
- D. Les motifs de l'abonné précédent

---

<details>
<summary>Voir les réponses et les explications</summary>

1. **B.** La mesure doit correspondre à la capacité réelle de l'équipe. Chapitre 7, section 2.
2. **B.** C'est pourquoi le hasard sert de contrôle de la mesure. Chapitre 7, sections 2 et 4.
3. **A.** La séparation se fait dans le temps. Chapitre 7, section 3.
4. **B.** L'embargo dure au moins l'horizon de 30 jours. Chapitre 7, section 3.
5. **B.** C'est la référence métier, contre laquelle se calcule le lift. Chapitre 7, section 4.
6. **B.** Un test ne protège que ce qu'il manipule. Chapitre 8, section 1.
7. **B.** Choisir sur le test rendrait le résultat optimiste par construction. Chapitre 8, section 4.
8. **C.** Avec quatre plis, ce gain ne se distingue pas du bruit. Chapitre 8, section 5.
9. **B.** Sinon, le même motif s'afficherait chez tout le monde. Chapitre 9, section 2.
10. **C.** Un motif inventé est pire qu'un motif absent. Chapitre 9, section 4.

**Votre score :** 8 bonnes réponses ou plus, vous maîtrisez l'essentiel du projet à ce stade.

</details>

**Retour au** [sommaire du cours](README.md)
