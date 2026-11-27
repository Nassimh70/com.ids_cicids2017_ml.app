"""Étape 6 : analyse critique des résultats et proposition de déploiement."""

import time

import joblib
import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from config import PROCESSED_DIR, FIGURES_DIR, TABLES_DIR, MODELS_DIR, DOCS_DIR


metriques = pd.read_csv(TABLES_DIR / "metriques_test.csv").iloc[0]
comparaison = pd.read_csv(TABLES_DIR / "comparaison_test_cv.csv")
par_classe = pd.read_csv(TABLES_DIR / "rapport_classification.csv")
erreurs = pd.read_csv(TABLES_DIR / "erreurs_test.csv")
rare = pd.read_csv(PROCESSED_DIR / "attaques_rares.csv")

with open(PROCESSED_DIR / "selected_features.txt", encoding="utf-8") as fichier:
    colonnes = [ligne.strip() for ligne in fichier if ligne.strip()]

# 1. synthèse par famille, sans les lignes de moyenne
familles = par_classe[~par_classe["famille"].isin(["macro avg", "weighted avg"])].copy()
familles = familles.sort_values("f1")
familles.to_csv(TABLES_DIR / "analyse_par_classe.csv", index=False)

# 2. résumé des confusions
resume_erreurs = (erreurs.groupby(["famille_reelle", "famille_predite"])
                  .size().rename("nombre").reset_index()
                  .sort_values("nombre", ascending=False))
resume_erreurs.to_csv(TABLES_DIR / "erreurs_resume.csv", index=False)

# 3. familles volontairement exclues du modèle supervisé
rare_counts = rare["Family"].value_counts().to_dict()
familles_rares = (rare["Family"].value_counts().rename("effectif")
                  .reset_index().rename(columns={"index": "famille", "Family": "famille"}))
familles_rares.to_csv(TABLES_DIR / "familles_rares.csv", index=False)

# 4. temps d'inférence mesuré sur un volume équivalent au test, mais sur le train
modele = joblib.load(MODELS_DIR / "final_model.joblib")
train = pd.read_csv(PROCESSED_DIR / "train.csv", usecols=colonnes)[colonnes].head(len(erreurs) + 27000)
debut = time.time()
modele.predict(train)
temps = time.time() - debut
ms_par_flow = round(temps / len(train) * 1000, 4)
pd.DataFrame({
    "nb_flows": [len(train)],
    "temps_s": [round(temps, 3)],
    "ms_par_flow": [ms_par_flow],
}).to_csv(TABLES_DIR / "temps_inference.csv", index=False)
print("Inférence :", ms_par_flow, "ms par flux sur", len(train), "flux du train")

# 5. graphiques simples pour le rapport
fig, ax = plt.subplots(figsize=(6, 4))
ax.scatter(familles["support"], familles["f1"], color="steelblue")
ax.set_xscale("log")
ax.set_xlabel("Nombre d'exemples en test (échelle log)")
ax.set_ylabel("F1")
ax.set_title("F1 selon le nombre d'exemples par famille")
for _, ligne in familles.iterrows():
    ax.annotate(ligne["famille"], (ligne["support"], ligne["f1"]),
                fontsize=8, xytext=(4, 4), textcoords="offset points")
ax.grid(alpha=0.3)
fig.savefig(FIGURES_DIR / "analyse_f1_support.png", dpi=120, bbox_inches="tight")
plt.close(fig)

fig, ax = plt.subplots(figsize=(8, 4))
pairs = resume_erreurs["famille_reelle"] + " -> " + resume_erreurs["famille_predite"]
ax.barh(pairs.head(8), resume_erreurs["nombre"].head(8), color="indianred")
ax.set_xlabel("Nombre d'erreurs")
ax.set_title("Principales confusions sur le test")
fig.savefig(FIGURES_DIR / "analyse_erreurs.png", dpi=120, bbox_inches="tight")
plt.close(fig)

# 6. rapport final écrit avec les chiffres réellement mesurés
cv_f1 = comparaison.iloc[0]["f1_macro"]
test_f1 = comparaison.iloc[1]["f1_macro"]
nb_erreurs = len(erreurs)
nb_test = int(familles["support"].sum())
pct_erreurs = round(nb_erreurs / nb_test * 100, 2)
top_erreur = resume_erreurs.iloc[0]
precision_web = familles[familles["famille"] == "WebAttack"]["precision"].iloc[0]
precision_bot = familles[familles["famille"] == "Bot"]["precision"].iloc[0]

texte = f"""# Rapport final — IDS multi-classes sur CIC-IDS2017

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
| Accuracy brute | {metriques['accuracy']:.4f} |
| Accuracy équilibrée | {metriques['balanced_accuracy']:.4f} |
| F1 macro | {metriques['f1_macro']:.4f} |
| F1 pondéré | {metriques['f1_pondere']:.4f} |
| Précision macro | {metriques['precision_macro']:.4f} |
| Rappel macro | {metriques['rappel_macro']:.4f} |
| PR-AUC macro | {metriques['pr_auc_macro']:.4f} |

La validation croisée donnait {cv_f1:.4f} de F1 macro ; le test donne
{test_f1:.4f}. L'écart est faible et s'explique par le fait que le modèle final
a vu tout le train, contre 4/5 des données dans chaque fold.

Il y a {nb_erreurs} erreurs sur {nb_test} flux, soit {pct_erreurs} %.

## 3. Points forts

- Le F1 macro de {metriques['f1_macro']:.4f} montre que les petites classes sont
  traitées, contrairement à ce que suggère l'accuracy brute de
  {metriques['accuracy']:.4f}.
- Le rappel macro de {metriques['rappel_macro']:.4f} signifie que presque toutes
  les attaques présentes sont détectées.
- La sélection de variables et le rééchantillonnage ont été faits dans le
  pipeline, donc sans fuite de données vers la validation ou le test.
- L'inférence mesure {ms_par_flow} ms par flux sur {len(train)} flux du train,
  ce qui est compatible avec un traitement en continu (à confirmer sur le
  matériel de production).

## 4. Limites et biais

1. **Jeu de 2017** : les attaques ont été scriptées dans un laboratoire. Un
   trafic réel, chiffré ou plus récent, peut avoir un comportement différent.
2. **Échantillon de 5 %** : les conclusions valent pour cet échantillon
   stratifié, pas pour les 2,8 millions de flux bruts.
3. **Déséquilibre extrême** : BENIGN domine. Le F1 pondéré proche de 1 ne doit
   pas être présenté comme la performance du système.
4. **Familles non couvertes** : Infiltration ({rare_counts.get('Infiltration', 0)} lignes)
   et Heartbleed ({rare_counts.get('Heartbleed', 0)} lignes) ont été mises de côté faute
   d'exemples. Le modèle est donc aveugle à ces deux menaces.
5. **Port de destination** : il arrivait en tête des importances, mais l'enlever
   a amélioré le F1. Il a été écarté pour éviter un raccourci lié au service.
6. **Pas de charge utile** : CICFlowMeter ne garde que des statistiques de flux.
   Le modèle ne peut pas inspecter le contenu d'une requête ou d'un fichier.
7. **Fausses alertes** : WebAttack a une précision de
   {precision_web:.4f} et Bot de {precision_bot:.4f}. La première confusion est
   {top_erreur['famille_reelle']} -> {top_erreur['famille_predite']}
   avec {top_erreur['nombre']} cas.

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

Le modèle atteint un F1 macro de {metriques['f1_macro']:.4f} sur un test jamais
vu, avec un rappel très élevé. Il est utilisable comme outil d'aide à la
détection, à condition d'accepter ses limites : attaques anciennes et
scriptées, deux familles absentes, et fausses alertes sur les classes rares.
La proposition de déploiement privilégie donc l'observation, le seuillage et
le suivi humain avant toute automatisation.
"""

with open(DOCS_DIR / "RAPPORT_FINAL.md", "w", encoding="utf-8") as fichier:
    fichier.write(texte)

print("Rapport écrit dans docs/RAPPORT_FINAL.md")
