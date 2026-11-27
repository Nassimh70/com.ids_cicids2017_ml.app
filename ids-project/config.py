"""Constantes partagées par les scripts du projet."""

import sys
from pathlib import Path

# pour que les accents s'affichent correctement sur une console Windows
sys.stdout.reconfigure(encoding="utf-8")

RANDOM_STATE = 42

BASE = Path(__file__).resolve().parent
RAW_DIR = BASE / "data" / "raw"
PROCESSED_DIR = BASE / "data" / "processed"
FIGURES_DIR = BASE / "reports" / "figures"
TABLES_DIR = BASE / "reports" / "tables"
MODELS_DIR = BASE / "models"
DOCS_DIR = BASE / "docs"

for dossier in (RAW_DIR, PROCESSED_DIR, FIGURES_DIR, TABLES_DIR, MODELS_DIR, DOCS_DIR):
    dossier.mkdir(parents=True, exist_ok=True)

# 5 % par famille, mais on garde toutes les lignes des familles très rares
SAMPLE_FRACTION = 0.05
RARE_MAX = 100
SAMPLE_FILE = "sample_stratified_5pct.csv"

FAMILIES = {
    "BENIGN": "BENIGN",
    "DoS GoldenEye": "DoS",
    "DoS Hulk": "DoS",
    "DoS Slowloris": "DoS",
    "DoS Slowhttptest": "DoS",
    "DDoS": "DDoS",
    "PortScan": "PortScan",
    "FTP-Patator": "BruteForce",
    "SSH-Patator": "BruteForce",
    "Web Attack Brute Force": "WebAttack",
    "Web Attack XSS": "WebAttack",
    "Web Attack Sql Injection": "WebAttack",
    "Bot": "Bot",
    "Infiltration": "Infiltration",
    "Heartbleed": "Heartbleed",
}
FAMILY_ORDER = ["BENIGN", "DoS", "DDoS", "PortScan", "BruteForce",
                "WebAttack", "Bot", "Infiltration", "Heartbleed"]

KEY_FEATURES = ["Flow Duration", "Total Fwd Packets", "Total Length of Fwd Packets",
                "Flow Bytes/s", "Flow Packets/s", "Packet Length Mean"]

# retirées à l'étape 2 : identifiants ou fuite temporelle
RISKY_COLUMNS = ["Flow ID", "Source IP", "Destination IP",
                 "Source Port", "Timestamp"]

# trop peu d'exemples pour évaluer une classe correctement (36 et 11)
RARE_FAMILIES = ["Infiltration", "Heartbleed"]
