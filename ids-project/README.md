# IDS multi-classes sur CIC-IDS2017

Projet universitaire : détecter et classer des attaques réseau à partir de flux
CIC-IDS2017, puis dire honnêtement ce que le modèle vaut et comment le
déployer. Le détail pédagogique est dans `docs/ARCHITECTURE.md`.

## Données

Les 8 CSV officiels sont attendus dans `data/raw/MachineLearningCVE/` (ou
directement dans `data/raw/`). Ils viennent de la page du CIC, Université du
Nouveau-Brunswick : <https://www.unb.ca/cic/datasets/ids-2017.html>
(archive `MachineLearningCSV.zip`, formulaire à remplir). Référence :
Sharafaldin, Lashkari & Ghorbani, ICISSP 2018.

Les données sont déjà présentes ici. L'échantillon utilisé par toutes les
étapes est `data/processed/sample_stratified_5pct.csv` (141 581 lignes).

## Installation et exécution

```bash
pip install -r requirements.txt
python 01_exploration.py      # étape 1
python 02_pretraitement.py    # étape 2
python 03_selection.py        # étape 3
...
```

Chaque étape est un script indépendant. Les graphiques vont dans
`reports/figures/`, les tableaux CSV dans `reports/tables/`, le modèle final
dans `models/`.

## Structure

```
ids-project/
├── config.py                 # constantes et graine = 42
├── 01_exploration.py         # étape 1
├── 02_pretraitement.py ...   # une étape par script
├── data/raw/                 # CSV officiels (non versionnés)
├── data/processed/           # échantillon et jeux train/test
├── docs/ARCHITECTURE.md
├── reports/figures/, reports/tables/
├── models/
└── requirements.txt
```

## Résultat de l'étape 1

- 2 830 743 flux bruts, échantillon de 141 581 flux (5 % stratifié).
- 80,28 % de trafic `BENIGN` : l'accuracy sera donc évitée.
- 3,92 % de doublons, 162 valeurs infinies, 8 colonnes constantes,
  48 paires de variables très corrélées.
- 10 figures et 6 tableaux générés, sans aucune donnée inventée.

## Résultat de l'étape 2

- Après déduplication : 136 032 lignes ; 47 lignes rares mises de côté ;
  train 108 788 / test 27 197 (split stratifié 80/20, graine 42).
- F1 macro en CV 5 folds : class_weight 0,5616 ; sous-échantillonnage 0,6395 ;
  SMOTE 0,6544. L'accuracy de 0,84 du premier cache un F1 macro de 0,56.
- Le rééchantillonnage se fait dans le pipeline, donc à l'intérieur de chaque
  fold ; le jeu de test reste intact jusqu'à l'étape 5.

## Résultat de l'étape 3

- Deux méthodes comparées en CV (sélection dans le pipeline) : ANOVA et
  importance Random Forest. À 15 variables : 0,6334 contre 0,8153 de F1 macro.
- Les 70 variables donnent 0,8689, mais on garde 15 variables (F1 0,8398) pour
  une inférence plus rapide et un modèle plus simple.
- `Destination Port` est exclu après un contrôle : sans lui, le F1 passe de
  0,8153 à 0,8398 (biais de service).
- Liste finale dans `data/processed/selected_features.txt`, courbe dans
  `reports/figures/courbe_selection.png`.
