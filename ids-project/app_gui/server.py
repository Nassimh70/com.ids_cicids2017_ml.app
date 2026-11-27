"""Serveur local minimal pour tester le modèle IDS dans une interface web."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import joblib
import pandas as pd

DOSSIER_GUI = Path(__file__).resolve().parent
RACINE = DOSSIER_GUI.parent

# seul le résultat de l'étape 4 est chargé : aucun réentraînement ici
modele = joblib.load(RACINE / "models" / "final_model.joblib")
encodeur = joblib.load(RACINE / "models" / "label_encoder.joblib")
with open(RACINE / "data" / "processed" / "selected_features.txt", encoding="utf-8") as fichier:
    FEATURES = [ligne.strip() for ligne in fichier if ligne.strip()]

valeurs_imputation = modele.named_steps["imputation"].statistics_

GROUPES = ["Volumétrie du flux", "Taille des paquets", "Rythme et TCP"]

INFOS = {
    "Init_Win_bytes_backward": ("Rythme et TCP", "fenêtre TCP initiale dans le sens réponse"),
    "Subflow Fwd Bytes": ("Volumétrie du flux", "octets dans un sous-flux"),
    "Bwd Packet Length Mean": ("Taille des paquets", "taille moyenne des paquets reçus"),
    "Average Packet Size": ("Taille des paquets", "taille moyenne globale des paquets"),
    "Bwd Packet Length Min": ("Taille des paquets", "plus petit paquet reçu"),
    "Packet Length Variance": ("Taille des paquets", "variance des tailles de paquets"),
    "Packet Length Mean": ("Taille des paquets", "taille moyenne de tous les paquets"),
    "Packet Length Std": ("Taille des paquets", "variation des tailles de paquets"),
    "min_seg_size_forward": ("Taille des paquets", "plus petit segment TCP envoyé"),
    "Init_Win_bytes_forward": ("Rythme et TCP", "fenêtre TCP initiale dans le sens initial"),
    "Fwd Packet Length Mean": ("Taille des paquets", "taille moyenne des paquets envoyés"),
    "Total Length of Fwd Packets": ("Volumétrie du flux", "octets envoyés dans le sens initial"),
    "Fwd IAT Max": ("Rythme et TCP", "plus long intervalle entre deux paquets envoyés"),
    "Subflow Bwd Bytes": ("Volumétrie du flux", "octets dans le sous-flux inverse"),
    "Flow Bytes/s": ("Volumétrie du flux", "débit du flux en octets par seconde"),
}


def description_features():
    """Données nécessaires pour construire le formulaire côté navigateur."""
    return {
        "modele": "XGBoost réglé (15 variables)",
        "nb_variables": len(FEATURES),
        "classes": [str(classe) for classe in encodeur.classes_],
        "groupes": GROUPES,
        "features": [
            {
                "nom": nom,
                "groupe": INFOS[nom][0],
                "signification": INFOS[nom][1],
                "defaut": round(float(valeurs_imputation[i]), 4),
            }
            for i, nom in enumerate(FEATURES)
        ],
    }


class Handler(BaseHTTPRequestHandler):
    """Renvoie les fichiers de l'interface et répond aux prédictions."""

    def _fichier(self, chemin, type_mime):
        contenu = (DOSSIER_GUI / chemin).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", type_mime)
        self.send_header("Content-Length", str(len(contenu)))
        self.end_headers()
        self.wfile.write(contenu)

    def _json(self, objet, code=200):
        contenu = json.dumps(objet, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(contenu)))
        self.end_headers()
        self.wfile.write(contenu)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._fichier("index.html", "text/html; charset=utf-8")
        elif self.path in ("/style.css", "/static/style.css"):
            self._fichier("static/style.css", "text/css; charset=utf-8")
        elif self.path in ("/app.js", "/static/app.js"):
            self._fichier("static/app.js", "application/javascript; charset=utf-8")
        elif self.path == "/api/features":
            self._json(description_features())
        elif self.path == "/health":
            self._json({"ok": True})
        elif self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != "/api/predict":
            self.send_error(404)
            return

        taille = int(self.headers.get("Content-Length", 0))
        donnees = json.loads(self.rfile.read(taille).decode("utf-8"))
        try:
            valeurs = [float(donnees["values"][nom]) for nom in FEATURES]
        except (KeyError, TypeError, ValueError) as erreur:
            self._json({"erreur": "Valeurs invalides : " + str(erreur)}, 400)
            return

        # l'ordre des colonnes doit être exactement celui de l'entraînement
        X = pd.DataFrame([valeurs], columns=FEATURES)
        probabilites = modele.predict_proba(X)[0]
        index = int(probabilites.argmax())
        prediction = str(encodeur.inverse_transform([index])[0])

        self._json({
            "prediction": prediction,
            "confiance": round(float(probabilites[index]), 4),
            "est_attaque": prediction != "BENIGN",
            "probabilites": {
                str(classe): round(float(proba), 4)
                for classe, proba in zip(encodeur.classes_, probabilites)
            },
        })


if __name__ == "__main__":
    serveur = ThreadingHTTPServer(("127.0.0.1", 8000), Handler)
    print("Interface IDS : http://127.0.0.1:8000")
    print("Modèle chargé :", len(FEATURES), "variables et",
          len(encodeur.classes_), "familles")
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt de l'interface.")
        serveur.server_close()
