"""Transformation des mesures brutes en variables pour le modèle.

Le modèle ne regarde pas seulement la valeur instantanée : il regarde aussi
comment elle évolue sur une fenêtre glissante de 30 s (15 mesures à 2 s).
Une montée brutale de température ou de gaz est donc anormale même si la
valeur absolue reste "raisonnable" -> c'est ce qui remplace les if temp > 40.

Les mêmes fonctions servent à l'entraînement ET en direct, pour que le
modèle voie toujours exactement les mêmes variables.
"""
import numpy as np
import pandas as pd

WINDOW = 15  # 15 mesures x 2 s = 30 s
RAW = ["temp", "hum", "gas"]
# Pas d'écart-type de température : le vrai DHT22 garde souvent la même valeur
# (écart-type = 0), ce qui faisait sonner le modèle pour rien.
FEATURES = ["temp", "hum", "gas",
            "temp_delta", "hum_delta", "gas_delta",
            "gas_std"]


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    raw = df[RAW].astype(float).interpolate(limit_direction="both")  # le DHT22 renvoie parfois NaN
    f = raw.copy()
    for c in RAW:
        f[f"{c}_delta"] = raw[c] - raw[c].shift(WINDOW - 1)  # variation sur 30 s
    f["gas_std"] = raw["gas"].rolling(WINDOW).std()
    return f[FEATURES].dropna()


def explain(row: pd.Series, mean: pd.Series, std: pd.Series):
    """Retourne (type d'alerte, variable la plus anormale) pour le dashboard."""
    z = ((row - mean) / std.replace(0, np.nan)).abs().fillna(0)
    top = z.idxmax()
    if top.startswith("gas"):
        return "gas_leak", top
    if top.startswith("temp"):
        rising = row["temp_delta"] > 0 or row["temp"] > mean["temp"]
        return ("overheat" if rising else "temperature"), top
    return "humidity", top
