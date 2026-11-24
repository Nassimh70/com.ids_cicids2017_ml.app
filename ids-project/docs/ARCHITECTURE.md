# Architecture du projet IDS multi-classes

Ce document explique le projet simplement, étape par étape. Il est mis à jour
après chaque étape avec les résultats réels, une explication du code et cinq
questions possibles du jury.

## État d'avancement

| Étape | Script | État |
|---|---|---|
| 1. Exploration | `01_exploration.py` | terminée |
| 2. Prétraitement et déséquilibre | `02_pretraitement.py` | terminée |
| 3. Sélection de variables | `03_selection.py` | à faire |
| 4. Modèles et validation croisée | `04_modeles.py` | à faire |
| 5. Évaluation sur le test | `05_evaluation.py` | à faire |
| 6. Analyse critique et déploiement | `06_analyse.py` | à faire |

Le projet est volontairement plat : `config.py` plus un script par étape.
Il n'y a pas de classes, ni de dossier `src/` avec dix modules.

---

## 1. Qu'est-ce qu'un IDS ?

Un IDS (*Intrusion Detection System*) observe une activité et signale ce qui
semble suspect. Il alerte, il ne bloque pas forcément le trafic.

- **NIDS** : analyse le trafic réseau, via un port miroir (SPAN) ou un TAP.
- **HIDS** : analyse les logs et les processus d'une machine.

Trois façons de détecter :

| Méthode | Idée | Force | Faiblesse |
|---|---|---|---|
| Signatures | règles connues (Snort, Suricata) | fiable, explicable | rate les attaques inconnues |
| Anomalies | apprentissage du comportement normal | peut surprendre | beaucoup de fausses alertes |
| Machine learning | apprentissage à partir de flux étiquetés | automatique | dépend des données |

Notre projet est un **NIDS supervisé multi-classes** : à partir d'un flux résumé
en statistiques, il prédit la famille d'attaque ou `BENIGN`.

## 2. Le dataset CIC-IDS2017

Publié par le Canadian Institute for Cybersecurity (Université du
Nouveau-Brunswick), capture du 3 au 7 juillet 2017. Page officielle :
<https://www.unb.ca/cic/datasets/ids-2017.html>.

Le lundi contient seulement du trafic normal ; les autres jours contiennent
des attaques scriptées : brute force FTP/SSH, DoS, Heartbleed, Web attacks,
infiltration, botnet, DDoS, PortScan. Chaque ligne d'un CSV est un flux extrait
par CICFlowMeter.

Colonnes utiles à connaître :

| Colonne | Signification |
|---|---|
| `Flow Duration` | durée du flux en microsecondes |
| `Total Fwd Packets`, `Total Length of Fwd Packets` | paquets et octets dans le sens initial |
| `Flow Bytes/s`, `Flow Packets/s` | débits (source de valeurs infinies) |
| `Flow IAT Mean`, `Fwd IAT Mean` | temps moyen entre deux paquets (*Inter Arrival Time*) |
| `Packet Length Mean` | taille moyenne des paquets |
| `SYN Flag Count`, `RST Flag Count`, `ACK Flag Count` | drapeaux TCP : connexion, fermeture brutale |
| `Source IP`, `Destination IP`, `Source Port`, `Destination Port`, `Timestamp` | identifiants ou horodatage, à retirer plus tard |

Les libellés bruts sont regroupés en familles pour être lisibles et assez
peuplées :

| Famille | Libellés regroupés |
|---|---|
| `BENIGN` | `BENIGN` |
| `DoS` | GoldenEye, Hulk, Slowloris, Slowhttptest |
| `DDoS` | `DDoS` |
| `PortScan` | `PortScan` |
| `BruteForce` | FTP-Patator, SSH-Patator |
| `WebAttack` | Brute Force, XSS, Sql Injection |
| `Bot`, `Infiltration`, `Heartbleed` | conservés tels quels pour l'instant |

**Échantillon** : 5 % par famille avec graine 42 ; les familles de 100 lignes
ou moins sont gardées entièrement, sinon `Heartbleed` (11 lignes) aurait
disparu. Le déséquilibre d'origine est donc conservé.

## 3. Vue d'ensemble du pipeline

```mermaid
flowchart LR
    A[8 CSV dans data/raw/] --> B[01_exploration.py<br/>chargement, familles, échantillon, graphiques]
    B --> C[02_pretraitement.py<br/>nettoyage, doublons, split 80/20, équilibrage]
    C --> D[03_selection.py<br/>variables gardées]
    D --> E[04_modeles.py<br/>RF, XGBoost, LR + CV 5 folds]
    E --> F[05_evaluation.py<br/>matrice de confusion, FPR, temps]
    F --> G[06_analyse.py<br/>fuite, biais, déploiement]
```

## 4. Les fichiers du projet

| Fichier | Rôle |
|---|---|
| `config.py` | graine, chemins, mapping des familles, colonnes à retirer |
| `01_exploration.py` | lit les CSV, crée l'échantillon, produit les graphiques et tableaux |
| `02_pretraitement.py` ... `06_analyse.py` | une étape chacun, créés au fur et à mesure |
| `data/raw/MachineLearningCVE/` | CSV officiels (non versionnés) |
| `data/processed/` | échantillon et jeux d'entraînement/test |
| `reports/figures/`, `reports/tables/` | graphiques et tableaux CSV |
| `models/` | modèle final sauvegardé |

## 5. Choix techniques déjà faits

- **Échantillon stratifié** : le jeu complet fait 2,8 millions de lignes, trop
  lourd pour un PC ; 5 % suffisent pour comparer des modèles.
- **Libellés normalisés** : sans cela, 7 976 lignes partaient dans `AUTRE`.
- **Doublons pas encore supprimés** : on les a comptés à l'étape 1, on les
  retirera avant le split à l'étape 2 pour éviter la fuite de données.
- **Identifiants et timestamp** : la liste `RISKY_COLUMNS` est appliquée à
  l'étape 2. Dans la version des CSV fournie ici, ces colonnes ne sont déjà
  pas présentes (le fichier commence par `Destination Port`) : aucune
  suppression n'a donc été faite. Le `Destination Port` est gardé car c'est
  une information disponible en production (service visé), mais son
  importance sera surveillée aux étapes 3 et 6.
- **F1 macro et PR-AUC** (plus tard) plutôt que l'accuracy : 80 % des flux sont
  `BENIGN`, donc l'accuracy est trompeuse.

Les sections 6 (algorithmes) et 7 (métriques détaillées) seront complétées aux
étapes 4 et 5.

## 8. Comment exécuter

Depuis le dossier du projet :

```bash
pip install -r requirements.txt
python 01_exploration.py
python 02_pretraitement.py
```

Le script lit les 8 CSV, écrit `data/processed/sample_stratified_5pct.csv`, puis
les graphiques dans `reports/figures/` et les tableaux dans `reports/tables/`.
Pour lire les résultats : `distribution_classes.csv` montre le déséquilibre,
`valeurs_manquantes.csv` et `valeurs_infinies.csv` les cellules à corriger,
`doublons.csv` le risque de fuite, `correlations_fortes.csv` les variables
redondantes, et `correlations.png` la heatmap.

## 9. Pièges rencontrés

- **Libellés sales** : `DoS slowloris` en minuscules, et `Web Attack` suivi d'un
  caractère de remplacement `U+FFFD` au lieu d'un espace. Corrigé par une
  normalisation des caractères et un mapping insensible à la casse.
- **Doublons** : 5 549 lignes identiques (3,92 %), à traiter avant le split.
- **Valeurs infinies** : 162 cellules dans les débits, à remplacer par NaN puis
  imputer sur le train seulement.
- **Corrélations** : 48 paires à plus de 0,95, dont des doublons de colonnes
  calculées deux fois par CICFlowMeter.
- Aucun score de modèle n'a encore été calculé : on ne peut donc pas encore
  parler de score « trop parfait ».

## 10. Glossaire (en cours)

- **Flux** : suite de paquets partageant les mêmes adresses, ports et protocole.
- **IAT** : temps entre l'arrivée de deux paquets.
- **Fuite de données** : information du test qui passe dans l'entraînement.
- **Stratifié** : tirage qui garde les proportions de chaque classe.

---

## Explication du code — étape 1

### `config.py`

Il contient uniquement des constantes : `RANDOM_STATE = 42`, les chemins
(`RAW_DIR`, `PROCESSED_DIR`, ...), la règle d'échantillonnage, le dictionnaire
`FAMILIES` et la liste `RISKY_COLUMNS`. Les dossiers de sortie sont créés au
chargement du fichier. Les autres scripts font `from config import ...`, ce qui
évite de recopier les chemins partout.

### `01_exploration.py`

Le script se lit de haut en bas.

1. `charger_csv()` repère les 8 CSV dans `data/raw/MachineLearningCVE/` (ou
   directement dans `data/raw/`), supprime l'espace en tête des colonnes et
   ajoute `source_file` et `jour`. Ces deux colonnes servent seulement plus
   tard à la validation par jour ; ce ne sont pas des features.
2. La normalisation des libellés utilise trois `str.replace` : on enlève les
   caractères bizarres, on remplace les espaces multiples par un seul, puis on
   passe par `lookup` (dictionnaire en minuscules) pour obtenir `Family`.
3. `echantillonner(df)` fait un `groupby("Family")` et tire `n` lignes par
   famille avec `sample(random_state=42)`. Les familles de moins de 100 lignes
   sont gardées en entier.
4. La distribution est construite avec `value_counts().reindex(...)` puis
   sauvegardée en CSV. Le graphique utilise une échelle log : avec 113 655
   `BENIGN` et 11 `Heartbleed`, une échelle linéaire rendrait les petites
   classes invisibles.
5. La qualité des données utilise `isna().sum()`, `np.isinf()`, `nunique()` et
   `duplicated()`. On ne supprime rien ici : on mesure d'abord.
6. Les boxplots utilisent `sns.boxplot` sur 1 000 lignes par famille (assez pour
   voir la forme des distributions). L'échelle `symlog` permet d'afficher des
   valeurs très étalées, y compris quelques négatives.
7. La heatmap utilise `df.corr()`. Pour lister les paires redondantes, on garde
   seulement le triangle supérieur avec `np.triu(..., k=1)`, sinon chaque paire
   apparaîtrait deux fois.

### Résultats réels de l'étape 1

- Brut : **2 830 743 lignes × 81 colonnes**. Échantillon : **141 581 lignes**,
  124,7 Mo, sauvegardé dans `data/processed/sample_stratified_5pct.csv`.
- Familles de l'échantillon : BENIGN 113 655 (80,28 %), DoS 12 633, PortScan
  7 946, DDoS 6 401, BruteForce 692, WebAttack 109, Bot 98, Infiltration 36,
  Heartbleed 11.
- 54 valeurs manquantes (`Flow Bytes/s`), 162 infinies (54 `Flow Bytes/s` et
  108 `Flow Packets/s`), 8 colonnes constantes, 5 549 doublons exacts (3,92 %)
  et 48 paires de variables corrélées à plus de 0,95.
- Fichiers créés : **10 figures** (`distribution_classes.png`,
  `valeurs_manquantes.png`, `correlations.png`, 6 `box_*.png`, 2
  `hist_*.png`) et **6 tableaux** (`distribution_classes.csv`,
  `valeurs_manquantes.csv`, `valeurs_infinies.csv`, `colonnes_constantes.csv`,
  `doublons.csv`, `correlations_fortes.csv`).

## Cinq questions du jury — étape 1

1. **Pourquoi 5 % et pas tout le jeu ?** Le jeu complet fait 2,8 millions de
   lignes ; 5 % = 141 581 lignes, largement suffisant pour comparer des
   modèles en CV sur un PC, et l'échantillon est fixé par la graine 42.
2. **Pourquoi garder toutes les lignes des familles rares ?** `Heartbleed` n'a
   11 exemples : à 5 %, il aurait pu disparaître complètement.
3. **Pourquoi une échelle logarithmique pour les classes ?** Le rapport est de
   10 000 à 1 entre BENIGN et Heartbleed ; en linéaire, les petites classes ne
   verraient presque rien.
4. **D'où venaient les 7 976 lignes `AUTRE` ?** De libellés mal écrits dans les
   CSV (casse et caractère `U+FFFD`). Après normalisation, elles sont classées
   dans DoS et WebAttack ; il ne reste aucun libellé inconnu.
5. **Les doublons sont-ils un problème ?** Oui : si la même ligne est en train
   et en test, le score sera gonflé. On les a comptés ici (3,92 %) et on les
   supprimera avant le split à l'étape 2.

---

## Explication du code — étape 2

`02_pretraitement.py` se lit encore de haut en bas, sans fonction compliquée.

1. **Lecture et colonnes** : on relit l'échantillon de l'étape 1. La liste
   `RISKY_COLUMNS` est appliquée, mais dans les CSV fournis ces colonnes
   n'existent pas déjà : le script affiche donc `[]`. C'est normal et c'est
   tracé dans le tableau `resume_pretraitement.csv`. Les 8 colonnes constantes
   trouvées à l'étape 1 sont retirées.
2. **Infinis** : `replace([np.inf, -np.inf], np.nan)` transforme les 162 valeurs
   infinies en `NaN`. L'imputation médiane n'est pas faite ici : elle est dans
   le pipeline, donc recalculée sur chaque fold d'entraînement.
3. **Doublons** : `drop_duplicates()` est appelé **avant** `train_test_split()`.
   C'est le point clé anti-fuite.
4. **Familles rares** : `Infiltration` (36) et `Heartbleed` (11) sont écrites
   dans `data/processed/attaques_rares.csv` puis enlevées du jeu de modèle.
   Avec environ 2 et 7 exemples dans le test, on ne peut pas tirer de
   conclusion sur leur détection.
5. **Split** : `train_test_split(..., test_size=0.2, stratify=y,
   random_state=42)`. Le jeu de test est écrit dans `test.csv` et n'est plus
   touché jusqu'à l'étape 5.
6. **Comparaison des équilibrages** : on utilise
   `imblearn.pipeline.Pipeline` avec `SimpleImputer`, `StandardScaler`, un
   sampleur, puis `LogisticRegression`. `cross_validate` avec
   `StratifiedKFold(5)` évalue chaque stratégie. Comme le sampleur fait partie
   du pipeline, il n'est ajusté que sur les 4/5 d'entraînement de chaque fold.
7. **Cibles de rééchantillonnage** : imblearn refuse un float pour le
   multi-classes, donc on donne un dictionnaire. Le sous-échantillonnage
   ramène `BENIGN` à 20 000 lignes. SMOTE vise 20 % de la taille de `BENIGN`
   pour chaque classe, avec un plafond de 10 fois la classe d'origine (pour ne
   pas créer 17 000 faux `Bot` à partir de 78 exemples).

### Résultats réels de l'étape 2

- Après déduplication : **136 032** lignes ; après retrait des 47 lignes rares :
  **135 985** lignes. Train : **108 788**, test : **27 197**.
- Classes du train : BENIGN 88 952, DoS 8 040, PortScan 6 070, DDoS 5 121,
  BruteForce 440, WebAttack 87, Bot 78.
- Comparaison en CV 5 folds (F1 macro moyen ± écart-type) :

| Stratégie | F1 macro | Accuracy | Temps |
|---|---:|---:|---:|
| `class_weight='balanced'` | 0,5616 ± 0,0019 | 0,8436 | 393 s |
| Sous-échantillonnage | 0,6395 ± 0,0106 | 0,9621 | 103 s |
| SMOTE | **0,6544 ± 0,0079** | 0,9631 | 341 s |

- L'écart entre SMOTE et le sous-échantillonnage est faible (0,015) et
  SMOTE est trois fois plus lent : le choix définitif sera fait à l'étape 4
  avec les autres modèles. Le point important est que **l'accuracy de 0,84
  du `class_weight` cache un F1 macro de 0,56** : la classe majoritaire
  domine le score.
- Fichiers créés : `data/processed/train.csv`, `test.csv`,
  `attaques_rares.csv`; `reports/tables/resume_pretraitement.csv`,
  `comparaison_equilibrage.csv`; `reports/figures/comparaison_equilibrage.png`.

## Cinq questions du jury — étape 2

1. **Pourquoi supprimer les doublons avant le split ?** Sinon une ligne
   identique peut être en train et en test ; le modèle la « connaît » déjà et
   le score est artificiellement haut. On en a retiré 5 549.
2. **Pourquoi le sampleur est-il dans le pipeline ?** Parce que dans chaque
   fold, SMOTE ne doit voir que les 4/5 d'entraînement. Si on rééchantillonnait
   avant la CV, des points synthétiques calculés à partir du fold de
   validation fuiraient dans l'entraînement.
3. **Pourquoi exclure deux familles au lieu de les garder ?** 11 et 36
   exemples donnent 2 et 7 lignes en test : le F1 par classe serait du bruit.
   Elles sont conservées dans `attaques_rares.csv` pour l'analyse critique.
4. **Pourquoi 0,84 d'accuracy avec seulement 0,56 de F1 macro ?** Parce que
   BENIGN représente 82 % du train : un modèle peut bien prédire la majorité et
   rater les petites classes. Le F1 macro donne le même poids à chaque classe.
5. **Pourquoi un dictionnaire pour `sampling_strategy` ?** En multi-classes,
   imblearn interdit les floats. On fixe donc un effectif cible par classe,
   avec un plafond pour ne pas synthétiser trop de données rares.
