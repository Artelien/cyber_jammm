"""Détection d'anomalies en temps réel à partir de l'API CyberJam.

Le programme :
1. récupère régulièrement la dernière mesure de l'ESP32 via FastAPI ;
2. conserve les dernières mesures dans une fenêtre ;
3. calcule les features utilisées à l'entraînement ;
4. applique Isolation Forest ;
5. envoie une alerte via l'API après plusieurs anomalies consécutives.
"""

import time
from collections import deque
from pathlib import Path

import joblib
import pandas as pd
import requests

from anomaly.features import compute_features, explain
from common import config
from common.alerts import build_alert, send_alert


MODEL = Path(__file__).resolve().parent / "models" / "isoforest.joblib"

# Temps entre deux lectures de l'API
POLL_INTERVAL_S = 2

# Évite d'envoyer la même alerte en boucle
COOLDOWN_S = 30


def main():

    # ---------------------------------------------------------
    # 1. Chargement du modèle entraîné
    # ---------------------------------------------------------

    bundle = joblib.load(MODEL)

    model = bundle["model"]
    window = bundle["window"]
    needed = bundle["consecutive"]

    # Stocke les dernières mesures reçues
    buffer = deque(maxlen=window * 2)

    # État de la détection
    state = {
        "streak": 0,
        "last_alert": {}
    }

    # Permet d'éviter d'analyser plusieurs fois
    # la même mesure reçue depuis l'API
    last_measure_id = None

    print(
        f"Modèle chargé "
        f"(entraîné sur {bundle['n_samples']} fenêtres "
        f"de {bundle['trained_on']})"
    )

    print("Surveillance via l'API FastAPI...")


    # ---------------------------------------------------------
    # 2. Boucle de surveillance
    # ---------------------------------------------------------

    while True:

        try:

            # ---------------------------------------------
            # Récupération de la dernière mesure
            # ---------------------------------------------

            response = requests.get(
                f"{config.API_BASE_URL}/telemetry/latest",
                headers={
                    "X-API-Key": config.API_KEY
                },
                timeout=5
            )

            response.raise_for_status()

            data = response.json()


            # ---------------------------------------------
            # Éviter de traiter plusieurs fois
            # la même mesure
            # ---------------------------------------------

            measure_id = data.get("_id")

            if measure_id is not None and measure_id == last_measure_id:
                time.sleep(POLL_INTERVAL_S)
                continue

            last_measure_id = measure_id


            # ---------------------------------------------
            # Vérification des données nécessaires
            # ---------------------------------------------

            required = [
                "temp",
                "hum",
                "gaz",
                "gaz_base"
            ]

            if any(data.get(k) is None for k in required):
                print("Mesure incomplète ignorée :", data)

                time.sleep(POLL_INTERVAL_S)
                continue


            # ---------------------------------------------
            # Ajout de la mesure dans notre historique
            # ---------------------------------------------

            buffer.append({
                "temp": data["temp"],
                "hum": data["hum"],
                "gaz": data["gaz"],
                "gaz_base": data["gaz_base"]
            })


            # ---------------------------------------------
            # Il faut suffisamment de mesures pour
            # calculer les features temporelles
            # ---------------------------------------------

            if len(buffer) < window:

                print(
                    f"Remplissage de la fenêtre "
                    f"{len(buffer)}/{window}"
                )

                time.sleep(POLL_INTERVAL_S)
                continue


            # ---------------------------------------------
            # Calcul des features
            # ---------------------------------------------

            df_buffer = pd.DataFrame(list(buffer))

            features = compute_features(df_buffer)

            if features.empty:
                time.sleep(POLL_INTERVAL_S)
                continue


            # On ne veut analyser que la mesure la plus récente
            row = features.iloc[[-1]]


            # ---------------------------------------------
            # Isolation Forest
            # ---------------------------------------------

            score = float(
                model.decision_function(row)[0]
            )

            prediction = model.predict(row)[0]

            abnormal = prediction == -1


            # ---------------------------------------------
            # Compteur d'anomalies consécutives
            # ---------------------------------------------

            if abnormal:
                state["streak"] += 1
            else:
                state["streak"] = 0


            # ---------------------------------------------
            # Affichage console
            # ---------------------------------------------

            print(
                f"temp={data['temp']} "
                f"hum={data['hum']} "
                f"gaz={data['gaz']} "
                f"gaz_base={data['gaz_base']} "
                f"score={score:+.3f} "
                f"{'ANORMAL' if abnormal else 'OK'}"
            )


            # ---------------------------------------------
            # Création de l'alerte
            # ---------------------------------------------

            if state["streak"] >= needed:

                alert_type, main_factor = explain(
                    row.iloc[0],
                    bundle["mean"],
                    bundle["std"]
                )

                now = time.time()

                last_alert_time = state["last_alert"].get(
                    alert_type,
                    0
                )

                # Évite de spammer les alertes
                if now - last_alert_time >= COOLDOWN_S:

                    state["last_alert"][alert_type] = now

                    level = (
                        "critical"
                        if score < bundle["critical_threshold"]
                        else "warning"
                    )

                    alert = build_alert(
                        "anomaly",
                        alert_type,
                        level,
                        score,
                        {
                            "temp": data["temp"],
                            "hum": data["hum"],
                            "gaz": data["gaz"],
                            "gaz_base": data["gaz_base"],
                            "main_factor": main_factor
                        }
                    )

                    send_alert(alert)


        # -------------------------------------------------
        # Erreur API / réseau
        # -------------------------------------------------

        except requests.RequestException as e:

            print("Erreur API :", e)


        except KeyboardInterrupt:

            print("\nArrêt de la surveillance.")
            break


        except Exception as e:

            print("Erreur pendant l'analyse :", e)


        time.sleep(POLL_INTERVAL_S)


if __name__ == "__main__":
    main()
