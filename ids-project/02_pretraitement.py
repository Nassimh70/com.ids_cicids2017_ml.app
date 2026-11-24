"""Étape 2 : nettoyage, split train/test et comparaison des équilibrages."""

import time

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline
from imblearn.under_sampling import RandomUnderSampler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.preprocessing import StandardScaler

from config import (RANDOM_STATE, RISKY_COLUMNS, RARE_FAMILIES,
                    PROCESSED_DIR, FIGURES_DIR, TABLES_DIR, SAMPLE_FILE)


df = pd.read_csv(PROCESSED_DIR / SAMPLE_FILE, low_memory=False)
n_depart = len(df)
print("Départ :", n_depart, "lignes et", df.shape[1], "colonnes")

# 1. identifiants et horodatage dehors : on ne veut pas mémoriser une machine
colonnes_a_retirer = [c for c in RISKY_COLUMNS if c in df.columns]
df = df.drop(columns=colonnes_a_retirer)
print("Colonnes identifiantes retirées :", colonnes_a_retirer)

# 2. colonnes constantes relevées à l'étape 1
uniques = df.nunique(dropna=False)
constantes = list(uniques[uniques <= 1].index)
df = df.drop(columns=constantes)
print("Colonnes constantes retirées :", len(constantes))

# 3. les débits infinis deviennent des NaN, imputés plus tard sur le train seulement
colonnes_num = list(df.select_dtypes(include="number").columns)
nb_infinis = int(np.isinf(df[colonnes_num].to_numpy(dtype=float)).sum())
df[colonnes_num] = df[colonnes_num].replace([np.inf, -np.inf], np.nan)
print("Infinis remplacés par NaN :", nb_infinis)

# 4. doublons enlevés AVANT le split, sinon la même ligne peut être en train et test
avant_dedup = len(df)
df = df.drop_duplicates(subset=colonnes_num + ["Label"]).reset_index(drop=True)
apres_dedup = len(df)
print("Doublons supprimés :", avant_dedup - apres_dedup)

# 5. familles trop rares mises de côté (11 et 36 exemples, pas assez pour tester)
rares = df[df["Family"].isin(RARE_FAMILIES)].copy()
rares.to_csv(PROCESSED_DIR / "attaques_rares.csv", index=False)
df = df[~df["Family"].isin(RARE_FAMILIES)].reset_index(drop=True)
print("Familles rares mises de côté :", len(rares), "(attaques_rares.csv)")

# 6. features / cible, puis split stratifié 80/20
y = df["Family"]
X = df.drop(columns=["Family", "Label", "source_file", "jour"])
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE
)
print("Train :", len(X_train), "lignes / Test :", len(X_test), "lignes")
print("Classes du train :", y_train.value_counts().to_dict())

resume = pd.DataFrame({
    "etape": ["échantillon", "après colonnes à risque", "après colonnes constantes",
              "après doublons", "après familles rares", "train", "test"],
    "lignes": [n_depart, n_depart, n_depart, apres_dedup, len(df), len(X_train), len(X_test)],
})
resume.to_csv(TABLES_DIR / "resume_pretraitement.csv", index=False)

train = X_train.copy()
train["Family"] = y_train
test = X_test.copy()
test["Family"] = y_test
train.to_csv(PROCESSED_DIR / "train.csv", index=False)
test.to_csv(PROCESSED_DIR / "test.csv", index=False)

# 7. comparaison des 3 stratégies, uniquement sur le train
# le sampleur est dans le pipeline imblearn : à chaque fold, il ne voit que
# les données d'entraînement du fold, jamais le jeu de test.
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)

# en multi-classes, imblearn attend un dictionnaire {classe: effectif voulu}
comptage = y_train.value_counts()
majoritaire = comptage.idxmax()
cible_smote = {}
for classe, nb in comptage.drop(majoritaire).items():
    cible_smote[classe] = min(int(0.2 * comptage[majoritaire]), 10 * int(nb))

strategies = {
    "class_weight": ("passthrough", {"class_weight": "balanced"}),
    "sous-échantillonnage": (
        RandomUnderSampler(sampling_strategy={majoritaire: 20000}, random_state=RANDOM_STATE), {}),
    "SMOTE": (SMOTE(sampling_strategy=cible_smote, random_state=RANDOM_STATE), {}),
}
resultats = []

for nom, (sampleur, parametres) in strategies.items():
    pipe = Pipeline([
        ("imputation", SimpleImputer(strategy="median")),
        ("scaling", StandardScaler()),
        ("equilibrage", sampleur),
        ("modele", LogisticRegression(max_iter=1000, random_state=RANDOM_STATE,
                                      **parametres)),
    ])
    debut = time.time()
    scores = cross_validate(pipe, X_train, y_train, cv=cv,
                            scoring=["f1_macro", "accuracy"])
    resultats.append({
        "strategie": nom,
        "f1_macro_moy": round(scores["test_f1_macro"].mean(), 4),
        "f1_macro_std": round(scores["test_f1_macro"].std(), 4),
        "accuracy_moy": round(scores["test_accuracy"].mean(), 4),
        "temps_s": round(time.time() - debut, 1),
    })
    print(nom, "F1 macro =", resultats[-1]["f1_macro_moy"],
          "+/-", resultats[-1]["f1_macro_std"])

comparaison = pd.DataFrame(resultats)
comparaison.to_csv(TABLES_DIR / "comparaison_equilibrage.csv", index=False)

fig, ax = plt.subplots(figsize=(7, 4))
ax.bar(comparaison["strategie"], comparaison["f1_macro_moy"],
       yerr=comparaison["f1_macro_std"], capsize=4, color="steelblue")
ax.set_ylim(0, 1)
ax.set_title("F1 macro en validation croisée (train uniquement)")
ax.set_ylabel("F1 macro")
ax.tick_params(axis="x", rotation=15)
fig.savefig(FIGURES_DIR / "comparaison_equilibrage.png", dpi=120, bbox_inches="tight")
plt.close(fig)

print("\nLe jeu de test n'a pas été utilisé ici. Fin de l'étape 2.")
