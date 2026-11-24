"""Étape 1 : charger les CSV, construire l'échantillon et explorer les données."""

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from config import (RANDOM_STATE, SAMPLE_FRACTION, RARE_MAX, SAMPLE_FILE,
                    RAW_DIR, PROCESSED_DIR, FIGURES_DIR, TABLES_DIR,
                    FAMILIES, FAMILY_ORDER, KEY_FEATURES)


def charger_csv():
    dossier = RAW_DIR / "MachineLearningCVE"
    if not dossier.exists():
        dossier = RAW_DIR

    fichiers = sorted(dossier.glob("*.csv"))
    if not fichiers:
        print("Place les 8 CSV dans data/raw ou data/raw/MachineLearningCVE.")
        raise SystemExit(1)

    frames = []
    for fichier in fichiers:
        tmp = pd.read_csv(fichier, low_memory=False)
        tmp.columns = [col.strip() for col in tmp.columns]  # les colonnes ont un espace devant
        tmp["source_file"] = fichier.name
        tmp["jour"] = fichier.name.split("-")[0]
        frames.append(tmp)
        print("lu", fichier.name, len(tmp), "lignes")

    return pd.concat(frames, ignore_index=True)


def echantillonner(df):
    morceaux = []
    for famille, groupe in df.groupby("Family"):
        n = len(groupe) if len(groupe) <= RARE_MAX else round(len(groupe) * SAMPLE_FRACTION)
        morceaux.append(groupe.sample(n, random_state=RANDOM_STATE))
    return pd.concat(morceaux).sample(frac=1, random_state=RANDOM_STATE).reset_index(drop=True)


def sauvegarder_table(table, nom):
    table.to_csv(TABLES_DIR / nom, index=False)


def sauvegarder_figure(fig, nom):
    fig.savefig(FIGURES_DIR / nom, dpi=120, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# 1. Chargement et nettoyage des libellés
# ---------------------------------------------------------------------------
df = charger_csv()
print("\nBrut :", len(df), "lignes et", df.shape[1], "colonnes")

df["Label"] = df["Label"].astype(str).str.strip()
# certains CSV contiennent un caractère bizarre à la place de l'espace
df["Label"] = df["Label"].str.replace(r"[^\w\s-]+", " ", regex=True)
df["Label"] = df["Label"].str.replace(r"\s+", " ", regex=True)

lookup = {nom.lower(): famille for nom, famille in FAMILIES.items()}
df["Family"] = df["Label"].str.lower().map(lookup).fillna("AUTRE")
inconnus = sorted(df.loc[df["Family"] == "AUTRE", "Label"].unique())
print("Libellés non reconnus :", inconnus)

print("\nFamilles dans le jeu complet :")
print(df["Family"].value_counts().to_string())

# ---------------------------------------------------------------------------
# 2. Échantillon stratifié
# ---------------------------------------------------------------------------
df = echantillonner(df)
df.to_csv(PROCESSED_DIR / SAMPLE_FILE, index=False)
print("\nÉchantillon :", len(df), "lignes")
print("Mémoire (Mo) :", round(df.memory_usage(deep=True).sum() / 1e6, 1))
print("Types :", df.dtypes.value_counts().to_dict())

# ---------------------------------------------------------------------------
# 3. Distribution des classes
# ---------------------------------------------------------------------------
ordre = [famille for famille in FAMILY_ORDER if famille in df["Family"].unique()]
familles = df["Family"].value_counts().reindex(ordre)
distribution = pd.DataFrame({"famille": familles.index,
                             "effectif": familles.values,
                             "pourcent": (100 * familles.values / len(df)).round(2)})
sauvegarder_table(distribution, "distribution_classes.csv")
print("\nDistribution de l'échantillon :")
print(distribution.to_string(index=False))

fig, ax = plt.subplots(figsize=(10, 4))
ax.bar(distribution["famille"], distribution["effectif"], color="steelblue")
ax.set_yscale("log")
ax.set_title("Nombre de flux par famille (échelle log)")
ax.set_ylabel("Nombre de flux")
ax.tick_params(axis="x", rotation=35)
sauvegarder_figure(fig, "distribution_classes.png")

# ---------------------------------------------------------------------------
# 4. Valeurs manquantes, infinies, colonnes constantes et doublons
# ---------------------------------------------------------------------------
manquants = df.isna().sum()
manquants = manquants[manquants > 0].sort_values(ascending=False)
table_manquants = pd.DataFrame({"colonne": manquants.index,
                                "nb_manquant": manquants.values,
                                "pourcent": (100 * manquants.values / len(df)).round(3)})
sauvegarder_table(table_manquants, "valeurs_manquantes.csv")

colonnes_num = list(df.select_dtypes(include="number").columns)
nb_infinis = {}
for col in colonnes_num:
    nb = int(np.isinf(df[col].to_numpy(dtype=float)).sum())
    if nb > 0:
        nb_infinis[col] = nb
table_infinis = pd.DataFrame({"colonne": list(nb_infinis),
                              "nb_infini": list(nb_infinis.values())})
sauvegarder_table(table_infinis, "valeurs_infinies.csv")

uniques = df.nunique(dropna=False)
constantes = uniques[uniques <= 1]
sauvegarder_table(pd.DataFrame({"colonne": constantes.index}), "colonnes_constantes.csv")

# on ignorera 'Family', 'source_file' et 'jour' dans la recherche de doublons
colonnes_features = [c for c in colonnes_num]
doublons_exacts = int(df.duplicated(colonnes_features + ["Label"]).sum())
doublons_features = int(df.duplicated(colonnes_features).sum())
table_doublons = pd.DataFrame({
    "type": ["lignes identiques (features + label)", "mêmes features, label ignoré"],
    "nombre": [doublons_exacts, doublons_features],
    "pourcent": [round(100 * doublons_exacts / len(df), 2),
                 round(100 * doublons_features / len(df), 2)]
})
sauvegarder_table(table_doublons, "doublons.csv")

print("\nQualité :")
print("  valeurs manquantes :", int(manquants.sum()), "cellules")
print("  valeurs infinies   :", sum(nb_infinis.values()), "cellules")
print("  colonnes constantes:", len(constantes))
print("  doublons           :", doublons_exacts, "(", table_doublons.loc[0, "pourcent"], "%)")

if len(table_manquants) > 0:
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.bar(table_manquants["colonne"], table_manquants["pourcent"], color="indianred")
    ax.set_title("Colonnes avec des valeurs manquantes")
    ax.set_ylabel("Pourcentage")
    ax.tick_params(axis="x", rotation=35)
    sauvegarder_figure(fig, "valeurs_manquantes.png")

# ---------------------------------------------------------------------------
# 5. Distributions par classe et corrélations
# ---------------------------------------------------------------------------
# 1 000 lignes par famille suffisent pour des boxplots lisibles
plot_df = df.groupby("Family", group_keys=False).head(1000)

for feature in KEY_FEATURES:
    if feature not in df.columns:
        continue
    fig, ax = plt.subplots(figsize=(11, 4))
    sns.boxplot(data=plot_df, x="Family", y=feature, order=ordre,
                showfliers=False, ax=ax, color="lightsteelblue")
    ax.set_yscale("symlog", linthresh=0.1)
    ax.set_title(feature + " par famille")
    ax.tick_params(axis="x", rotation=35)
    sauvegarder_figure(fig, "box_" + feature.lower().replace(" ", "_").replace("/", "_") + ".png")

for feature in ["Flow Duration", "Packet Length Mean"]:
    fig, ax = plt.subplots(figsize=(8, 4))
    for famille in ordre[:4]:
        valeurs = plot_df.loc[plot_df["Family"] == famille, feature]
        valeurs = valeurs[valeurs > 0]
        if len(valeurs) > 0:
            ax.hist(valeurs, bins=np.logspace(np.log10(valeurs.min()),
                    np.log10(valeurs.max()), 30), alpha=0.5, label=famille)
    ax.set_xscale("log")
    ax.set_title("Histogramme log : " + feature)
    ax.set_xlabel(feature)
    ax.legend(fontsize=8)
    sauvegarder_figure(fig, "hist_" + feature.lower().replace(" ", "_") + ".png")

corr = df[colonnes_num].corr()
fig, ax = plt.subplots(figsize=(15, 12))
sns.heatmap(corr, cmap="coolwarm", vmin=-1, vmax=1, ax=ax,
            cbar_kws={"shrink": 0.8})
ax.set_title("Corrélations entre variables numériques")
ax.tick_params(axis="x", rotation=90, labelsize=6)
ax.tick_params(axis="y", labelsize=6)
sauvegarder_figure(fig, "correlations.png")

masque = np.triu(np.ones(corr.shape, dtype=bool), k=1)
paires = corr.where(masque).stack().rename("correlation").reset_index()
paires.columns = ["variable_1", "variable_2", "correlation"]
paires = paires[paires["correlation"].abs() > 0.95]
paires = paires.reindex(paires["correlation"].abs().sort_values(ascending=False).index)
sauvegarder_table(paires, "correlations_fortes.csv")
print("Paires de variables corrélées à plus de 0,95 :", len(paires))

print("\nFin de l'étape 1. Figures et tableaux écrits dans reports/.")
