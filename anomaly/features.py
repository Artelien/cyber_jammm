"""Transformation des mesures brutes en variables pour le modèle.

Le modèle ne regarde pas seulement la valeur instantanée : il regarde aussi
comment elle évolue sur une fenêtre glissante de 30 s (15 mesures à 2 s).

Les mêmes fonctions servent à l'entraînement ET en direct, pour que le
modèle voie toujours exactement les mêmes variables.
"""

import numpy as np
import pandas as pd


# 15 mesures x 2 secondes = environ 30 secondes
WINDOW = 15

# Variables réellement reçues et utilisées depuis l'ESP32
RAW_COLUMNS = [
    "temp",
    "hum",
    "gaz",
    "gaz_base"
]

# Variables effectivement données à Isolation Forest
FEATURES = [
    "temp",
    "hum",
    "gaz",
    "gaz_ecart",
    "temp_delta",
    "hum_delta",
    "gaz_delta",
    "gaz_std"
]


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Transforme les mesures brutes en features pour Isolation Forest."""

    # Vérifie que toutes les colonnes nécessaires sont présentes
    missing = [col for col in RAW_COLUMNS if col not in df.columns]

    if missing:
        raise ValueError(
            f"Colonnes manquantes pour calculer les features : {missing}"
        )

    # Conversion en numérique
    raw = (
        df[RAW_COLUMNS]
        .astype(float)
        .interpolate(limit_direction="both")
    )

    # On commence avec les valeurs instantanées
    features = raw[["temp", "hum", "gaz"]].copy()

    # ---------------------------------------------------------
    # Écart entre la mesure gaz actuelle et sa valeur de référence
    # ---------------------------------------------------------
    features["gaz_ecart"] = (
        raw["gaz"] - raw["gaz_base"]
    )

    # ---------------------------------------------------------
    # Évolution entre maintenant et environ 30 secondes auparavant
    # ---------------------------------------------------------
    features["temp_delta"] = (
        raw["temp"] - raw["temp"].shift(WINDOW - 1)
    )

    features["hum_delta"] = (
        raw["hum"] - raw["hum"].shift(WINDOW - 1)
    )

    features["gaz_delta"] = (
        raw["gaz"] - raw["gaz"].shift(WINDOW - 1)
    )

    # ---------------------------------------------------------
    # Variabilité du gaz sur les 15 dernières mesures
    # ---------------------------------------------------------
    features["gaz_std"] = (
        raw["gaz"]
        .rolling(WINDOW)
        .std()
    )

    # Les premières lignes ne disposent pas encore
    # d'un historique complet de 30 secondes.
    return features[FEATURES].dropna()


def explain(
    row: pd.Series,
    mean: pd.Series,
    std: pd.Series
):
    """Retourne le type d'alerte et la feature la plus inhabituelle."""

    # Distance de chaque feature à son comportement moyen d'entraînement
    z = (
        ((row - mean) / std.replace(0, np.nan))
        .abs()
        .fillna(0)
    )

    # Feature qui s'écarte le plus de son comportement habituel
    top = z.idxmax()

    # Anomalie principalement liée au gaz
    if top.startswith("gaz"):
        return "gas_leak", top

    # Anomalie principalement liée à la température
    if top.startswith("temp"):

        rising = (
            row["temp_delta"] > 0
            or row["temp"] > mean["temp"]
        )

        return (
            "overheat" if rising else "temperature",
            top
        )

    # Sinon, anomalie liée principalement à l'humidité
    return "humidity", top
