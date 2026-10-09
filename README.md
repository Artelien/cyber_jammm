# Sentinel-X — Cyberjammm

## Système intelligent de surveillance et de sécurisation industrielle

**Sentinel-X** est une solution de surveillance cyber-physique développée dans le cadre du **Workshop 2026**.

L'objectif est de superviser un environnement industriel en temps réel grâce à plusieurs briques complémentaires :

- acquisition de données par **ESP32 et capteurs** ;
- communication sécurisée via **MQTT / MQTTS** ;
- collecte et stockage des données ;
- exposition des données avec **FastAPI** ;
- détection d'anomalies avec **Isolation Forest** ;
- détection d'intrusions physiques avec **YOLOv8n** ;
- supervision à travers un **dashboard Streamlit** ;
- sécurisation réseau avec **TLS, authentification, firewall et isolation des services**.

---

# 1. Objectif du projet

Sentinel-X a pour objectif de détecter rapidement plusieurs types d'événements pouvant affecter un site industriel :

| Risque | Mécanisme de détection |
|---|---|
| **Fuite de gaz** | Capteur gaz + Isolation Forest |
| **Surchauffe** | Température + Isolation Forest |
| **Humidité inhabituelle** | Humidité + Isolation Forest |
| **Intrusion physique** | Webcam + YOLOv8n |
| **Accès réseau non autorisé** | Authentification + firewall |
| **Interception des communications MQTT** | TLS / MQTTS |

Sentinel-X cherche ainsi à couvrir à la fois :

- la **sécurité physique** ;
- la **surveillance environnementale** ;
- la **cybersécurité** ;
- la **supervision temps réel**.

---

# 2. Architecture générale

L'architecture du projet repose sur plusieurs composants indépendants.

```text
                         ┌─────────────────────┐
                         │        ESP32        │
                         │  + capteurs terrain │
                         └──────────┬──────────┘
                                    │
                               MQTT / MQTTS
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │     Mosquitto       │
                         │    MQTT Broker      │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │     Collector       │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │      MongoDB        │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │      FastAPI        │
                         └───────┬─────┬───────┘
                                 │     │
                                 │     │
                     télémétrie  │     │ dashboard
                                 ▼     ▼
                       Isolation      Streamlit
                        Forest
                           │
                           │ résultat IA
                           └───────────► FastAPI


Webcam USB
    │
    ▼
 OpenCV
    │
    ▼
 YOLOv8n
    │
    │ résultat IA
    ▼
 FastAPI
    │
    ▼
Dashboard
```

La partie **IA est exécutée directement sur le PC serveur**, notamment afin de permettre un accès simple à la webcam USB.

Les composants backend sont exécutés dans **Docker** :

- Mosquitto ;
- Collector ;
- MongoDB ;
- FastAPI ;
- Streamlit.

---

# 3. Organisation du dépôt

```text
cyber_jammm/
│
├── IA/
│   ├── anomaly/
│   │   ├── data/
│   │   │   └── train.csv
│   │   ├── models/
│   │   │   └── isoforest.joblib
│   │   ├── __init__.py
│   │   ├── features.py
│   │   ├── train.py
│   │   └── detect_live.py
│   │
│   ├── common/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── alerts.py
│   │
│   ├── vision/
│   │   ├── reports/
│   │   │   └── vision_latency.json
│   │   ├── captures/
│   │   ├── __init__.py
│   │   └── detect.py
│   │
│   ├── requirements.txt
│   └── .env.example
│
├── api/
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── collector/
│   ├── collector.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── mosquitto/
│   └── mosquitto.conf
│
├── streamlit/
│   ├── app.py
│   ├── config.toml
│   ├── requirements.txt
│   └── Dockerfile
│
├── docker-compose.yml
├── .gitignore
└── README.md
```

---

# 4. Partie IoT — ESP32 et capteurs

L'ESP32 constitue le point d'acquisition des données terrain.

Les principales mesures utilisées sont :

- **température** ;
- **humidité** ;
- **gaz** ;
- **gaz_base**, valeur de référence du gaz en fonctionnement normal ;
- **mouvement**.

Les capteurs sont interrogés périodiquement puis les données sont publiées vers le broker MQTT.

---

## 4.1 Fréquence d'envoi

Une nouvelle mesure est publiée environ toutes les :

```text
2 secondes
```

---

## 4.2 Format de télémétrie

Exemple de message transmis :

```json
{
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

---

# 5. Communication MQTT / MQTTS

Le protocole MQTT est utilisé pour transporter les données entre l'ESP32 et le serveur Sentinel-X.

Le broker utilisé est :

```text
Mosquitto
```

---

## 5.1 Topic de télémétrie

Les mesures sont publiées sur :

```text
sentinelx/telemetry
```

---

## 5.2 Topic des commandes

Le topic destiné aux commandes doit correspondre à la configuration finale du firmware ESP32.

```text
À compléter avec le topic exact utilisé pour les commandes.
```

Ce topic permet notamment de transmettre des ordres depuis le système vers l'ESP32 ou ses actionneurs.

---

## 5.3 Sécurisation des échanges

La communication MQTT est prévue en version sécurisée :

```text
MQTT + TLS = MQTTS
```

TLS permet de chiffrer les communications afin d'éviter qu'un attaquant présent sur le réseau puisse facilement lire ou modifier les données échangées.

Une authentification par :

```text
identifiant + mot de passe
```

est également utilisée pour limiter l'accès au broker.

---

# 6. Collector

Le **Collector** fait le lien entre Mosquitto et MongoDB.

Son rôle est de :

1. recevoir les messages MQTT ;
2. interpréter les données JSON ;
3. les transmettre vers la couche de stockage ;
4. rendre les données disponibles pour le reste de l'application.

Flux :

```text
ESP32
  ↓
MQTTS
  ↓
Mosquitto
  ↓
Collector
  ↓
MongoDB
```

---

# 7. MongoDB

MongoDB est utilisé pour conserver les données issues de la télémétrie.

Les mesures stockées peuvent ensuite être utilisées par :

- FastAPI ;
- le dashboard ;
- l'historique des mesures ;
- le module de détection d'anomalies.

La partie IA **n'accède pas directement à MongoDB**.

Elle passe par FastAPI afin de conserver une architecture découplée.

---

# 8. API — FastAPI

FastAPI constitue l'interface centrale entre les données, l'IA et le dashboard.

---

## 8.1 Récupération de la dernière télémétrie

```text
GET /telemetry/latest
```

Cette route permet notamment à l'IA de récupérer la dernière mesure disponible.

---

## 8.2 Historique de télémétrie

```text
GET /telemetry/history
```

Cette route permet de récupérer plusieurs mesures historiques.

Elle peut notamment être utilisée par le dashboard pour afficher des courbes.

---

## 8.3 Statistiques

```text
GET /telemetry/stats
```

Cette route permet de récupérer des statistiques calculées sur les données enregistrées.

---

## 8.4 Publication d'un résultat IA

Les modules IA utilisent :

```text
POST /analysis/result
```

Exemple :

```json
{
  "risk": "CRITICAL",
  "score": 94,
  "message": "Presence humaine detectee"
}
```

Les niveaux de risque possibles sont :

```text
LOW
MEDIUM
HIGH
CRITICAL
```

---

## 8.5 Lecture du dernier résultat IA

Le dashboard peut récupérer le dernier résultat grâce à :

```text
GET /analysis/latest
```

---

# 9. Dashboard — Streamlit

Le dashboard constitue l'interface de supervision de Sentinel-X.

Il permet de centraliser les informations provenant du système.

Il peut notamment afficher :

- les dernières mesures ;
- la température ;
- l'humidité ;
- le niveau de gaz ;
- l'état du dispositif ;
- les données historiques ;
- le résultat de l'IA ;
- le niveau de risque ;
- les messages d'alerte.

Le dashboard combine deux sources d'informations :

```text
Télémétrie des capteurs
+
Résultat des modèles IA
```

---

# 10. Intelligence artificielle

La partie IA de Sentinel-X repose sur deux modules complémentaires :

| Module IA | Source | Fonction |
|---|---|---|
| **Isolation Forest** | Télémétrie ESP32 | Détection d'anomalies capteurs |
| **YOLOv8n** | Webcam USB | Détection de personnes |

---

# 11. IA Vision — YOLOv8n

Le module vision utilise **OpenCV** et **YOLOv8n**.

Le modèle recherche uniquement la classe :

```text
person
```

Dans le modèle COCO :

```python
classes=[0]
```

Le système ne réalise aucune reconnaissance faciale et ne cherche pas à identifier la personne détectée.

---

## 11.1 Validation d'une intrusion

Une détection isolée n'est pas suffisante.

Une intrusion est confirmée lorsqu'une personne est détectée sur :

```text
3 images consécutives
```

Après confirmation :

- une alerte est générée ;
- une capture annotée est enregistrée ;
- le résultat est envoyé à FastAPI ;
- un délai de 15 secondes est appliqué avant une nouvelle alerte.

---

## 11.2 Captures

Les captures sont enregistrées localement dans :

```text
IA/vision/captures/
```

Exemple :

```text
intrusion_2026-10-08_12-35-41_4personnes.jpg
```

Le dossier est généré automatiquement lors de l'exécution et n'est pas versionné sur GitHub.

---

## 11.3 Performances

Configuration du test :

```text
Résolution : 640 x 480
YOLO imgsz : 416
Modèle : YOLOv8n
```

Résultats obtenus :

```text
Latence moyenne ≈ 27 ms
Latence p95 ≈ 35 ms
```

L'objectif du projet étant inférieur à :

```text
100 ms
```

le résultat respecte l'objectif fixé.

Le rapport est enregistré dans :

```text
IA/vision/reports/vision_latency.json
```

---

# 12. Détection d'anomalies — Isolation Forest

Le deuxième module utilise :

```text
Isolation Forest
```

Il s'agit d'un algorithme de détection d'anomalies non supervisé.

Le modèle est entraîné principalement sur un comportement considéré comme normal.

L'objectif est ensuite d'identifier les nouvelles observations qui s'éloignent de ce comportement.

---

## 12.1 Données d'entrée

Les données utilisées sont :

```text
temp
hum
gaz
gaz_base
```

---

## 12.2 Features utilisées

À partir de ces données, le fichier :

```text
IA/anomaly/features.py
```

calcule exactement les features suivantes :

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

### `gaz_ecart`

```text
gaz_ecart = gaz - gaz_base
```

Cette feature représente l'écart du niveau actuel de gaz par rapport à sa valeur de référence.

### `temp_delta`

Variation de la température sur la fenêtre temporelle.

### `hum_delta`

Variation de l'humidité sur la fenêtre temporelle.

### `gaz_delta`

Variation du gaz sur la fenêtre temporelle.

### `gaz_std`

Écart-type du gaz sur la fenêtre temporelle.

Cette feature permet de mesurer l'instabilité du signal.

---

## 12.3 Fenêtre temporelle

Le modèle travaille avec :

```text
15 mesures
```

Avec une mesure toutes les 2 secondes :

```text
15 mesures ≈ 30 secondes
```

Le modèle analyse ainsi non seulement la valeur actuelle, mais également son évolution récente.

---

# 13. Dataset d'entraînement

Le dataset final se trouve dans :

```text
IA/anomaly/data/train.csv
```

Il contient :

```text
timestamp
temp
hum
gaz
gaz_base
```

Nombre de mesures :

```text
1 978 mesures brutes
```

Après calcul des features temporelles :

```text
1 964 fenêtres exploitables
```

Les premières mesures ne disposent pas encore d'un historique suffisant pour former une fenêtre complète, ce qui explique cette différence.

---

## 13.1 Origine des données

Le dataset initial provient du jeu de données public :

```text
Smoke Detection IoT
```

Il contient notamment :

```text
Temperature
Humidity
TVOC
Fire Alarm
```

Le dataset public n'utilisant pas exactement le même capteur MQ-2 que Sentinel-X, le signal :

```text
gaz
```

a été construit à partir du TVOC afin d'obtenir une donnée compatible avec le format de l'application.

Une valeur :

```text
gaz_base
```

a également été générée pour représenter la référence dynamique du capteur.

Ces valeurs ne doivent donc pas être considérées comme de véritables mesures MQ-2.

Un futur réentraînement avec un historique plus important des véritables capteurs Sentinel-X permettra d'améliorer la représentativité du modèle.

---

# 14. Entraînement Isolation Forest

Le modèle utilise :

```python
IsolationForest(
    n_estimators=300,
    contamination=0.005,
    random_state=42
)
```

Le paramètre :

```text
contamination = 0.005
```

correspond à environ :

```text
0,5 %
```

des observations d'entraînement considérées comme potentiellement atypiques.

Lors du dernier entraînement :

```text
Mesures brutes : 1978
Fenêtres exploitables : 1964
Anomalies détectées pendant l'entraînement : 10 / 1964
```

Le modèle entraîné est enregistré dans :

```text
IA/anomaly/models/isoforest.joblib
```

---

# 15. Détection d'anomalies en temps réel

Le script :

```text
IA/anomaly/detect_live.py
```

interroge régulièrement :

```text
GET /telemetry/latest
```

Il conserve les dernières mesures afin de construire la fenêtre temporelle utilisée par le modèle.

---

## 15.1 Règle anti-fausses alertes

Une seule observation anormale ne déclenche pas immédiatement une alerte.

Il faut :

```text
3 anomalies consécutives
```

Avec une nouvelle mesure environ toutes les 2 secondes :

```text
3 mesures ≈ 6 secondes
```

Cette règle permet de limiter les fausses alertes ponctuelles.

---

## 15.2 Types d'anomalies

Une anomalie confirmée peut être interprétée comme :

```text
gas_leak
overheat
temperature
humidity
```

Ce qui correspond à :

- **fuite de gaz suspectée** ;
- **surchauffe détectée** ;
- **température inhabituelle** ;
- **humidité inhabituelle**.

---

# 16. Communication IA → API → Dashboard

Les modules IA ne communiquent pas directement avec le dashboard.

Le fonctionnement est :

```text
IA
↓
POST /analysis/result
↓
FastAPI
↓
GET /analysis/latest
↓
Dashboard
```

Format du résultat :

```json
{
  "risk": "HIGH",
  "score": 63,
  "message": "Fuite de gaz suspectee"
}
```

Le champ :

```text
score
```

est compris entre 0 et 100.

Pour YOLO, il correspond à la confiance du modèle convertie sur 100.

Pour Isolation Forest, il s'agit d'un indicateur de sévérité calculé à partir du score d'anomalie.

Il ne doit pas être interprété comme une probabilité.

---

# 17. Cybersécurité

La sécurité de Sentinel-X repose sur plusieurs niveaux complémentaires.

L'objectif est d'appliquer une logique de :

```text
défense en profondeur
```

et de :

```text
moindre privilège
```

---

## 17.1 MQTT sécurisé

Les échanges entre l'ESP32 et Mosquitto sont protégés avec :

```text
TLS
```

ce qui transforme MQTT en :

```text
MQTTS
```

---

## 17.2 Authentification

L'accès au broker utilise une authentification par :

```text
identifiant
+
mot de passe
```

afin d'empêcher une connexion anonyme au broker.

---

## 17.3 Firewall

Une règle firewall limite les communications autorisées.

Une adresse réseau est attribuée / identifiée pour l'ESP32.

Le principe appliqué est :

```text
ESP32 autorisé
      ↓
Mosquitto
      ✅

Autre machine
      ↓
Mosquitto
      ❌
```

L'objectif est que seuls les équipements explicitement autorisés puissent atteindre le broker.

---

## 17.4 Docker

Les composants backend sont isolés dans différents services Docker.

Les accès externes inutiles sont fermés et seuls les ports nécessaires sont exposés.

Cette isolation permet de réduire la surface d'attaque.

---

## 17.5 API

Les routes protégées utilisent une clé API transmise dans l'en-tête :

```text
X-API-Key
```

Les secrets applicatifs ne sont pas stockés directement dans le code source.

Ils sont placés dans des variables d'environnement.

---

## 17.6 Secrets

Le fichier :

```text
.env
```

ne doit jamais être versionné.

Il est donc ajouté au :

```text
.gitignore
```

Un fichier :

```text
.env.example
```

peut être fourni comme modèle sans contenir les véritables secrets.

---

# 18. Matrice de sécurité simplifiée

| Risque | Protection appliquée | Technologie |
|---|---|---|
| Interception des données MQTT | Chiffrement | TLS / MQTTS |
| Accès non autorisé au broker | Authentification | User / Password |
| Accès réseau externe | Filtrage | Firewall |
| Machine non autorisée vers Mosquitto | Restriction réseau | Règle IP |
| Exposition excessive des services | Isolation | Docker |
| Accès non autorisé à l'API | Authentification | X-API-Key |
| Fuite de secrets | Variables d'environnement | `.env` |
| Intrusion physique | Détection vision | YOLOv8n |

---

# 19. Docker

Les services backend sont orchestrés avec :

```text
docker-compose.yml
```

Les principaux services sont :

```text
Mosquitto
Collector
MongoDB
FastAPI
Streamlit
```

La partie IA reste exécutée directement sur le PC serveur.

---

# 20. Installation de la partie IA

Depuis le dossier :

```text
IA/
```

Créer un environnement virtuel.

## Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

## macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Installer les dépendances :

```bash
pip install -r requirements.txt
```

Les principales dépendances sont :

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

# 21. Configuration de l'IA

Créer un fichier :

```text
IA/.env
```

à partir de :

```text
IA/.env.example
```

Exemple :

```env
API_BASE_URL=http://localhost:8000
API_KEY=
DEVICE_ID=sentinel-x
```

La valeur réelle de `API_KEY` ne doit pas être placée sur GitHub.

---

# 22. Lancement de l'IA

## Détection d'anomalies

Depuis le dossier `IA` :

```bash
python -m anomaly.detect_live
```

---

## Vision

Dans un deuxième terminal :

```bash
python -m vision.detect --cam 0 --imgsz 416
```

Pour arrêter la fenêtre vision :

```text
q
```

---

# 23. Gitignore

Les fichiers générés localement ou sensibles sont ignorés.

Exemple :

```gitignore
.venv/
.env
__pycache__/
*.pyc
*.pt
.DS_Store

vision/captures/
```

Le modèle entraîné :

```text
IA/anomaly/models/isoforest.joblib
```

est conservé dans le dépôt afin de permettre le lancement du système sans réentraînement.

---


# 25. Équipe

Projet réalisé dans le cadre du **Workshop 2026**.

**Groupe G1 — Cyberjammm**

Sentinel-X combine :

**IoT · Cybersécurité · Intelligence artificielle · Vision · API · Docker · Supervision**

> **Sentinel-X : la sécurité à la bordure.**
