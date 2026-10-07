"""Configuration commune aux scripts IA (lue depuis ai/.env, jamais commité)."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

GROUP = os.getenv("GROUP", "G1")
DEVICE_ID = os.getenv("DEVICE_ID", "SX-001")

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER") or None
MQTT_PASS = os.getenv("MQTT_PASS") or None
MQTT_CA = os.getenv("MQTT_CA") or None

TOPIC_SENSORS = f"sentinel/{GROUP}/sensors"

API_URL = os.getenv("API_URL") or None
API_CA = os.getenv("API_CA") or None
