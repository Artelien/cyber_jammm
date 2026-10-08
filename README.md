# cyber_jammm

# Sentinel-X : partie IA

Cette partie gère **deux IA** qui surveillent le site et lèvent des alertes :

| IA | Elle surveille | Elle détecte | Statut |
|---|---|---|---|
| **Vision** | La webcam USB branchée sur le laptop serveur | Une **personne** dans l'image (intrusion physique) | ✅ Marche |
| **Anomalies capteurs** | Les mesures de l'ESP32 (température, humidité, gaz) | Une **fuite de gaz**, une **surchauffe** ou une **humidité anormale** | ✅ Marche |

Quand une IA détecte quelque chose, elle envoie une **alerte** à l'API (`POST /api/v1/alerts`). Le dashboard l'affiche, et l'ESP32 fait sonner le buzzer.

---

## 1. IA vision : détection d'intrus

**Ce qu'elle fait** : elle lit la webcam, cherche des personnes avec **YOLOv8n** (un modèle de détection d'objets déjà entraîné) et envoie une alerte « intrusion » si une personne est vue sur 3 images d'affilée. Une image isolée ne suffit pas, ce qui évite les fausses alertes.

**Résultats mesurés** :
- **Environ 42 ms par image en moyenne**, et environ 60 ms dans 95 % des cas. Le sujet impose moins de 100 ms ✅
- Pour tenir ce temps, l'image est réduite (images en 640x480, analyse en 416 px).
- Après une alerte, il y a 15 s de pause pour ne pas inonder le dashboard.

**Lancer** :
```
python -m vision.detect --cam 1 --imgsz 416
```
(`--cam 0` pour la webcam intégrée du PC, touche **q** pour quitter)

---

## 2. IA anomalies capteurs : maintenance prédictive

**Ce qu'elle fait** : elle utilise un **Isolation Forest**, un modèle d'apprentissage automatique. On lui montre **uniquement du fonctionnement normal**, et il apprend à quoi ça ressemble. Ensuite, tout ce qui ne ressemble pas au normal est signalé.
→ **Il n'y a aucun seuil écrit à la main** du type `if temp > 40`, comme l'exige le sujet.

**Ce qu'elle regarde** : sur les 30 dernières secondes, la valeur de chaque capteur, **de combien elle a varié** et à quel point le gaz est instable. Une montée brutale est donc repérée même si la valeur reste « raisonnable ».

**Règle anti-fausses alertes** : il faut 3 mesures anormales d'affilée (6 s) pour lever une alerte. Ensuite, le type d'alerte est déduit (gaz, surchauffe ou humidité).

**Données utilisées** :
1. **De vraies mesures de notre ESP32** : 7 min une fois nettoyées. C'est trop peu pour entraîner un modèle seul.
2. Des **données synthétiques calibrées sur ces vraies mesures** : mêmes niveaux, même bruit, même comportement du DHT22. Elles servent à entraîner le modèle et à le tester sur des pannes simulées.
3. Une vérification finale sur les **vraies mesures** : le modèle ne doit pas sonner pour rien dessus.

**Résultats** (sur 1 h de test avec 8 anomalies simulées) :
- Fuite de gaz : 2/2 · Humidité : 2/2 · Surchauffe : 1/2
- **0 fausse alerte** en 1 h de test, et **4,7 s** en moyenne pour détecter
- Sur les vraies mesures : une seule fausse alerte, placée à un « trou » laissé par le nettoyage du fichier.

**Validation sur des données industrielles réelles** : la même méthode, testée sur le benchmark public **NAB** (température d'une machine industrielle avec 4 vraies pannes documentées), détecte les pannes de la période de test avec environ 0,5 fausse alerte par jour.

**Lancer** :
```
python -m anomaly.prepare_serial mesures.txt          # nettoie l'enregistrement de l'ESP32
python -m anomaly.simulate calib                       # crée les données calibrées
python -m anomaly.train --train anomaly/data/calib_train.csv --test anomaly/data/calib_test.csv --real anomaly/data/train.csv
python -m anomaly.detect_live                          # surveillance en direct (MQTT)
```
Le modèle (`anomaly/models/isoforest.joblib`) n'est pas sur GitHub : il pèse 47 Mo et se recrée en 30 s avec les commandes ci-dessus.

---

## Ce dont j'ai besoin de vous

**ESP32 (électronique / DEV)** : publier toutes les **2 secondes** sur le topic MQTT `sentinel/G1/sensors` :
```json
{"device_id": "SX-001", "ts": 1728201302, "temp": 25.5, "hum": 58.1, "gas": 351, "pir": 0}
```
- Encore à corriger : **le PIR vaut toujours 1**, et l'ESP32 imprime parfois la même ligne en boucle.
- Il faut aussi **un enregistrement de 30 à 60 min sans toucher aux capteurs** pour réentraîner le modèle sur du vrai.

**API (DEV)** : la route `POST /api/v1/alerts` doit accepter ce JSON :
```json
{"device_id": "SX-001", "ts": 1728201302, "source": "anomaly", "type": "gas_leak",
 "level": "critical", "value": -0.054, "details": {"temp": 21.5, "hum": 48.6, "gas": 863}}
```
- `source` : `vision` ou `anomaly`
- `type` : `intrusion`, `gas_leak`, `overheat`, `temperature` ou `humidity`
- `level` : `warning` ou `critical`

**Réseau (INFRA)** : l'**adresse IP du laptop serveur** (Mosquitto) et l'**URL de l'API**, à mettre dans le fichier `.env`.

**Pour tester sans ESP32** : le simulateur publie de fausses mesures sur MQTT, avec des anomalies. C'est pratique pour tester l'API et le dashboard :
```
python -m anomaly.simulate mqtt --anomalies
```

---

## Installation (une seule fois)
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```
Ensuite, remplir `.env` : `MQTT_HOST` (IP du serveur) et `API_URL` (adresse de l'API).

## Organisation des fichiers
```
vision/detect.py           IA vision (webcam + YOLO + alertes)
anomaly/simulate.py        faux capteur (CSV ou MQTT)
anomaly/prepare_serial.py  nettoyage des enregistrements de l'ESP32
anomaly/train.py           entraînement + évaluation + graphique
anomaly/detect_live.py     surveillance en direct sur MQTT
anomaly/benchmark_nab.py   validation sur le jeu industriel NAB
common/                    configuration, connexion MQTT, envoi des alertes
anomaly/reports/           graphiques et chiffres pour le dossier
```

## Limites connues
- Le modèle capteurs repère bien les changements **brusques**, moins bien les dérives **très lentes**.
- Il est entraîné en grande partie sur des données synthétiques (calibrées sur nos capteurs). Il sera réentraîné sur un long enregistrement réel dès qu'on l'aura.