"""Étape 4 : comparer 5 modèles en CV 5 folds, puis régler le meilleur."""

import time

import joblib
import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import auc, make_scorer, precision_recall_curve
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold, cross_validate
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline as SkPipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier
from xgboost import XGBClassifier

from config import RANDOM_STATE, PROCESSED_DIR, FIGURES_DIR, TABLES_DIR, MODELS_DIR


def pr_auc_macro(y_true, y_score, classes):
    """Aire sous la courbe précision-rappel de chaque classe, puis moyenne."""
    y_binaire = (np.asarray(y_true)[:, None] == np.asarray(classes)).astype(int)
    aires = []
    for i in range(len(classes)):
        precision, rappel, _ = precision_recall_curve(y_binaire[:, i], y_score[:, i])
        aires.append(auc(rappel, precision))
    return float(np.mean(aires))


def construire_pipeline(modele, cible_smote):
    """Imputation, mise à l'échelle, SMOTE puis modèle."""
    return ImbPipeline([
        ("imputation", SimpleImputer(strategy="median")),
        ("scaling", StandardScaler()),
        ("equilibrage", SMOTE(sampling_strategy=cible_smote, random_state=RANDOM_STATE)),
        ("modele", modele),
    ])


with open(PROCESSED_DIR / "selected_features.txt", encoding="utf-8") as fichier:
    colonnes = [ligne.strip() for ligne in fichier if ligne.strip()]

train = pd.read_csv(PROCESSED_DIR / "train.csv", usecols=colonnes + ["Family"])
# XGBoost exige des labels numériques : on code les familles une fois pour toutes
encodeur = LabelEncoder()
y = encodeur.fit_transform(train["Family"])
joblib.dump(encodeur, MODELS_DIR / "label_encoder.joblib")
CLASSES = list(range(len(encodeur.classes_)))
X = train[colonnes]
print("Train :", len(X), "lignes et", len(colonnes), "variables retenues")

# cibles SMOTE calculées une fois sur le train, puis appliquées dans chaque fold
comptage = pd.Series(y).value_counts()
majoritaire = comptage.idxmax()
cible_smote = {}
for classe, nb in comptage.drop(majoritaire).items():
    cible_smote[classe] = min(int(0.2 * comptage[majoritaire]), 10 * int(nb))

modeles = {
    "Random Forest": RandomForestClassifier(n_estimators=200, max_depth=15,
                                            n_jobs=-1, random_state=RANDOM_STATE),
    "XGBoost": XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.1,
                             subsample=0.8, colsample_bytree=0.8, tree_method="hist",
                             eval_metric="mlogloss", verbosity=0, n_jobs=-1,
                             random_state=RANDOM_STATE),
    "Regression logistique": LogisticRegression(max_iter=1000, random_state=RANDOM_STATE),
    "Arbre de decision": DecisionTreeClassifier(max_depth=12, random_state=RANDOM_STATE),
    "kNN": KNeighborsClassifier(n_neighbors=5),
}

scoring = {
    "f1_macro": "f1_macro",
    "f1_pondere": "f1_weighted",
    "rappel_macro": "recall_macro",
    "precision_macro": "precision_macro",
    "pr_auc_macro": make_scorer(pr_auc_macro, classes=CLASSES,
                                response_method="predict_proba"),
}

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
lignes = []

for nom, modele in modeles.items():
    debut = time.time()
    scores = cross_validate(construire_pipeline(modele, cible_smote), X, y,
                            cv=cv, scoring=scoring)
    ligne = {"modele": nom}
    for cle in scoring:
        ligne[cle + "_moy"] = round(scores["test_" + cle].mean(), 4)
        ligne[cle + "_std"] = round(scores["test_" + cle].std(), 4)
    ligne["temps_s"] = round(time.time() - debut, 1)
    lignes.append(ligne)
    print(nom, "F1 macro =", ligne["f1_macro_moy"], "+/-", ligne["f1_macro_std"],
          "PR-AUC =", ligne["pr_auc_macro_moy"])

comparaison = pd.DataFrame(lignes)
comparaison.to_csv(TABLES_DIR / "comparaison_modeles.csv", index=False)

fig, ax = plt.subplots(figsize=(10, 4))
ax.bar(comparaison["modele"], comparaison["f1_macro_moy"],
       yerr=comparaison["f1_macro_std"], capsize=4, color="steelblue")
ax.set_ylim(0, 1)
ax.set_title("F1 macro en validation croisée 5 folds (train uniquement)")
ax.set_ylabel("F1 macro")
ax.tick_params(axis="x", rotation=20)
fig.savefig(FIGURES_DIR / "comparaison_modeles.png", dpi=120, bbox_inches="tight")
plt.close(fig)

# écart-type : si les intervalles se chevauchent, on ne conclut pas à une différence nette
ordonne = comparaison.sort_values("f1_macro_moy", ascending=False)
premier, deuxieme = ordonne.iloc[0], ordonne.iloc[1]
nettet = premier["f1_macro_moy"] - premier["f1_macro_std"] > deuxieme["f1_macro_moy"] + deuxieme["f1_macro_std"]
print("Écart net entre les deux premiers :", nettet)

# petit réglage des deux meilleurs modèles, toujours sur le train
grilles = {
    "Random Forest": {
        "modele__n_estimators": [100, 200],
        "modele__max_depth": [10, 15],
        "modele__min_samples_leaf": [1, 2],
    },
    "XGBoost": {
        "modele__n_estimators": [150, 250],
        "modele__max_depth": [4, 6],
        "modele__learning_rate": [0.05, 0.1],
    },
    "Regression logistique": {
        "modele__C": [0.1, 1, 10],
        "modele__max_iter": [500, 1000],
    },
    "Arbre de decision": {
        "modele__max_depth": [8, 12, 16, None],
        "modele__min_samples_leaf": [1, 2, 4],
    },
    "kNN": {
        "modele__n_neighbors": [3, 5, 9],
        "modele__weights": ["uniform", "distance"],
    },
}

cv_tuning = StratifiedKFold(n_splits=3, shuffle=True, random_state=RANDOM_STATE)
reglages = []
meilleurs_params = {}

for nom in [premier["modele"], deuxieme["modele"]]:
    pipeline_recherche = construire_pipeline(modeles[nom], cible_smote)
    if nom in ("Random Forest", "XGBoost"):
        pipeline_recherche.set_params(modele__n_jobs=1)
    recherche = RandomizedSearchCV(
        pipeline_recherche, grilles[nom],
        n_iter=4, scoring="f1_macro", cv=cv_tuning,
        random_state=RANDOM_STATE, n_jobs=-1,
    )
    debut = time.time()
    recherche.fit(X, y)
    meilleurs_params[nom] = recherche.best_params_
    reglages.append({
        "modele": nom,
        "meilleur_f1_cv": round(recherche.best_score_, 4),
        "parametres": str(recherche.best_params_),
        "temps_s": round(time.time() - debut, 1),
    })
    print("Réglage", nom, "->", reglages[-1]["meilleur_f1_cv"])

pd.DataFrame(reglages).to_csv(TABLES_DIR / "meilleurs_parametres.csv", index=False)

# réévaluation avec la MÊME CV 5 folds pour comparer réglés et non réglés
pipes_reglees = {}
lignes_reglees = []
for nom in meilleurs_params:
    pipe = construire_pipeline(modeles[nom], cible_smote)
    pipe.set_params(**meilleurs_params[nom])
    pipes_reglees[nom] = pipe
    scores = cross_validate(pipe, X, y, cv=cv, scoring=scoring)
    lignes_reglees.append({
        "modele": nom,
        "f1_macro_moy": round(scores["test_f1_macro"].mean(), 4),
        "f1_macro_std": round(scores["test_f1_macro"].std(), 4),
        "pr_auc_macro_moy": round(scores["test_pr_auc_macro"].mean(), 4),
    })
    print("Réévaluation 5 folds", nom, "->", lignes_reglees[-1]["f1_macro_moy"])
reglees = pd.DataFrame(lignes_reglees)
reglees.to_csv(TABLES_DIR / "comparaison_apres_reglage.csv", index=False)

# le meilleur modèle réglé est entraîné sur tout le train et sauvegardé
choix = reglees.sort_values("f1_macro_moy", ascending=False).iloc[0]
nom_final = choix["modele"]
pipeline_final = pipes_reglees[nom_final]
pipeline_final.fit(X, y)

# on retire le SMOTE de la chaîne : il ne doit jamais agir au moment de prédire
pipeline_inference = SkPipeline([
    ("imputation", pipeline_final.named_steps["imputation"]),
    ("scaling", pipeline_final.named_steps["scaling"]),
    ("modele", pipeline_final.named_steps["modele"]),
])
joblib.dump(pipeline_inference, MODELS_DIR / "final_model.joblib")

pd.DataFrame({
    "modele": [nom_final],
    "f1_cv": [choix["f1_macro_moy"]],
    "variables": [len(colonnes)],
}).to_csv(TABLES_DIR / "meilleur_modele.csv", index=False)

print("\nModèle final sauvegardé :", nom_final, "-> models/final_model.joblib")
print("Le test n'a toujours pas été utilisé.")
