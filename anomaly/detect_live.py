"""Détection d'anomalies en direct sur le flux MQTT des capteurs.

  python -m anomaly.detect_live

Pour chaque mesure reçue : calcul des variables sur les 30 dernières secondes,
score Isolation Forest, puis alerte si 3 mesures anormales d'affilée.
Une seule alerte par type toutes les 30 s pour ne pas spammer le dashboard.
"""
import json
import time
from collections import deque
from pathlib import Path

import joblib
import pandas as pd

from anomaly.features import compute_features, explain
from common import config
from common.alerts import build_alert, send_alert
from common.mqtt_client import make_client

MODEL = Path(__file__).resolve().parent / "models" / "isoforest.joblib"
COOLDOWN_S = 30


def main():
    b = joblib.load(MODEL)
    model, window, needed = b["model"], b["window"], b["consecutive"]
    buffer = deque(maxlen=window * 2)
    state = {"streak": 0, "last_alert": {}}
    print(f"Modèle chargé (entraîné sur {b['n_samples']} fenêtres de {b['trained_on']})")

    def on_connect(client, userdata, flags, reason_code, properties):
        client.subscribe(config.TOPIC_SENSORS)
        print(f"Surveillance de {config.TOPIC_SENSORS}")

    def on_message(client, userdata, msg):
        try:
            data = json.loads(msg.payload)
            buffer.append({k: data.get(k) for k in ("temp", "hum", "gas")})
        except json.JSONDecodeError:
            return
        if len(buffer) < window:
            print(f"Remplissage de la fenêtre {len(buffer)}/{window}"); return

        feats = compute_features(pd.DataFrame(list(buffer)))
        if feats.empty:
            return
        row = feats.iloc[[-1]]
        score = float(model.decision_function(row)[0])
        abnormal = model.predict(row)[0] == -1
        state["streak"] = state["streak"] + 1 if abnormal else 0
        print(f"temp={data.get('temp')} hum={data.get('hum')} gas={data.get('gas')} "
              f"score={score:+.3f} {'ANORMAL' if abnormal else 'ok'}")

        if state["streak"] >= needed:
            alert_type, top = explain(row.iloc[0], b["mean"], b["std"])
            now = time.time()
            if now - state["last_alert"].get(alert_type, 0) >= COOLDOWN_S:
                state["last_alert"][alert_type] = now
                level = "critical" if score < b["critical_threshold"] else "warning"
                send_alert(build_alert("anomaly", alert_type, level, score, {
                    "temp": data.get("temp"), "hum": data.get("hum"),
                    "gas": data.get("gas"), "main_factor": top}))

    client = make_client("sentinel-ai-anomaly")
    client.on_connect, client.on_message = on_connect, on_message
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nArrêt")


if __name__ == "__main__":
    main()
