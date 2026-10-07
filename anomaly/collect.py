"""Enregistre les vraies mesures de l'ESP32 dans un CSV (données d'entraînement).

  python -m anomaly.collect                  # -> data/train.csv
  python -m anomaly.collect --out data/xx.csv

À lancer dès que l'ESP32 publie, dans des conditions NORMALES (pas de gaz,
pas de main sur le capteur). Laisser tourner au moins 30-60 min. Ctrl+C pour arrêter.
Le fichier est complété (pas écrasé) si on relance.
"""
import argparse
import csv
import json
from pathlib import Path

from common import config
from common.mqtt_client import make_client

COLUMNS = ["timestamp", "temp", "hum", "gaz", "gaz_base", "mouvement"]


def main(out):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    new_file = not out.exists()
    f = open(out, "a", newline="")
    writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
    if new_file:
        writer.writeheader()
    count = {"n": 0}

    def on_connect(client, userdata, flags, reason_code, properties):
        client.subscribe(config.TOPIC_SENSORS)
        print(f"Abonnée à {config.TOPIC_SENSORS} - enregistrement dans {out}")

    def on_message(client, userdata, msg):
        try:
            data = json.loads(msg.payload)
        except json.JSONDecodeError:
            print("Message ignoré (pas du JSON) :", msg.payload[:80]); return
        writer.writerow(data); f.flush()
        count["n"] += 1
        if count["n"] % 30 == 0:
            print(f"{count['n']} mesures enregistrées ({count['n'] * 2 // 60} min)")

    client = make_client("sentinel-ai-collector")
    client.on_connect, client.on_message = on_connect, on_message
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print(f"\nArrêt : {count['n']} nouvelles mesures dans {out}")
    finally:
        f.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=str(Path(__file__).resolve().parent / "data" / "train.csv"))
    main(p.parse_args().out)
