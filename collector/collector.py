import json
from datetime import datetime

import paho.mqtt.client as mqtt
from pymongo import MongoClient

mongo = MongoClient("mongodb://mongodb:27017")

db = mongo["cyberjam"]
logs = db["logs"]

def on_connect(client, userdata, flags, rc, properties=None):
    print("Connecté à MQTT")
    client.subscribe("sentinelx/telemetry")

def on_message(client, userdata, msg):

    try:
        payload = json.loads(msg.payload.decode())

        document = {
            "topic": msg.topic,
            "timestamp": datetime.utcnow(),
            **payload
        }

        logs.insert_one(document)

        print("Sauvé :", payload)

    except Exception as e:
        print("Erreur :", e)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set("collector", "CyberJam_256")
client.on_connect = on_connect
client.on_message = on_message

client.connect("mosquitto", 1883, 60)

client.loop_forever()
