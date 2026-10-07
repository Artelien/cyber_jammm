"""Simulateur de l'ESP32 : sert tant que les vrais capteurs n'envoient rien.

Deux usages :
  python -m anomaly.simulate csv
      -> data/sim_train.csv : 3 h de mesures normales (pour entraîner)
      -> data/sim_test.csv  : 1 h avec anomalies injectées et étiquetées (pour évaluer)

  python -m anomaly.simulate calib
      -> data/calib_train.csv + data/calib_test.csv : comme "csv", mais calé sur les
         VRAIES mesures (data/train.csv) : mêmes niveaux, même bruit, même précision.
         Données synthétiques calibrées : à présenter comme telles au jury.

  python -m anomaly.simulate mqtt [--anomalies] [--speed 1]
      -> publie en direct sur sentinel/<GROUP>/sensors toutes les 2 s, comme l'ESP32.
         Utile aussi à DEV/INFRA pour tester l'API et le dashboard sans matériel.

Valeurs réalistes : DHT22 au 0,1 près, MQ-2 lu sur l'ADC 12 bits de l'ESP32 (0-4095).
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

PERIOD_S = 2
DATA = Path(__file__).resolve().parent / "data"


DEFAULT = {"temp": 22.5, "temp_amp": 1.5, "temp_noise": 0.08,
           "hum": 48.0, "hum_noise": 0.3, "gas": 600.0, "gas_amp": 40.0, "gas_noise": 12.0,
           "temp_hold": 0.0, "hum_hold": 0.0}


def _hold(values, p_hold, rng):
    """Comme le vrai DHT22 : la valeur affichée reste souvent identique d'une mesure à l'autre."""
    if p_hold <= 0:
        return values
    out = values.copy()
    for i in range(1, len(out)):
        if rng.random() < p_hold:
            out[i] = out[i - 1]
    return out


def normal_series(n, seed, p=None):
    p = {**DEFAULT, **(p or {})}
    rng = np.random.default_rng(seed)
    t = np.arange(n) * PERIOD_S
    phase = rng.uniform(0, 2 * np.pi)
    temp = (p["temp"] + p["temp_amp"] * np.sin(2 * np.pi * t / 10800 + phase)
            + np.cumsum(rng.normal(0, 0.01, n)) + rng.normal(0, p["temp_noise"], n))
    hum = (p["hum"] - 1.2 * (temp - p["temp"]) + np.cumsum(rng.normal(0, 0.02, n))
           + rng.normal(0, p["hum_noise"], n))
    gas = p["gas"] + p["gas_amp"] * np.sin(2 * np.pi * t / 5400 + phase) + rng.normal(0, p["gas_noise"], n)
    pir = (rng.random(n) < 0.02).astype(int)
    temp = _hold(temp.round(1), p["temp_hold"], rng)
    hum = _hold(hum.round(1), p["hum_hold"], rng)
    return pd.DataFrame({
        "ts": (1_728_000_000 + t).astype(int),
        "temp": temp, "hum": hum,
        "gas": gas.round().astype(int), "pir": pir,
    })


def calibrate(real_csv):
    """Mesure niveaux et bruit sur les vraies données du capteur."""
    r = pd.read_csv(real_csv)
    diffs = lambda c: r[c].diff().dropna()
    changed = lambda c: diffs(c).ne(0)
    # bruit = moitié du saut typique quand la valeur change
    noise = lambda c: max(float(diffs(c)[changed(c)].abs().median()) / 2, 0.05)
    p = {"temp": float(r.temp.median()), "temp_amp": 1.5, "temp_noise": noise("temp"),
         "hum": float(r.hum.median()), "hum_noise": noise("hum"),
         "gas": float(r.gas.median()), "gas_amp": 20.0,
         "gas_noise": float(r.gas.diff().std() / np.sqrt(2)),
         "temp_hold": float(1 - changed("temp").mean()), "hum_hold": float(1 - changed("hum").mean())}
    print("Calibrage sur", real_csv, {k: round(v, 2) for k, v in p.items()})
    return p


def _bump(n, start, rise, hold, fall, height):
    """Profil d'anomalie : montée, plateau, retour à la normale."""
    off = np.zeros(n)
    seg = np.concatenate([np.linspace(0, height, rise), np.full(hold, height),
                          np.linspace(height, 0, fall)])
    end = min(n, start + len(seg))
    off[start:end] = seg[: end - start]
    return off


ANOMALIES = {
    # nom : (colonne, montée, plateau, descente, amplitude)
    "gas_leak": ("gas", 20, 30, 20, 1800),   # fuite de gaz
    "overheat": ("temp", 25, 20, 30, 9.0),   # surchauffe rapide (+9 °C en 50 s)
    "humidity": ("hum", 5, 15, 10, 30.0),    # projection d'eau / condensation
    "glitch":   ("temp", 1, 2, 1, 15.0),     # valeur aberrante du capteur
}


def inject(df, plan):
    """plan = [(nom_anomalie, index_de_début), ...] -> ajoute une colonne label 'anomaly'."""
    df = df.copy()
    df["anomaly"] = 0
    df["anomaly_type"] = ""
    for name, start in plan:
        col, rise, hold, fall, height = ANOMALIES[name]
        off = _bump(len(df), start, rise, hold, fall, height)
        df[col] = df[col] + (off.round() if col == "gas" else off.round(1))
        mask = np.abs(off) > 0.05 * height
        df.loc[mask, "anomaly"] = 1
        df.loc[mask, "anomaly_type"] = name
    return df


def make_csv(prefix="sim", params=None):
    DATA.mkdir(exist_ok=True)
    train = normal_series(5400, seed=1, p=params)  # 3 h
    train.to_csv(DATA / f"{prefix}_train.csv", index=False)

    test = normal_series(1800, seed=2, p=params)   # 1 h
    plan = [("gas_leak", 150), ("overheat", 400), ("humidity", 650), ("glitch", 850),
            ("gas_leak", 1050), ("overheat", 1300), ("humidity", 1500), ("glitch", 1700)]
    test = inject(test, plan)
    test.to_csv(DATA / f"{prefix}_test.csv", index=False)
    print(f"OK : {DATA / (prefix + '_train.csv')} ({len(train)} lignes normales)")
    print(f"OK : {DATA / (prefix + '_test.csv')} ({len(test)} lignes, {len(plan)} anomalies injectées)")


def stream_mqtt(with_anomalies, speed):
    from common import config
    from common.mqtt_client import make_client

    n = 3600  # 2 h de données
    df = normal_series(n, seed=int(time.time()))
    if with_anomalies:  # une anomalie toutes les 3 min, après 2 min de calme
        names = list(ANOMALIES)
        df = inject(df, [(names[i % len(names)], 60 + i * 90) for i in range((n - 60) // 90)])

    client = make_client("sentinel-simulator")
    client.loop_start()
    print(f"Publication sur {config.TOPIC_SENSORS} ({config.MQTT_HOST}:{config.MQTT_PORT}) - Ctrl+C pour arrêter")
    try:
        for _, r in df.iterrows():
            msg = {"device_id": config.DEVICE_ID, "ts": int(time.time()),
                   "temp": float(r.temp), "hum": float(r.hum),
                   "gas": int(r.gas), "pir": int(r.pir)}
            client.publish(config.TOPIC_SENSORS, json.dumps(msg))
            tag = "  <- anomalie injectée" if r.get("anomaly", 0) else ""
            print(json.dumps(msg) + tag)
            time.sleep(PERIOD_S / speed)
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["csv", "calib", "mqtt"])
    p.add_argument("--real", default=str(DATA / "train.csv"), help="vraies mesures pour le mode calib")
    p.add_argument("--anomalies", action="store_true", help="injecte des anomalies (mode mqtt)")
    p.add_argument("--speed", type=float, default=1.0, help="accélère la simulation (mode mqtt)")
    a = p.parse_args()
    if a.mode == "csv":
        make_csv()
    elif a.mode == "calib":
        make_csv("calib", calibrate(a.real))
    else:
        stream_mqtt(a.anomalies, a.speed)
