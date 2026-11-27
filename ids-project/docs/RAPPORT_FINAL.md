# Rapport final — IDS multi-classes sur CIC-IDS2017

## 1. Résumé

Nous avons construit un détecteur d'intrusions réseau supervisé qui classe un
flux dans une famille : BENIGN, DoS, DDoS, PortScan, BruteForce, WebAttack ou
Bot. Le travail suit six étapes reproductibles, avec une graine fixée à 42 et
un jeu de test laissé intact jusqu'à la dernière évaluation.

Le modèle final est un XGBoost réglé, entraîné sur 108 788 flux avec SMOTE à
l'intérieur du pipeline, à partir de 15 variables choisies sur le train.

## 2. Résultats chiffrés

| Métrique | Valeur |
|---|---:|
| Accuracy brute | 0.9966 |
| Accuracy équilibrée | 0.9907 |
| F1 macro | 0.8926 |
| F1 pondéré | 0.9970 |
| Précision macro | 0.8481 |
| Rappel macro | 0.9907 |
| PR-AUC macro | 0.8897 |

La validation croisée donnait 0.8714 de F1 macro ; le test donne
0.8926. L'écart est faible et s'explique par le fait que le modèle final
a vu tout le train, contre 4/5 des données dans chaque fold.

Il y a 93 erreurs sur 27197 flux, soit 0.34 %.

## 3. Points forts

- Le F1 macro de 0.8926 montre que les petites classes sont
  traitées, contrairement à ce que suggère l'accuracy brute de
  0.9966.
- Le rappel macro de 0.9907 signifie que presque toutes
  les attaques présentes sont détectées.
- La sélection de variables et le rééchantillonnage ont été faits dans le
  pipeline, donc sans fuite de données vers la validation ou le test.
- L'inférence mesure 0.0962 ms par flux sur 27093 flux du train,
  ce qui est compatible avec un traitement en continu (à confirmer sur le
  matériel de production).

## 4. Limites et biais

1. **Jeu de 2017** : les attaques ont été scriptées dans un laboratoire. Un
   trafic réel, chiffré ou plus récent, peut avoir un comportement différent.
2. **Échantillon de 5 %** : les conclusions valent pour cet échantillon
   stratifié, pas pour les 2,8 millions de flux bruts.
3. **Déséquilibre extrême** : BENIGN domine. Le F1 pondéré proche de 1 ne doit
   pas être présenté comme la performance du système.
4. **Familles non couvertes** : Infiltration (36 lignes)
   et Heartbleed (11 lignes) ont été mises de côté faute
   d'exemples. Le modèle est donc aveugle à ces deux menaces.
5. **Port de destination** : il arrivait en tête des importances, mais l'enlever
   a amélioré le F1. Il a été écarté pour éviter un raccourci lié au service.
6. **Pas de charge utile** : CICFlowMeter ne garde que des statistiques de flux.
   Le modèle ne peut pas inspecter le contenu d'une requête ou d'un fichier.
7. **Fausses alertes** : WebAttack a une précision de
   0.3729 et Bot de 0.5806. La première confusion est
   BENIGN -> WebAttack
   avec 37 cas.

## 5. Analyse des erreurs

Les erreurs sont concentrées sur deux phénomènes : des flux normaux pris pour
des attaques rares, et quelques attaques DoS prises pour du trafic normal.
Le détail est dans `reports/tables/erreurs_resume.csv` et la figure
`reports/figures/analyse_erreurs.png`.

Comme WebAttack et Bot n'ont que 22 et 19 exemples en test, quelques erreurs
suffisent à faire chuter leur précision. Ces chiffres doivent donc être lus
avec prudence, sans conclure que la classe est « maîtrisée ».

## 6. Proposition de déploiement

```text
Trafic réseau (port miroir SPAN ou TAP)
        |
        v
CICFlowMeter -> 15 statistiques de flux
        |
        v
Pipeline joblib (imputation, mise à l'échelle, XGBoost)
        |
        v
Famille prédite + probabilité
        |
        v
Règle d'alerte -> SIEM / SOC (mode observation)
```

Étapes concrètes :

1. **Capture** : brancher un port miroir ou un TAP en sortie de la zone à
   surveiller. Commencer en mode observation, sans blocage automatique.
2. **Extraction** : reproduire exactement les 15 colonnes et leurs noms avec
   CICFlowMeter. Toute colonne renommée casse le pipeline.
3. **Inférence** : charger `models/final_model.joblib` et
   `models/label_encoder.joblib`. Le SMOTE n'est pas dans ce fichier, donc il
   n'agit pas en production.
4. **Alerte** : ne pas alerter aveuglément sur WebAttack et Bot. Fixer un seuil
   de confiance après observation du trafic normal de l'organisation, puis
   mesurer le taux de fausses alertes.
5. **Supervision** : suivre la distribution des familles prédites, la dérive
   des variables, le taux d'alertes et le rappel quand des labels sont
   disponibles.
6. **Maintenance** : réentraîner périodiquement avec de nouvelles données
   étiquetées, toujours avec le même pipeline (SMOTE dans les folds), et
   garder un jeu de test séparé pour valider la nouvelle version.
7. **Sécurité** : garder un humain dans la boucle. Le modèle aide à trier les
   alertes, il ne remplace pas une analyse et ne bloque pas le trafic seul.

## 7. Conclusion

Le modèle atteint un F1 macro de 0.8926 sur un test jamais
vu, avec un rappel très élevé. Il est utilisable comme outil d'aide à la
détection, à condition d'accepter ses limites : attaques anciennes et
scriptées, deux familles absentes, et fausses alertes sur les classes rares.
La proposition de déploiement privilégie donc l'observation, le seuillage et
le suivi humain avant toute automatisation.
