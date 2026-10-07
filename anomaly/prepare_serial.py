"""Nettoie un enregistrement du moniteur série de l'ESP32 -> data/train.csv

  python -m anomaly.prepare_serial chemin\\vers\\fichier.txt

Accepte les formats :
  temp;hum;gas;pir          ou  temp,hum,gas,pir
  ts;temp;hum;gas;pir       ou  ts,temp,hum,gas,pir
Supprime : les lignes de texte ("[DHT] Lecture invalide"...), les valeurs vides (nan),
les valeurs impossibles et les blocs de lignes identiques répétées
(ESP32 qui imprime en boucle ou capteur figé).
"""
import argparse
import re
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent / "data" / "train.csv"
MAX_REPEAT = 5  # au-delà de 5 lignes identiques d'affilée, ce sont des copies


def parse(path):
    rows = []
    for line in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = [p for p in re.split(r"[;,\s]+", line.strip()) if p]
        try:
            values = [float(p) for p in parts]
        except ValueError:
            continue  # ligne de texte
        if len(values) == 4:
            rows.append([None] + values)
        elif len(values) == 5:
            rows.append(values)
    df = pd.DataFrame(rows, columns=["ts", "temp", "hum", "gas", "pir"])
    return df


def clean(df):
    n0 = len(df)
    df = df.dropna(subset=["temp", "hum", "gas"])
    df = df[df.temp.between(-20, 80) & df.hum.between(0, 100) & df.gas.between(0, 4095)]
    n1 = len(df)
    key = df[["temp", "hum", "gas", "pir"]].astype(str).agg(";".join, axis=1)
    run_id = (key != key.shift()).cumsum()
    pos_in_run = df.groupby(run_id).cumcount()
    df = df[pos_in_run < MAX_REPEAT].reset_index(drop=True)
    if df.ts.isna().all():  # pas d'horodatage : une mesure toutes les 2 s
        df["ts"] = range(0, 2 * len(df), 2)
    df[["ts", "gas", "pir"]] = df[["ts", "gas", "pir"]].astype(int)
    print(f"Lignes lues                 : {n0}")
    print(f"Supprimées (nan / absurdes) : {n0 - n1}")
    print(f"Supprimées (copies)         : {n1 - len(df)}")
    print(f"Lignes gardées              : {len(df)}  (~{len(df) * 2 / 60:.0f} min de mesures)")
    if df.pir.nunique() == 1:
        print(f"Attention : le PIR vaut toujours {df.pir.iloc[0]} (capteur bloqué ?)")
    if len(df) < 900:
        print("Attention : moins de 30 min de mesures -> modèle peu fiable, à réenregistrer plus longtemps")
    return df


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("fichier")
    p.add_argument("--out", default=str(OUT))
    a = p.parse_args()
    df = clean(parse(a.fichier))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    df[["ts", "temp", "hum", "gas", "pir"]].to_csv(a.out, index=False)
    print(f"Fichier propre : {a.out}")
