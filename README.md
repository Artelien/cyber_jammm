# Sentinel-X — Partie IA

La partie IA de Sentinel-X repose sur deux modules :

| Module | Source de données | Rôle | Statut |
|---|---|---|---|
| **Vision** | Webcam USB du PC serveur | Détection de personnes / intrusion physique | Fonctionnel |
| **Anomalies capteurs** | Télémétrie ESP32 récupérée via FastAPI | Détection de comportements anormaux des capteurs | Fonctionnel |

La partie IA est exécutée directement sur le **PC serveur** avec Python.

Elle n'est pas exécutée dans Docker.

L'API, MongoDB, Mosquitto, le Collector et le dashboard peuvent rester exécutés dans Docker.

---

# 1. Architecture générale

Architecture simplifiée de Sentinel-X :

```text
ESP32
  ↓
MQTT
  ↓
Mosquitto
  ↓
Collector
  ↓
MongoDB
  ↓
FastAPI
  ↓
IA Python
  ├── Isolation Forest
  └── YOLOv8n
  ↓
POST /analysis/result
  ↓
Dashboard

## 2. Module vision

Le module vision utilise YOLOv8n avec OpenCV pour détecter la présence de personnes à partir de la webcam du PC serveur.

La détection est limitée à la classe `person`.

Une intrusion est confirmée lorsqu'une personne est détectée sur 3 images consécutives.

Après confirmation :
- une alerte est envoyée à l'API ;
- une capture annotée est enregistrée dans `vision/captures/` ;
- un délai de 15 secondes est appliqué avant une nouvelle alerte.

### Performances

Configuration utilisée :
- résolution webcam : 640x480 ;
- taille d'analyse YOLO : 416 px ;
- modèle : YOLOv8n.

Résultats mesurés :
- latence moyenne : environ 27 ms ;
- latence p95 : environ 35 ms ;
- objectif inférieur à 100 ms respecté.

Le rapport de latence est enregistré dans :

`vision/reports/vision_latency.json`

### Lancement

```bash
python -m vision.detect --cam 0 --imgsz 416
