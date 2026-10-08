# Sentinel-X — Partie IA

La partie IA de **Sentinel-X** repose sur deux modules principaux :

| Module | Source de données | Rôle | Statut |
|---|---|---|---|
| **Vision** | Webcam USB du PC serveur | Détection de personnes / intrusion physique | **Fonctionnel** |
| **Anomalies capteurs** | Télémétrie ESP32 récupérée via FastAPI | Détection de comportements anormaux des capteurs | **Fonctionnel** |

La partie IA est exécutée directement sur le **PC serveur** avec Python.

Elle **n'est pas exécutée dans Docker**.

L'API, MongoDB, Mosquitto, le Collector et le dashboard sont exécutés dans Docker.

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
Isolation Forest
```

En parallèle, pour la vision :

```text
Webcam USB
  ↓
OpenCV
  ↓
YOLOv8n
```

Les deux modules IA envoient ensuite leurs résultats à FastAPI :

```text
Isolation Forest ──┐
                   ├──> POST /analysis/result
YOLOv8n ───────────┘
                         ↓
                      FastAPI
                         ↓
                      Dashboard
```

---

# 2. Module Vision

## 2.1 Objectif

Le module vision utilise **YOLOv8n** avec **OpenCV** pour détecter la présence de personnes à partir de la webcam du PC serveur.

La détection est limitée à la classe :

```text
person
```

Dans le modèle COCO utilisé par YOLO, la classe `0` correspond à une personne :

```python
classes=[0]
```

Le système ne réalise **pas de reconnaissance faciale** et ne cherche pas à identifier les personnes détectées.

---

## 2.2 Fonctionnement

Le fonctionnement général est le suivant :

```text
Webcam
  ↓
OpenCV
  ↓
YOLOv8n
  ↓
Détection des personnes
  ↓
Comptage des personnes
  ↓
Confirmation de l'intrusion
```

Une intrusion est confirmée lorsqu'une personne est détectée sur **3 images consécutives**.

Cette règle permet d'éviter qu'une détection incorrecte sur une seule image déclenche immédiatement une alerte.

Après confirmation :

- une **alerte** est envoyée à l'API ;
- une **capture annotée** est enregistrée dans `vision/captures/` ;
- un délai de **15 secondes** est appliqué avant de pouvoir envoyer une nouvelle alerte.

---

## 2.3 Performances

### Configuration utilisée

- **Résolution webcam** : 640x480
- **Taille d'analyse YOLO** : 416 px
- **Modèle** : YOLOv8n

### Résultats mesurés

- **Latence moyenne** : environ 27 ms
- **Latence p95** : environ 35 ms
- **Objectif < 100 ms** : respecté

Le projet impose une latence inférieure à 100 ms.

Les mesures obtenues sont donc conformes :

```text
35 ms < 100 ms
```

Le rapport de latence est enregistré dans :

```text
vision/reports/vision_latency.json
```

---

## 2.4 Captures d'intrusion

Lorsqu'une intrusion est confirmée, une capture annotée est enregistrée automatiquement dans :

```text
vision/captures/
```

Exemple :

```text
intrusion_2026-10-08_12-35-41_4personnes.jpg
```

La capture contient les cadres de détection YOLO autour des personnes détectées.

Le dossier `vision/captures/` est généré automatiquement lors de l'exécution du programme.

Les captures sont conservées localement sur le PC serveur et ne sont pas versionnées sur GitHub.

---

## 2.5 Lancement

Depuis la racine du dossier IA :

```bash
python -m vision.detect --cam 0 --imgsz 416
```

Pour utiliser une autre webcam :

```bash
python -m vision.detect --cam 1 --imgsz 416
```

Pour lancer le programme sans fenêtre graphique :

```bash
python -m vision.detect --no-show --imgsz 416
```

Pour exposer le flux vidéo MJPEG :

```bash
python -m vision.detect --stream 8081
```

Lorsque la fenêtre OpenCV est affichée, la touche :

```text
q
```

permet d'arrêter proprement la détection.

---

# 3. Module Anomalies Capteurs

## 3.1 Objectif

Le module de détection d'anomalies utilise un modèle **Isolation Forest**.

Son objectif est de détecter des comportements inhabituels dans les données provenant des capteurs de l'ESP32.

Les principales données surveillées sont :

- la **température** ;
- l'**humidité** ;
- le **niveau de gaz** ;
- la **valeur de référence du gaz**.

Le modèle apprend le comportement considéré comme normal puis identifie les nouvelles observations qui s'en éloignent.

---

## 3.2 Pourquoi Isolation Forest ?

Le projet ne repose pas uniquement sur des règles fixes comme :

```python
if temperature > 40:
    alerte()
```

Isolation Forest analyse plusieurs variables simultanément.

Il peut donc identifier un comportement inhabituel même lorsqu'une seule valeur n'a pas encore dépassé un seuil fixe.

---

## 3.3 Variables utilisées

Les données brutes utilisées sont :

```text
temp
hum
gaz
gaz_base
```

À partir de ces valeurs, le fichier :

```text
anomaly/features.py
```

calcule les features suivantes :

```text
temp
hum
gaz
gaz_ecart
temp_delta
hum_delta
gaz_delta
gaz_std
```

Le modèle utilise donc **8 features**.

---

## 3.4 Écart du gaz

La variable :

```text
gaz_ecart
```

est calculée avec :

```text
gaz_ecart = gaz - gaz_base
```

Elle représente l'écart entre le niveau de gaz actuel et sa valeur de référence.

---

## 3.5 Variables temporelles

Les variables :

```text
temp_delta
hum_delta
gaz_delta
```

permettent d'étudier l'évolution des capteurs dans le temps.

Elles sont calculées sur une fenêtre de :

```text
15 mesures
```

Avec une mesure environ toutes les 2 secondes :

```text
15 mesures ≈ 30 secondes
```

Cela permet au modèle de prendre en compte une montée ou une baisse rapide d'un capteur.

---

## 3.6 Variabilité du gaz

La feature :

```text
gaz_std
```

représente la variabilité du gaz sur la fenêtre temporelle.

Elle permet notamment de repérer un comportement instable du capteur de gaz.

---

# 4. Dataset d'entraînement

## 4.1 Dataset final

Le dataset utilisé pour entraîner le modèle est :

```text
anomaly/data/train.csv
```

Il contient les colonnes :

```text
timestamp
temp
hum
gaz
gaz_base
```

Le dataset final contient :

- **1978 mesures brutes**
- **1964 fenêtres utilisables** après création des features temporelles

---

## 4.2 Origine des données

Le jeu de données initial utilisé pour préparer l'entraînement provient du dataset public :

```text
Smoke Detection IoT
```

Les variables utilisées initialement comprennent notamment :

```text
Temperature
Humidity
TVOC
Fire Alarm
```

Le dataset public ne contient pas exactement le même capteur de gaz MQ-2 que celui utilisé dans Sentinel-X.

La variable :

```text
gaz
```

a donc été construite à partir du signal TVOC afin d'obtenir une donnée compatible avec le format attendu par Sentinel-X.

La variable :

```text
gaz_base
```

a également été générée afin de représenter une référence dynamique du capteur.

Ces valeurs ne doivent donc pas être considérées comme de véritables mesures MQ-2.

Elles permettent de développer et d'entraîner le pipeline IA avant de disposer d'un historique suffisamment important provenant du système Sentinel-X réel.

---

# 5. Entraînement du modèle

## 5.1 Script d'entraînement

Le modèle est entraîné avec :

```text
anomaly/train.py
```

La configuration utilisée est :

```python
IsolationForest(
    n_estimators=300,
    contamination=0.005,
    random_state=42
)
```

---

## 5.2 Lancement de l'entraînement

Depuis la racine du dossier IA :

```bash
python -m anomaly.train
```

Lors du dernier entraînement :

```text
Nombre de mesures brutes : 1978
Nombre de fenêtres utilisables : 1964
Anomalies détectées dans les données d'entraînement : 10 / 1964
```

Le modèle entraîné est enregistré dans :

```text
anomaly/models/isoforest.joblib
```

Le fichier `isoforest.joblib` est conservé dans le projet afin que la détection puisse être lancée sans avoir besoin de réentraîner le modèle à chaque démarrage.

---

# 6. Détection d'anomalies en temps réel

Le script utilisé pour la surveillance en temps réel est :

```text
anomaly/detect_live.py
```

La partie IA ne récupère pas directement les données depuis MQTT.

Elle interroge l'API FastAPI avec :

```text
GET /telemetry/latest
```

Exemple de télémétrie reçue :

```json
{
  "_id": "...",
  "device": "sentinel-x",
  "temp": 28.2,
  "hum": 53.8,
  "gaz": 341,
  "gaz_base": 350,
  "mouvement": 1,
  "etat": "NORMAL",
  "sim": 1,
  "rssi": -33,
  "uptime": 5071
}
```

Pour Isolation Forest, les principales valeurs utilisées sont :

```text
temp
hum
gaz
gaz_base
```

---

## 6.1 Règle anti-fausses alertes

Une mesure anormale isolée ne déclenche pas immédiatement une alerte.

Il faut :

```text
3 anomalies consécutives
```

pour confirmer l'anomalie.

Avec une mesure toutes les 2 secondes :

```text
3 mesures ≈ 6 secondes
```

Cette règle permet de réduire les fausses alertes provoquées par un bruit ponctuel.

---

## 6.2 Types d'anomalies

Une fois l'anomalie confirmée, le système analyse la feature qui s'écarte le plus du comportement normal.

Les principaux types d'alertes possibles sont :

```text
gas_leak
overheat
temperature
humidity
```

Ils correspondent à :

- **gas_leak** : fuite de gaz suspectée
- **overheat** : surchauffe détectée
- **temperature** : température inhabituelle
- **humidity** : humidité inhabituelle

---

# 7. Communication avec FastAPI et le Dashboard

## 7.1 Fonctionnement général

L'IA **ne communique pas directement avec le dashboard**.

Les deux modules IA envoient leurs résultats à FastAPI avec :

```text
POST /analysis/result
```

Le dashboard récupère ensuite le dernier résultat avec :

```text
GET /analysis/latest
```

Le fonctionnement est donc :

```text
IA
↓
FastAPI
↓
Dashboard
```

---

## 7.2 Format envoyé par l'IA

Les modules IA utilisent le même format :

```json
{
  "risk": "CRITICAL",
  "score": 94,
  "message": "Presence humaine detectee"
}
```

Les informations envoyées sont :

- **risk** : niveau de risque ;
- **score** : score de sévérité entre 0 et 100 ;
- **message** : description lisible de l'événement détecté.

Les niveaux de risque possibles sont :

```text
LOW
MEDIUM
HIGH
CRITICAL
```

---

## 7.3 Exemple avec la Vision

Si YOLO détecte une personne avec une confiance de :

```text
0.94
```

le module vision peut envoyer :

```json
{
  "risk": "CRITICAL",
  "score": 94,
  "message": "Presence humaine detectee"
}
```

Le score vision correspond à la confiance YOLO convertie sur une échelle de 0 à 100.

---

## 7.4 Exemple avec Isolation Forest

En cas d'anomalie liée au gaz :

```json
{
  "risk": "HIGH",
  "score": 63,
  "message": "Fuite de gaz suspectee"
}
```

Ou en cas de surchauffe :

```json
{
  "risk": "HIGH",
  "score": 51,
  "message": "Surchauffe detectee"
}
```

Le score Isolation Forest n'est pas une probabilité.

Il est converti sur une échelle de 0 à 100 afin de fournir au dashboard un indicateur de sévérité facilement affichable.

---

## 7.5 Données affichées séparément

Les données comme :

- **température**
- **humidité**
- **gaz**
- **gaz_base**
- **mouvement**

ne sont pas envoyées par l'IA dans `/analysis/result`.

Elles proviennent directement de la télémétrie récupérée par FastAPI.

Le dashboard combine donc :

```text
Télémétrie capteurs
+
Résultat IA
```

afin d'afficher l'état global du système Sentinel-X.

---

# 8. Configuration

La configuration locale de l'IA est stockée dans :

```text
.env
```

Exemple :

```env
API_BASE_URL=http://localhost:8000
API_KEY=
DEVICE_ID=sentinel-x
```

Comme la partie IA fonctionne directement sur le PC serveur et non dans Docker, elle utilise :

```text
http://localhost:8000
```

pour accéder à FastAPI exposée par Docker sur le PC serveur.

Le fichier `.env` peut contenir des informations sensibles comme la clé API.

Il ne doit donc **jamais être envoyé sur GitHub**.

Le fichier :

```text
.env.example
```

sert uniquement de modèle et peut être versionné.

---

# 9. Installation

## 9.1 Windows

Créer un environnement virtuel :

```bash
python -m venv .venv
```

L'activer :

```bash
.venv\Scripts\activate
```

---

## 9.2 macOS / Linux

Créer l'environnement :

```bash
python3 -m venv .venv
```

L'activer :

```bash
source .venv/bin/activate
```

---

## 9.3 Installer les dépendances

```bash
pip install -r requirements.txt
```

Le fichier `requirements.txt` contient notamment :

```text
ultralytics
opencv-python
numpy
pandas
scikit-learn
joblib
requests
python-dotenv
```

---

# 10. Lancement sur le PC serveur

L'IA fonctionne directement sur le PC serveur.

Les autres composants de Sentinel-X peuvent être exécutés dans Docker.

Architecture d'exécution :

```text
PC serveur

Python
├── anomaly.detect_live
└── vision.detect

Docker
├── FastAPI
├── MongoDB
├── Mosquitto
├── Collector
└── Dashboard
```

---

## 10.1 Lancer Isolation Forest

Dans un premier terminal :

```bash
python -m anomaly.detect_live
```

---

## 10.2 Lancer la Vision

Dans un deuxième terminal :

```bash
python -m vision.detect --cam 0 --imgsz 416
```

Les deux programmes peuvent ainsi fonctionner simultanément.

---

# 11. Organisation des fichiers

```text
IA/
│
├── anomaly/
│   ├── data/
│   │   └── train.csv
│   │
│   ├── models/
│   │   └── isoforest.joblib
│   │
│   ├── __init__.py
│   ├── features.py
│   ├── train.py
│   └── detect_live.py
│
├── common/
│   ├── __init__.py
│   ├── config.py
│   └── alerts.py
│
├── vision/
│   ├── reports/
│   │   └── vision_latency.json
│   │
│   ├── captures/
│   ├── __init__.py
│   └── detect.py
│
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

# 12. Fichiers ignorés par Git

Les fichiers locaux ou générés automatiquement ne doivent pas être envoyés sur GitHub.

Exemple de `.gitignore` :

```gitignore
.venv/
.env
__pycache__/
*.pyc
*.pt

anomaly/data/sim_*.csv
anomaly/data/calib_*.csv
anomaly/data/*.txt

vision/captures/
```

Le modèle :

```text
anomaly/models/isoforest.joblib
```

est en revanche conservé dans le dépôt afin que le système puisse fonctionner sans réentraînement.

---


