# Interface graphique de test du modèle

Dossier indépendant : il ne modifie aucun script des étapes 1 à 6.

## Lancement

Depuis le dossier du projet :

```bash
cd app_gui
python server.py
```

Puis ouvrir <http://127.0.0.1:8000> dans un navigateur.

## Ce que l'interface charge

- `models/final_model.joblib` (modèle XGBoost de l'étape 4)
- `models/label_encoder.joblib` (noms des familles)
- `data/processed/selected_features.txt` (ordre exact des 15 variables)

Aucun réentraînement n'est fait. Les valeurs par défaut affichées dans le
formulaire viennent des médianes apprises par l'imputer du pipeline.

## Fonctionnement

1. `GET /api/features` renvoie les 15 variables, leur groupe et leur signification.
2. Le navigateur construit le formulaire avec `static/app.js`.
3. `POST /api/predict` envoie les 15 valeurs ; le serveur construit un
   DataFrame dans le bon ordre, appelle `predict_proba` et renvoie la famille,
   la confiance et toutes les probabilités.

## Fichiers

```text
app_gui/
├── server.py          # serveur local, standard Python uniquement
├── index.html         # structure de la page
├── static/
│   ├── style.css      # thème, layout, formulaires, résultats, responsive
│   └── app.js         # formulaire dynamique et appels API
└── README.md
```

Le style est organisé en neuf sections commentées dans `static/style.css`.
