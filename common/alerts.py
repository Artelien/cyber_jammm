"""Envoi des résultats de l'IA vers l'API FastAPI.

L'IA publie son dernier résultat avec :

    POST /analysis/result

Format attendu par l'API :

{
    "risk": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
    "score": 0 à 100,
    "message": "..."
}
"""

import requests

from . import config


def build_alert(
    source,
    alert_type,
    level,
    value,
    details=None
):
    """Transforme le résultat interne de l'IA au format attendu par l'API."""

    details = details or {}

    # ---------------------------------------------------------
    # Conversion du niveau interne vers le format de l'API
    # ---------------------------------------------------------

    level_mapping = {
        "normal": "LOW",
        "warning": "HIGH",
        "critical": "CRITICAL",
    }

    risk = level_mapping.get(
        level.lower(),
        "MEDIUM"
    )


    # ---------------------------------------------------------
    # Création du message lisible
    # ---------------------------------------------------------

    if alert_type == "gas_leak":
        message = "Fuite de gaz suspectee"

    elif alert_type == "overheat":
        message = "Surchauffe detectee"

    elif alert_type == "temperature":
        message = "Temperature inhabituelle"

    elif alert_type == "humidity":
        message = "Humidite inhabituelle"

    elif alert_type == "intrusion":
        message = "Presence humaine detectee"

    else:
        message = "Anomalie detectee"


    # ---------------------------------------------------------
    # Conversion du score Isolation Forest
    # vers une échelle 0 - 100
    #
    # Plus le score IF est négatif, plus l'anomalie est forte.
    # ---------------------------------------------------------

    anomaly_score = float(value)

    score = int(
        max(
            0,
            min(
                100,
                abs(anomaly_score) * 500
            )
        )
    )


    return {
        "risk": risk,
        "score": score,
        "message": message
    }


def send_alert(alert):
    """Envoie le résultat IA vers FastAPI."""

    url = f"{config.API_BASE_URL}/analysis/result"

    headers = {
        "X-API-Key": config.API_KEY,
        "Content-Type": "application/json"
    }

    print("Résultat IA :", alert)

    try:

        response = requests.post(
            url,
            headers=headers,
            json=alert,
            timeout=5
        )

        response.raise_for_status()

        print("Résultat IA envoyé à l'API.")

        return True

    except requests.RequestException as e:

        print(
            f"Erreur lors de l'envoi du résultat IA : {e}"
        )

        return False
