"""Configuration commune aux scripts IA.

Les valeurs sensibles sont lues depuis le fichier ai/.env
et ne doivent pas être commitées sur GitHub.
"""

import os
from pathlib import Path

from dotenv import load_dotenv


# ---------------------------------------------------------
# Chargement du fichier .env situé dans le dossier ai/
# ---------------------------------------------------------

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

load_dotenv(ENV_FILE)


# ---------------------------------------------------------
# API FastAPI
# ---------------------------------------------------------

# Depuis Docker Compose, "api" correspond au nom du service API.
API_BASE_URL = os.getenv(
    "API_BASE_URL",
    "http://api:8000"
).rstrip("/")


# Clé utilisée dans l'en-tête X-API-Key.
API_KEY = os.getenv(
    "API_KEY",
    ""
)


# ---------------------------------------------------------
# Informations du dispositif
# ---------------------------------------------------------

DEVICE_ID = os.getenv(
    "DEVICE_ID",
    "sentinel-x"
)
