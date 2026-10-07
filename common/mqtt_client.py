"""Connexion à Mosquitto (TLS activé automatiquement si MQTT_CA est renseigné)."""
import sys

import paho.mqtt.client as mqtt

from . import config


def make_client(client_id):
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    if config.MQTT_USER:
        client.username_pw_set(config.MQTT_USER, config.MQTT_PASS)
    if config.MQTT_CA:
        client.tls_set(ca_certs=config.MQTT_CA)
    try:
        client.connect(config.MQTT_HOST, config.MQTT_PORT, keepalive=30)
    except OSError as e:
        sys.exit(f"Mosquitto injoignable sur {config.MQTT_HOST}:{config.MQTT_PORT} ({e}). "
                 "Vérifie que le conteneur tourne et l'IP dans .env")
    return client
