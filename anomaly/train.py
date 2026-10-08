"""Entraînement du modèle Isolation Forest de Sentinel-X.

Utilisation :

    python -m anomaly.train

ou avec un autre dataset :

    python -m anomaly.train --train anomaly/data/mon_dataset.csv


Le dataset doit contenir au minimum :

    temp
    hum
    gaz
    gaz_base

Les mêmes features que celles utilisées en temps réel sont calculées
avec anomaly.features.compute_features().

Le modèle entraîné est sauvegardé dans :

    anomaly/models/isoforest.joblib
"""

import argparse
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import IsolationForest

from anomaly.features import (
    FEATURES,
    WINDOW,
    RAW_COLUMNS,
    compute_features,
)


HERE = Path(__file__).resolve().parent

DEFAULT_DATASET = HERE / "data" / "train.csv"

MODEL_PATH = HERE / "models" / "isoforest.joblib"

# Nombre d'anomalies consécutives nécessaires
# avant de déclencher une alerte en temps réel.
CONSECUTIVE = 3


def train(train_csv):
    """Entraîne Isolation Forest à partir d'un dataset de fonctionnement normal."""

    train_csv = Path(train_csv)

    # ---------------------------------------------------------
    # 1. Vérification du fichier
    # ---------------------------------------------------------

    if not train_csv.exists():
        raise FileNotFoundError(
            f"Dataset introuvable : {train_csv}"
        )

    print(f"Lecture du dataset : {train_csv}")

    df = pd.read_csv(train_csv)

    print(f"Nombre de mesures brutes : {len(df)}")


    # ---------------------------------------------------------
    # 2. Vérification des colonnes nécessaires
    # ---------------------------------------------------------

    missing = [
        col
        for col in RAW_COLUMNS
        if col not in df.columns
    ]

    if missing:
        raise ValueError(
            "Le dataset ne contient pas toutes les colonnes nécessaires.\n"
            f"Colonnes manquantes : {missing}\n"
            f"Colonnes attendues : {RAW_COLUMNS}"
        )


    # ---------------------------------------------------------
    # 3. Calcul des features
    # ---------------------------------------------------------

    X = compute_features(df)

    if X.empty:
        raise ValueError(
            "Impossible de calculer les features. "
            "Le dataset ne contient probablement pas assez de mesures."
        )

    print(f"Nombre de fenêtres utilisables : {len(X)}")

    print("\nFeatures utilisées :")

    for feature in FEATURES:
        print(f" - {feature}")


    # ---------------------------------------------------------
    # 4. Création du modèle Isolation Forest
    # ---------------------------------------------------------

    model = IsolationForest(
        n_estimators=300,
        contamination=0.005,
        random_state=42
    )


    # ---------------------------------------------------------
    # 5. Entraînement
    # ---------------------------------------------------------

    print("\nEntraînement du modèle...")

    model.fit(X)

    print("Entraînement terminé.")


    # ---------------------------------------------------------
    # 6. Scores sur les données d'entraînement
    # ---------------------------------------------------------

    scores = model.decision_function(X)

    predictions = model.predict(X)

    nb_anomalies = int((predictions == -1).sum())

    print(
        f"Anomalies détectées dans les données d'entraînement : "
        f"{nb_anomalies}/{len(X)}"
    )


    # ---------------------------------------------------------
    # 7. Création du bundle
    # ---------------------------------------------------------

    bundle = {
        "model": model,

        "features": FEATURES,

        "window": WINDOW,

        "consecutive": CONSECUTIVE,

        # Statistiques utilisées par explain()
        "mean": X.mean(),
        "std": X.std(),

        # Une valeur inférieure à tout ce qui a été observé
        # pendant l'entraînement est considérée très anormale.
        "critical_threshold": float(scores.min()),

        "trained_on": train_csv.name,

        "n_samples": int(len(X)),
    }


    # ---------------------------------------------------------
    # 8. Sauvegarde
    # ---------------------------------------------------------

    MODEL_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    joblib.dump(
        bundle,
        MODEL_PATH
    )

    print(
        f"\nModèle sauvegardé : {MODEL_PATH}"
    )

    return bundle


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--train",
        default=str(DEFAULT_DATASET),
        help="Chemin vers le dataset d'entraînement"
    )

    args = parser.parse_args()

    train(args.train)
