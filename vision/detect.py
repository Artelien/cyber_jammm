"""IA vision : détection de personnes sur la webcam avec YOLOv8n.

Lancement :
    python -m vision.detect
    python -m vision.detect --cam 1
    python -m vision.detect --no-show
    python -m vision.detect --imgsz 416
    python -m vision.detect --stream 8081

Fonctionnement :
- webcam en 640x480 ;
- YOLOv8n détecte uniquement les personnes ;
- une alerte "intrusion" est envoyée si une personne est détectée
  sur 3 images consécutives ;
- une capture annotée est enregistrée lors de l'intrusion ;
- délai de 15 secondes entre deux alertes pour éviter le spam ;
- possibilité d'exposer le flux vidéo annoté en MJPEG ;
- à l'arrêt, les statistiques de latence sont enregistrées
  dans reports/vision_latency.json.
"""

import argparse
import json
import os
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

from common.alerts import build_alert, send_alert


HERE = Path(__file__).resolve().parent

CONSECUTIVE = 3
COOLDOWN_S = 15

latest_jpeg = {
    "data": None
}


class MJPEGHandler(BaseHTTPRequestHandler):
    """Petit serveur HTTP pour diffuser le flux vidéo annoté."""

    def do_GET(self):

        if self.path != "/video":
            self.send_error(404)
            return

        self.send_response(200)

        self.send_header(
            "Content-Type",
            "multipart/x-mixed-replace; boundary=frame"
        )

        self.end_headers()

        try:

            while True:

                data = latest_jpeg["data"]

                if data is not None:

                    self.wfile.write(
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n"
                        + data
                        + b"\r\n"
                    )

                time.sleep(0.05)

        except (
            BrokenPipeError,
            ConnectionResetError
        ):
            pass

    def log_message(self, *args):
        pass


def open_camera(index):
    """Ouvre la webcam et configure la résolution."""

    if os.name == "nt":
        cap = cv2.VideoCapture(
            index,
            cv2.CAP_DSHOW
        )

    else:
        cap = cv2.VideoCapture(index)

    cap.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        640
    )

    cap.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        480
    )

    if not cap.isOpened():
        raise SystemExit(
            f"Webcam {index} introuvable. "
            f"Essaie par exemple --cam 1."
        )

    return cap


def save_capture(image, persons):
    """Enregistre une capture annotée lorsqu'une intrusion est détectée."""

    captures_dir = HERE / "captures"

    captures_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    timestamp = datetime.now().strftime(
        "%Y-%m-%d_%H-%M-%S"
    )

    filename = (
        captures_dir
        / f"intrusion_{timestamp}_{persons}personnes.jpg"
    )

    cv2.imwrite(
        str(filename),
        image
    )

    print(
        f"Capture enregistrée : {filename}"
    )


def main(args):

    print("Chargement de YOLOv8n...")

    model = YOLO("yolov8n.pt")

    print("Modèle YOLO chargé.")

    cap = open_camera(args.cam)

    print(f"Webcam {args.cam} ouverte.")

    if args.stream:

        server = ThreadingHTTPServer(
            (
                args.stream_host,
                args.stream
            ),
            MJPEGHandler
        )

        threading.Thread(
            target=server.serve_forever,
            daemon=True
        ).start()

        print(
            f"Flux vidéo : "
            f"http://{args.stream_host}:"
            f"{args.stream}/video"
        )

    latencies = []

    streak = 0

    last_alert = 0.0

    frame_count = 0

    try:

        while True:

            ok, frame = cap.read()

            if not ok:
                print("Lecture webcam impossible.")
                break

            frame = cv2.resize(
                frame,
                (640, 480)
            )

            start = time.perf_counter()

            result = model(
                frame,
                classes=[0],
                conf=args.conf,
                imgsz=args.imgsz,
                verbose=False
            )[0]

            latency_ms = (
                time.perf_counter() - start
            ) * 1000

            frame_count += 1

            if frame_count > 10:
                latencies.append(
                    latency_ms
                )

            persons = len(result.boxes)

            if persons > 0:
                streak += 1
            else:
                streak = 0

            # Image annotée par YOLO
            image = result.plot()

            color = (
                (0, 0, 255)
                if persons > 0
                else (0, 200, 0)
            )

            cv2.putText(
                image,
                (
                    f"{latency_ms:.0f} ms | "
                    f"personnes : {persons}"
                ),
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                color,
                2
            )

            # -------------------------------------------------
            # Intrusion confirmée
            # -------------------------------------------------

            if (
                streak >= CONSECUTIVE
                and
                time.time() - last_alert >= COOLDOWN_S
            ):

                last_alert = time.time()

                confidence = float(
                    result.boxes.conf.max()
                )

                # Sauvegarde de la capture annotée
                save_capture(
                    image,
                    persons
                )

                alert = build_alert(
                    source="vision",
                    alert_type="intrusion",
                    level="critical",
                    value=confidence,
                    details={
                        "persons": persons,
                        "latency_ms": round(
                            latency_ms,
                            1
                        )
                    }
                )

                send_alert(alert)

            if args.stream:

                success, encoded = cv2.imencode(
                    ".jpg",
                    image,
                    [
                        cv2.IMWRITE_JPEG_QUALITY,
                        70
                    ]
                )

                if success:
                    latest_jpeg["data"] = (
                        encoded.tobytes()
                    )

            if args.show:

                cv2.imshow(
                    "Sentinel-X Vision",
                    image
                )

                if (
                    cv2.waitKey(1) & 0xFF
                    == ord("q")
                ):
                    break

            if (
                latencies
                and frame_count % 50 == 0
            ):

                print(
                    f"Latence moyenne : "
                    f"{np.mean(latencies):.0f} ms | "
                    f"p95 : "
                    f"{np.percentile(latencies, 95):.0f} ms"
                )

    except KeyboardInterrupt:

        print("\nArrêt demandé.")

    finally:

        cap.release()

        cv2.destroyAllWindows()

        if latencies:

            p95 = float(
                np.percentile(
                    latencies,
                    95
                )
            )

            stats = {
                "frames": len(latencies),
                "resolution": "640x480",
                "imgsz": args.imgsz,
                "modele": "yolov8n",

                "latence_moyenne_ms": round(
                    float(
                        np.mean(latencies)
                    ),
                    1
                ),

                "latence_p95_ms": round(
                    p95,
                    1
                ),

                "objectif_100ms_respecte": (
                    p95 < 100
                )
            }

            reports_dir = (
                HERE / "reports"
            )

            reports_dir.mkdir(
                parents=True,
                exist_ok=True
            )

            report_file = (
                reports_dir
                / "vision_latency.json"
            )

            report_file.write_text(
                json.dumps(
                    stats,
                    indent=2,
                    ensure_ascii=False
                )
            )

            print("\nRapport de latence :")

            print(
                json.dumps(
                    stats,
                    indent=2,
                    ensure_ascii=False
                )
            )


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--cam",
        type=int,
        default=0,
        help="Index de la webcam"
    )

    parser.add_argument(
        "--conf",
        type=float,
        default=0.5,
        help="Confiance minimale YOLO"
    )

    parser.add_argument(
        "--imgsz",
        type=int,
        default=416,
        help="Taille d'analyse YOLO"
    )

    parser.add_argument(
        "--no-show",
        dest="show",
        action="store_false",
        help="Désactive la fenêtre OpenCV"
    )

    parser.add_argument(
        "--stream",
        type=int,
        default=0,
        help="Port du flux vidéo MJPEG"
    )

    parser.add_argument(
        "--stream-host",
        default="127.0.0.1",
        help="Adresse d'écoute du flux vidéo"
    )

    main(
        parser.parse_args()
    )
