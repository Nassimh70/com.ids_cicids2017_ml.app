"""Étape 5 : évaluation unique sur le jeu de test jamais utilisé."""

import joblib
import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, auc, balanced_accuracy_score,
                             classification_report, confusion_matrix, f1_score,
                             precision_recall_curve, precision_score, recall_score)

from config import (PROCESSED_DIR, FIGURES_DIR, TABLES_DIR,
                    MODELS_DIR, FAMILY_ORDER)


def pr_auc_macro(y_true, y_score, classes):
    """Aire sous la courbe précision-rappel de chaque classe, puis moyenne."""
    y_binaire = (np.asarray(y_true)[:, None] == np.asarray(classes)).astype(int)
    aires = []
    for i in range(len(classes)):
        precision, rappel, _ = precision_recall_curve(y_binaire[:, i], y_score[:, i])
        aires.append(auc(rappel, precision))
    return float(np.mean(aires))


with open(PROCESSED_DIR / "selected_features.txt", encoding="utf-8") as fichier:
    colonnes = [ligne.strip() for ligne in fichier if ligne.strip()]

test = pd.read_csv(PROCESSED_DIR / "test.csv", usecols=colonnes + ["Family"])
X_test = test[colonnes]
y_vrai = test["Family"]

modele = joblib.load(MODELS_DIR / "final_model.joblib")
encodeur = joblib.load(MODELS_DIR / "label_encoder.joblib")

y_code = encodeur.transform(y_vrai)
y_pred_code = modele.predict(X_test)
probabilites = modele.predict_proba(X_test)

y_pred = encodeur.inverse_transform(y_pred_code)
classes = list(range(len(encodeur.classes_)))
print("Test :", len(X_test), "flux,", len(colonnes), "variables,",
      len(classes), "familles")

# 1. métriques globales : une seule passe sur le test
metriques = {
    "accuracy": round(accuracy_score(y_code, y_pred_code), 4),
    "balanced_accuracy": round(balanced_accuracy_score(y_code, y_pred_code), 4),
    "f1_macro": round(f1_score(y_code, y_pred_code, average="macro", zero_division=0), 4),
    "f1_pondere": round(f1_score(y_code, y_pred_code, average="weighted", zero_division=0), 4),
    "precision_macro": round(precision_score(y_code, y_pred_code, average="macro", zero_division=0), 4),
    "rappel_macro": round(recall_score(y_code, y_pred_code, average="macro", zero_division=0), 4),
    "pr_auc_macro": round(pr_auc_macro(y_code, probabilites, classes), 4),
}
pd.DataFrame([metriques]).to_csv(TABLES_DIR / "metriques_test.csv", index=False)
print("Métriques globales :", metriques)

# 2. rapport par famille
rapport = classification_report(y_code, y_pred_code, labels=classes,
                                target_names=encodeur.classes_,
                                output_dict=True, zero_division=0)
lignes = []
for famille, valeurs in rapport.items():
    if isinstance(valeurs, dict):
        lignes.append({"famille": famille,
                       "precision": round(valeurs["precision"], 4),
                       "rappel": round(valeurs["recall"], 4),
                       "f1": round(valeurs["f1-score"], 4),
                       "support": int(valeurs["support"])})
par_famille = pd.DataFrame(lignes)
par_famille.to_csv(TABLES_DIR / "rapport_classification.csv", index=False)
print("\nRésultats par famille :")
print(par_famille.to_string(index=False))

# 3. comparaison avec la CV de l'étape 4 (mêmes métriques disponibles)
cv = pd.read_csv(TABLES_DIR / "comparaison_apres_reglage.csv")
meilleur_cv = cv.sort_values("f1_macro_moy", ascending=False).iloc[0]
comparaison = pd.DataFrame([
    {"jeu": "CV 5 folds (train)", "f1_macro": meilleur_cv["f1_macro_moy"],
     "pr_auc_macro": meilleur_cv["pr_auc_macro_moy"]},
    {"jeu": "Test intact", "f1_macro": metriques["f1_macro"],
     "pr_auc_macro": metriques["pr_auc_macro"]},
])
comparaison.to_csv(TABLES_DIR / "comparaison_test_cv.csv", index=False)
print("\nCV vs test :")
print(comparaison.to_string(index=False))

# 4. matrice de confusion, avec les familles dans l'ordre du projet
matrice = confusion_matrix(y_code, y_pred_code, labels=classes)
ordre = [famille for famille in FAMILY_ORDER if famille in encodeur.classes_]
_indices = [list(encodeur.classes_).index(famille) for famille in ordre]
matrice_ordonee = matrice[np.ix_(_indices, _indices)]

fig, ax = plt.subplots(figsize=(7, 6))
image = ax.imshow(matrice_ordonee, cmap="Blues")
ax.set_xticks(range(len(ordre)), ordre, rotation=45, ha="right")
ax.set_yticks(range(len(ordre)), ordre)
ax.set_xlabel("Famille prédite")
ax.set_ylabel("Famille réelle")
ax.set_title("Matrice de confusion sur le test")
for i in range(len(ordre)):
    for j in range(len(ordre)):
        ax.text(j, i, str(matrice_ordonee[i, j]), ha="center", va="center",
                color="white" if matrice_ordonee[i, j] > matrice_ordonee.max() / 2 else "black",
                fontsize=8)
fig.colorbar(image, ax=ax, shrink=0.8)
fig.savefig(FIGURES_DIR / "matrice_confusion_test.png", dpi=120, bbox_inches="tight")
plt.close(fig)

# 5. graphique simple du F1 par famille
fig, ax = plt.subplots(figsize=(9, 4))
ax.bar(par_famille["famille"], par_famille["f1"], color="steelblue")
ax.set_ylim(0, 1)
ax.set_ylabel("F1")
ax.set_title("F1 par famille sur le test")
ax.tick_params(axis="x", rotation=30)
fig.savefig(FIGURES_DIR / "f1_par_famille_test.png", dpi=120, bbox_inches="tight")
plt.close(fig)

# 6. erreurs gardées pour l'analyse critique de l'étape 6
masque_erreur = y_pred_code != y_code
erreurs = test.loc[masque_erreur, colonnes].copy()
erreurs.insert(0, "confiance", probabilites[masque_erreur].max(axis=1).round(4))
erreurs.insert(0, "famille_predite", y_pred[masque_erreur])
erreurs.insert(0, "famille_reelle", y_vrai[masque_erreur].values)
erreurs.to_csv(TABLES_DIR / "erreurs_test.csv", index=False)
print("\nErreurs sauvegardées :", len(erreurs))
print("Fin de l'étape 5 : le test n'est plus réutilisé pour choisir un modèle.")
