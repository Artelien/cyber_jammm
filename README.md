# Sentinel-X — Partie IA

La partie IA de Sentinel-X repose sur deux modules :

| Module | Source de données | Rôle | Statut |
|---|---|---|---|
| **Vision** | Webcam USB du PC serveur | Détection de personnes / intrusion physique | ✅ Fonctionnel |
| **Anomalies capteurs** | Télémétrie ESP32 récupérée via FastAPI | Détection de comportements anormaux des capteurs | ✅ Fonctionnel |

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
