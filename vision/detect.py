"""IA vision : détection d'intrus sur la webcam avec YOLOv8n.

  python -m vision.detect                 # webcam 0, fenêtre d'affichage
  python -m vision.detect --cam 1         # webcam USB
  python -m vision.detect --no-show       # sans fenêtre (sur le serveur)
  python -m vision.detect --imgsz 416     # plus rapide si la latence dépasse 100 ms
  python -m vision.detect --stream 8081   # flux vidéo annoté sur http://127.0.0.1:8081/video

- Images réduites en 640x480 pour rester sous 100 ms par trame.
- Alerte "intrusion" si une personne est vue sur 3 images d'affilée
  (évite les fausses détections d'une seule image), puis 15 s de pause.
- À l'arrêt (q ou Ctrl+C) : statistiques de latence dans reports/vision_latency.json
  (moyenne, p95) -> à mettre dans le dossier technique.
"""
import argparse
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

from common.alerts import build_alert, send_alert

HERE = Path(__file__).resolve().parent
CONSECUTIVE = 3
COOLDOWN_S = 15
latest_jpeg = {"data": None}


class MJPEGHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/video":
            self.send_error(404); return
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()
        try:
            while True:
                data = latest_jpeg["data"]
                if data:
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + data + b"\r\n")
                time.sleep(0.05)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *args):
        pass


def open_camera(index):
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW) if os.name == "nt" else cv2.VideoCapture(index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    if not cap.isOpened():
        raise SystemExit(f"Webcam {index} introuvable : essaie --cam 1")
    return cap


def main(a):
    model = YOLO("yolov8n.pt")
    cap = open_camera(a.cam)
    if a.stream:
        server = ThreadingHTTPServer((a.stream_host, a.stream), MJPEGHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        print(f"Flux vidéo : http://{a.stream_host}:{a.stream}/video")

    latencies, streak, last_alert, n = [], 0, 0.0, 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Lecture webcam impossible"); break
            frame = cv2.resize(frame, (640, 480))

            t0 = time.perf_counter()
            res = model(frame, classes=[0], conf=a.conf, imgsz=a.imgsz, verbose=False)[0]  # classe 0 = personne
            ms = (time.perf_counter() - t0) * 1000
            n += 1
            if n > 10:  # on ignore le temps de chauffe du modèle
                latencies.append(ms)

            persons = len(res.boxes)
            streak = streak + 1 if persons else 0
            if streak >= CONSECUTIVE and time.time() - last_alert >= COOLDOWN_S:
                last_alert = time.time()
                conf = float(res.boxes.conf.max())
                send_alert(build_alert("vision", "intrusion", "critical", conf,
                                       {"persons": persons, "latency_ms": round(ms, 1)}))

            image = res.plot()
            color = (0, 0, 255) if persons else (0, 200, 0)
            cv2.putText(image, f"{ms:.0f} ms | personnes : {persons}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            if a.stream:
                latest_jpeg["data"] = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 70])[1].tobytes()
            if a.show:
                cv2.imshow("Sentinel-X vision", image)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            if latencies and n % 50 == 0:
                print(f"latence moyenne {np.mean(latencies):.0f} ms | p95 {np.percentile(latencies, 95):.0f} ms")
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        cv2.destroyAllWindows()
        if latencies:
            stats = {"frames": len(latencies), "resolution": "640x480", "imgsz": a.imgsz, "modele": "yolov8n",
                     "latence_moyenne_ms": round(float(np.mean(latencies)), 1),
                     "latence_p95_ms": round(float(np.percentile(latencies, 95)), 1),
                     "objectif_100ms_respecte": bool(np.percentile(latencies, 95) < 100)}
            (HERE / "reports").mkdir(exist_ok=True)
            (HERE / "reports" / "vision_latency.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False))
            print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--cam", type=int, default=0)
    p.add_argument("--conf", type=float, default=0.5)
    p.add_argument("--imgsz", type=int, default=640, help="taille d'analyse YOLO (480 ou 416 si > 100 ms)")
    p.add_argument("--no-show", dest="show", action="store_false")
    p.add_argument("--stream", type=int, default=0, help="port du flux MJPEG (0 = désactivé)")
    p.add_argument("--stream-host", default="127.0.0.1",
                   help="127.0.0.1 par défaut : exposer via l'API en HTTPS plutôt qu'en direct")
    main(p.parse_args())
