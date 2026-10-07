"""Entraînement de l'Isolation Forest sur des données NORMALES, puis évaluation.

  python -m anomaly.train                                   # simulé : sim_train.csv + sim_test.csv
  python -m anomaly.train --train anomaly/data/train.csv --skip 90  # vraies données (90 lignes = 3 min de chauffe du MQ-2)
  python -m anomaly.train --train anomaly/data/train.csv --model lof  # secours si moins de 30 min de données
  python -m anomaly.train --train anomaly/data/calib_train.csv --test anomaly/data/calib_test.csv --real anomaly/data/train.csv

Principe : l'Isolation Forest apprend à quoi ressemble le fonctionnement normal.
Un point qu'il "isole" en peu de coupures est différent de tout ce qu'il a vu
-> anomalie. Aucun seuil écrit à la main.

Sorties :
  models/isoforest.joblib       modèle + statistiques (utilisé par detect_live.py)
  reports/anomaly_metrics.json  métriques pour le dossier technique
  reports/anomaly_eval.png      graphique pour le dossier / la soutenance
"""
import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_score, recall_score
from sklearn.neighbors import LocalOutlierFactor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from anomaly.features import FEATURES, WINDOW, compute_features

HERE = Path(__file__).resolve().parent
CONSECUTIVE = 3  # il faut 3 mesures anormales d'affilée (6 s) pour lever une alerte


def alerts_from_flags(flags: np.ndarray) -> np.ndarray:
    s = pd.Series(flags.astype(int))
    return (s.rolling(CONSECUTIVE).sum() >= CONSECUTIVE).to_numpy()


def segments(mask):
    """Liste des (début, fin) des zones où mask est vrai."""
    out, start = [], None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        if not v and start is not None:
            out.append((start, i - 1)); start = None
    if start is not None:
        out.append((start, len(mask) - 1))
    return out


def train(train_csv, skip, model_name="if"):
    df = pd.read_csv(train_csv).iloc[skip:].reset_index(drop=True)
    X = compute_features(df)
    if model_name == "lof":
        # Secours si peu de données (< 30 min) : Local Outlier Factor, basé sur les
        # distances, il reconnaît mieux une valeur jamais vue quand l'historique est court.
        model = make_pipeline(StandardScaler(),
                              LocalOutlierFactor(n_neighbors=20, novelty=True, contamination=0.005))
    else:
        # Chaque arbre voit toutes les données : arbres plus profonds -> meilleure
        # séparation normal / anormal (testé : 256 -> 2048 -> tout = de mieux en mieux)
        model = IsolationForest(n_estimators=300, max_samples=len(X),
                                contamination=0.005, random_state=42)
    model.fit(X)
    scores = model.decision_function(X)
    bundle = {
        "model": model, "model_name": model_name, "features": FEATURES, "window": WINDOW,
        "consecutive": CONSECUTIVE,
        "mean": X.mean(), "std": X.std(),
        "critical_threshold": float(scores.min()),  # plus anormal que tout le normal vu
        "trained_on": str(train_csv), "n_samples": int(len(X)),
    }
    (HERE / "models").mkdir(exist_ok=True)
    joblib.dump(bundle, HERE / "models" / "isoforest.joblib")
    print(f"Modèle {model_name.upper()} entraîné sur {len(X)} fenêtres normales ({train_csv})")
    return bundle


def evaluate(bundle, test_csv):
    df = pd.read_csv(test_csv)
    X = compute_features(df)
    model = bundle["model"]
    scores = model.decision_function(X)
    flags = model.predict(X) == -1
    alerts = alerts_from_flags(flags)

    y = df.loc[X.index, "anomaly"].to_numpy().astype(bool)
    # Les variations sur 30 s restent visibles 30 s après la fin d'une anomalie :
    # une alerte dans cette zone n'est pas une fausse alerte.
    tolerance = pd.Series(y.astype(int)).rolling(WINDOW, min_periods=1).max().to_numpy().astype(bool)

    events = segments(y)
    types = df.loc[X.index, "anomaly_type"].fillna("").to_numpy() if "anomaly_type" in df else None
    detected, delays, per_type = 0, [], {}
    for s, e in events:
        hit = np.where(alerts[s:e + 1])[0]  # strict : l'alerte doit tomber PENDANT l'anomalie
        name = types[s] if types is not None else "anomalie"
        per_type.setdefault(name, [0, 0])[1] += 1
        if len(hit):
            detected += 1
            per_type[name][0] += 1
            delays.append(int(hit[0]) * 2)
    onsets = [s for s, _ in segments(alerts)]
    false_alarms = sum(1 for s in onsets if not tolerance[s])
    duration_h = len(X) * 2 / 3600

    metrics = {
        "evenements_anomalie": len(events),
        "evenements_detectes": detected,
        "detail_par_type": {k: f"{d}/{n}" for k, (d, n) in per_type.items()},
        "delai_moyen_detection_s": round(float(np.mean(delays)), 1) if delays else None,
        "fausses_alertes": false_alarms,
        "fausses_alertes_par_heure": round(false_alarms / duration_h, 2),
        "precision_points": round(float(precision_score(tolerance, alerts, zero_division=0)), 3),
        "rappel_points": round(float(recall_score(y, alerts, zero_division=0)), 3),
        "jeu_test": str(test_csv),
    }
    (HERE / "reports").mkdir(exist_ok=True)
    (HERE / "reports" / "anomaly_metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False))
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    plot(df.loc[X.index].reset_index(drop=True), scores, alerts, y)


def plot(df, scores, alerts, y):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t = np.arange(len(df)) * 2 / 60  # minutes
    fig, axes = plt.subplots(4, 1, figsize=(12, 9), sharex=True)
    series = [("temp", "Température (°C)"), ("hum", "Humidité (%)"), ("gas", "Gaz MQ-2 (ADC)")]
    for ax, (col, label) in zip(axes, series):
        ax.plot(t, df[col], lw=1, color="#1d4ed8")
        ax.set_ylabel(label)
    axes[3].plot(t, scores, lw=1, color="#334155")
    axes[3].axhline(0, color="#dc2626", ls="--", lw=1)
    axes[3].set_ylabel("Score IF\n(< 0 = anormal)")
    axes[3].set_xlabel("Temps (min)")
    for ax in axes:
        for s, e in segments(y):
            ax.axvspan(t[s], t[e], color="#fde68a", alpha=0.6, lw=0)
        for s, e in segments(alerts):
            ax.axvspan(t[s], t[e], color="#dc2626", alpha=0.25, lw=0)
    axes[0].set_title("Isolation Forest - jaune : anomalies réelles, rouge : alertes levées")
    fig.tight_layout()
    fig.savefig(HERE / "reports" / "anomaly_eval.png", dpi=130)
    print(f"Graphique : {HERE / 'reports' / 'anomaly_eval.png'}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--train", default=str(HERE / "data" / "sim_train.csv"))
    p.add_argument("--test", default=None,
                   help="jeu de test étiqueté (par défaut : sim_test.csv si on entraîne sur le simulé)")
    p.add_argument("--skip", type=int, default=0, help="lignes ignorées au début (chauffe du MQ-2)")
    p.add_argument("--real", default=None,
                   help="vraies mesures normales : vérifie que le modèle ne sonne pas dessus")
    p.add_argument("--model", choices=["if", "lof"], default="if",
                   help="if = Isolation Forest (défaut) ; lof = secours si moins de 30 min de données")
    a = p.parse_args()
    b = train(a.train, a.skip, a.model)
    test = a.test or (str(HERE / "data" / "sim_test.csv") if "sim_train" in a.train else None)
    if test and Path(test).exists():
        evaluate(b, test)
        if a.real:
            Xr = compute_features(pd.read_csv(a.real))
            n_alerts = len(segments(alerts_from_flags(b["model"].predict(Xr) == -1)))
            print(f"Validation sur les VRAIES mesures ({a.real}) : {n_alerts} fausse(s) alerte(s) "
                  f"sur {len(Xr) * 2 / 60:.0f} min (idéal : 0)")
    else:
        # Pas de test étiqueté pour les vraies données : on vérifie au moins que le
        # modèle ne sonne pas en permanence sur les données normales.
        X = compute_features(pd.read_csv(a.train).iloc[a.skip:].reset_index(drop=True))
        alerts = alerts_from_flags(b["model"].predict(X) == -1)
        n_alerts = len(segments(alerts))
        print(f"Vérification sur les données normales : {n_alerts} alerte(s) "
              f"sur {len(X) * 2 / 60:.0f} min (idéal : 0)")
