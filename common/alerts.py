"""Envoi des alertes IA vers l'API (POST /api/v1/alerts).

Format JSON proposé (à valider avec DEV) :
{
  "device_id": "SX-001",
  "ts": 1728201302,                 # timestamp Unix en secondes
  "source": "vision" | "anomaly",
  "type": "intrusion" | "gas_leak" | "overheat" | "humidity" | "temperature",
  "level": "warning" | "critical",
  "value": 0.87,                    # confiance (vision) ou score d'anomalie
  "details": {...}                  # infos utiles pour le dashboard
}
Tant que API_URL est vide, l'alerte est seulement affichée dans le terminal.
"""
import json
import time

import requests

from . import config


def build_alert(source, alert_type, level, value, details=None):
    return {
        "device_id": config.DEVICE_ID,
        "ts": int(time.time()),
        "source": source,
        "type": alert_type,
        "level": level,
        "value": round(float(value), 3),
        "details": details or {},
    }


def send_alert(alert):
    print("ALERTE", json.dumps(alert, ensure_ascii=False))
    if not config.API_URL:
        return False
    try:
        r = requests.post(config.API_URL, json=alert, timeout=2,
                          verify=config.API_CA or True)
        r.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"  -> API injoignable : {e}")
        return False
