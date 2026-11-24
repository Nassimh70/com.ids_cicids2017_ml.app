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
python 01_exploration.py      # étape 1, terminée
python 02_pretraitement.py    # à créer à l'étape 2
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
