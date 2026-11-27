"""Étape 3 : sélection de variables sur le train uniquement."""

import time

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import SelectFromModel, SelectKBest, VarianceThreshold, f_classif
from sklearn.impute import SimpleImputer
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline

from config import RANDOM_STATE, PROCESSED_DIR, FIGURES_DIR, TABLES_DIR

SIGNIFICATION = {
    "Destination Port": "port de la machine cible, donc service visé",
    "Flow Duration": "durée totale du flux",
    "Total Fwd Packets": "nombre de paquets envoyés dans le sens initial",
    "Total Backward Packets": "nombre de paquets en réponse",
    "Total Length of Fwd Packets": "octets envoyés dans le sens initial",
    "Total Length of Bwd Packets": "octets reçus en réponse",
    "Flow Bytes/s": "débit du flux en octets par seconde",
    "Flow Packets/s": "débit du flux en paquets par seconde",
    "Flow IAT Mean": "temps moyen entre deux paquets",
    "Flow IAT Std": "variation du temps entre paquets",
    "Flow IAT Max": "plus long silence entre deux paquets",
    "Flow IAT Min": "plus court intervalle entre deux paquets",
    "Fwd IAT Mean": "temps moyen entre paquets envoyés",
    "Bwd IAT Mean": "temps moyen entre paquets reçus",
    "Fwd Packet Length Mean": "taille moyenne des paquets envoyés",
    "Bwd Packet Length Mean": "taille moyenne des paquets reçus",
    "Packet Length Mean": "taille moyenne de tous les paquets",
    "Packet Length Std": "variabilité des tailles de paquets",
    "Packet Length Variance": "variance des tailles de paquets",
    "Average Packet Size": "taille moyenne globale des paquets",
    "Min Packet Length": "plus petit paquet observé",
    "Max Packet Length": "plus grand paquet observé",
    "FIN Flag Count": "drapeau TCP de fermeture normale",
    "SYN Flag Count": "drapeau TCP d'ouverture de connexion",
    "RST Flag Count": "drapeau TCP de fermeture brutale",
    "PSH Flag Count": "drapeau TCP de poussée des données",
    "ACK Flag Count": "drapeau TCP d'acquittement",
    "URG Flag Count": "drapeau TCP de données urgentes",
    "CWE Flag Count": "drapeau TCP de congestion",
    "ECE Flag Count": "drapeau TCP de notification ECN",
    "Fwd PSH Flags": "poussée de données dans le sens initial",
    "Fwd URG Flags": "données urgentes dans le sens initial",
    "Fwd Header Length": "taille de l'en-tête TCP envoyé",
    "Bwd Header Length": "taille de l'en-tête TCP reçu",
    "Fwd Header Length.1": "copie de Fwd Header Length calculée par CICFlowMeter",
    "Down/Up Ratio": "rapport entre trafic descendant et montant",
    "Init_Win_bytes_forward": "fenêtre TCP Initiale dans le sens initial",
    "Init_Win_bytes_backward": "fenêtre TCP initiale dans le sens réponse",
    "act_data_pkt_fwd": "nombre de paquets avec des données utiles",
    "min_seg_size_forward": "plus petit segment TCP envoyé",
    "Subflow Fwd Packets": "paquets dans un sous-flux (égal à Total Fwd ici)",
    "Subflow Bwd Packets": "paquets dans le sous-flux inverse",
    "Subflow Fwd Bytes": "octets dans un sous-flux",
    "Subflow Bwd Bytes": "octets dans le sous-flux inverse",
    "Active Mean": "durée moyenne des périodes actives du flux",
    "Idle Mean": "durée moyenne des périodes d'inactivité",
}

K_VALUES = [5, 10, 15, 25, 40, 70]


def modele():
    """Forêt fixe, utilisée pour les importances et pour noter les sélections."""
    return RandomForestClassifier(n_estimators=60, max_depth=12, n_jobs=-1,
                                  class_weight="balanced_subsample", random_state=RANDOM_STATE)


train = pd.read_csv(PROCESSED_DIR / "train.csv", low_memory=False)
y = train["Family"]
X = train.drop(columns=["Family"])
features = list(X.columns)
print("Départ :", X.shape[1], "variables et", len(X), "lignes de train")

# 1. paires redondantes, mesurées sur le train seulement
imputation = SimpleImputer(strategy="median")
X_impute = imputation.fit_transform(X)
corr = pd.DataFrame(X_impute, columns=features).corr().abs()
masque = np.triu(np.ones(corr.shape, dtype=bool), k=1)
paires = corr.where(masque).stack().rename("correlation").reset_index()
paires.columns = ["variable_1", "variable_2", "correlation"]
paires = paires[paires["correlation"] > 0.95]
paires.to_csv(TABLES_DIR / "correlations_train.csv", index=False)
print("Paires redondantes sur le train :", len(paires))

# 2. classement par ANOVA et par importance Random Forest (train uniquement)
scores_anova, _ = f_classif(X_impute, y)
foret = modele()
foret.fit(X_impute, y)

classement = pd.DataFrame({
    "feature": features,
    "f_anova": scores_anova,
    "importance_rf": foret.feature_importances_,
})
classement["rang_anova"] = classement["f_anova"].rank(ascending=False, method="min")
classement["rang_rf"] = classement["importance_rf"].rank(ascending=False, method="min")
top = classement[(classement["rang_anova"] <= 15) | (classement["rang_rf"] <= 15)].copy()
top["signification"] = top["feature"].map(SIGNIFICATION).fillna("statistique de flux CICFlowMeter")
top = top.sort_values(["rang_rf", "rang_anova"])
top.to_csv(TABLES_DIR / "top15_features.csv", index=False)
print("\nVariables les plus utiles (union des tops 15) :")
print(top[["feature", "rang_anova", "rang_rf", "signification"]].head(15).to_string(index=False))

# 3. courbe F1 macro selon le nombre de variables gardées
# les deux sélections sont DANS le pipeline : chaque fold recalcule la sienne
cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=RANDOM_STATE)
resultats = []

for methode in ["anova", "random_forest"]:
    for k in K_VALUES:
        if methode == "anova":
            selection = SelectKBest(score_func=f_classif, k=k)
        else:
            selection = SelectFromModel(modele(), threshold=-np.inf, max_features=k)

        pipe = Pipeline([
            ("imputation", SimpleImputer(strategy="median")),
            ("variance", VarianceThreshold()),
            ("selection", selection),
            ("modele", modele()),
        ])
        debut = time.time()
        scores = cross_val_score(pipe, X, y, cv=cv, scoring="f1_macro")
        resultats.append({
            "methode": methode,
            "nb_variables": k,
            "f1_moy": round(scores.mean(), 4),
            "f1_std": round(scores.std(), 4),
            "temps_s": round(time.time() - debut, 1),
        })
        print(methode, "k =", k, "F1 =", resultats[-1]["f1_moy"])

courbe = pd.DataFrame(resultats)
courbe.to_csv(TABLES_DIR / "courbe_selection.csv", index=False)

fig, ax = plt.subplots(figsize=(8, 5))
for methode, couleur in [("anova", "steelblue"), ("random_forest", "darkorange")]:
    partie = courbe[courbe["methode"] == methode]
    ax.errorbar(partie["nb_variables"], partie["f1_moy"], yerr=partie["f1_std"],
                marker="o", label=methode, color=couleur, capsize=3)
ax.set_title("F1 macro selon le nombre de variables gardées")
ax.set_xlabel("Nombre de variables")
ax.set_ylabel("F1 macro (validation croisée sur le train)")
ax.legend()
ax.grid(alpha=0.3)
fig.savefig(FIGURES_DIR / "courbe_selection.png", dpi=120, bbox_inches="tight")
plt.close(fig)

# 4. contrôle : le port de destination est-il un raccourci trompeur ?
X_sans_port = X.drop(columns=["Destination Port"])
controle = []
for cas, donnees in [("avec Destination Port", X), ("sans Destination Port", X_sans_port)]:
    pipe = Pipeline([
        ("imputation", SimpleImputer(strategy="median")),
        ("variance", VarianceThreshold()),
        ("selection", SelectFromModel(modele(), threshold=-np.inf, max_features=15)),
        ("modele", modele()),
    ])
    scores = cross_val_score(pipe, donnees, y, cv=cv, scoring="f1_macro")
    controle.append({"cas": cas, "f1_moy": round(scores.mean(), 4),
                     "f1_std": round(scores.std(), 4)})
    print(cas, "F1 =", controle[-1]["f1_moy"])
pd.DataFrame(controle).to_csv(TABLES_DIR / "controle_port.csv", index=False)

# 5. choix final : 15 variables choisies par la forêt, sans le port
# 70 variables donnent 0,8689 mais 15 suffisent à garder 0,8398 (-0,029)
# avec un temps d'inférence bien plus faible et moins de biais de service.
X_final_impute = SimpleImputer(strategy="median").fit_transform(X_sans_port)
foret_finale = modele()
foret_finale.fit(X_final_impute, y)
classement_final = pd.DataFrame({
    "feature": X_sans_port.columns,
    "importance_rf": foret_finale.feature_importances_,
})
colonnes_finales = list(classement_final.sort_values("importance_rf", ascending=False)["feature"][:15])
f1_final = controle[1]["f1_moy"]

with open(PROCESSED_DIR / "selected_features.txt", "w", encoding="utf-8") as fichier:
    fichier.write("\n".join(colonnes_finales))

top["dans_selection_finale"] = top["feature"].isin(colonnes_finales)
top.to_csv(TABLES_DIR / "top15_features.csv", index=False)

pd.DataFrame({
    "methode": ["Random Forest, sans Destination Port"],
    "nb_variables": [len(colonnes_finales)],
    "f1_moy": [f1_final],
    "variables": [", ".join(colonnes_finales)],
}).to_csv(TABLES_DIR / "selection_finale.csv", index=False)

print("\nChoix final :", len(colonnes_finales), "variables (F1 =", f1_final, ")")
print("Liste sauvegardée dans data/processed/selected_features.txt")
