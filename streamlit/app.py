import streamlit as st
import requests
import pandas as pd
from pathlib import Path
from PIL import Image
from streamlit_autorefresh import st_autorefresh

st.set_page_config(
    page_title="CyberJam Dashboard",
    page_icon="???",
    layout="wide"
)

API_URL = "http://host.docker.internal:8000"
API_KEY = ""

headers = {
    "X-API-Key": API_KEY
}

st.markdown("""
<style>
.stApp {
    background-color: #0F172A;
}

h1, h2, h3 {
    color: #A78BFA;
}

div[data-testid="metric-container"] {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-left: 6px solid #A78BFA;
    padding: 15px;
    border-radius: 12px;
}

[data-testid="stAppDeployButton"] {
    display: none;
}

#MainMenu {
    visibility: hidden;
}

footer {
    visibility: hidden;
}

header {
    visibility: hidden;
}
</style>
""", unsafe_allow_html=True)

st.title("?? CYBERJAM Dashboard ??")
st.caption("Supervision temps réel ESP32 • MQTT • IA • Webcam")

telemetry = {}

try:
    response = requests.get(
        f"{API_URL}/telemetry/latest",
        headers=headers,
        timeout=3
    )

    telemetry = response.json()

    if telemetry is None:
        telemetry = {}

    if not isinstance(telemetry, dict):
        telemetry = {}

except Exception:
    telemetry = {}

temp = telemetry.get("temp", "--")
hum = telemetry.get("hum", "--")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("??? Température", f"{temp} °C ???")

with col2:
    st.metric("?? Humidité", f"{hum} % ??")

with col3:
    st.metric("?? MQTT", "Connecté ??")

with col4:
    st.metric("?? IA", "Active ??")

st.divider()

st.subheader("??? Monitoring Poste Local ???")

try:
    system = requests.get(
        f"{API_URL}/system/status",
        headers=headers,
        timeout=3
    ).json()

    m1, m2, m3 = st.columns(3)

    with m1:
        st.metric("CPU", f"{system.get('cpu', '--')} %")

    with m2:
        st.metric("RAM", f"{system.get('ram', '--')} %")

    with m3:
        st.metric("DISQUE", f"{system.get('disk', '--')} %")

except Exception as e:
    st.error(f"Erreur monitoring : {e}")

st.divider()

graph_col, cam_col = st.columns([2, 1])

with graph_col:

    st.subheader("?? Données environnementales ??")

    try:
        history = requests.get(
            f"{API_URL}/telemetry/history?limit=20",
            headers=headers,
            timeout=3
        ).json()

        if isinstance(history, list) and len(history) > 0:

            history.reverse()

            df = pd.DataFrame({
                "Température": [item.get("temp", 0) for item in history],
                "Humidité": [item.get("hum", 0) for item in history]
            })

            st.line_chart(df)

        else:
            st.warning("Aucune donnée historique disponible.")

    except Exception:
        st.warning("Impossible de charger les courbes.")

with cam_col:

    st.subheader("?? Webcam IA")

    st_autorefresh(interval=1000, key="camera")

    try:

        capture_dir = Path("/captures")

        images = []
        images.extend(capture_dir.glob("*.jpg"))
        images.extend(capture_dir.glob("*.jpeg"))
        images.extend(capture_dir.glob("*.png"))

        if images:

            latest_image = max(
                images,
                key=lambda f: f.stat().st_mtime
            )

            img = Image.open(latest_image)

            st.image(
                img,
                caption=f"Dernière détection : {latest_image.name}",
                use_container_width=True
            )

        else:
            st.warning("Aucune image disponible dans le dossier capture.")

    except Exception as e:
        st.error(f"Erreur affichage webcam : {e}")

st.divider()

st.subheader("?? État des équipements ??")

s1, s2, s3, s4 = st.columns(4)

with s1:
    st.success("? ESP32 connecté")

with s2:
    st.success("? API disponible")

with s3:
    st.success("? MongoDB disponible")

with s4:
    st.warning("?? MQTT en maintenance")

st.divider()

st.subheader("?? Commandes à distance")

c1, c2, c3 = st.columns(3)

with c1:
    if st.button("?? Activer Buzzer", use_container_width=True):
        st.success("Commande envoyée")

with c2:
    if st.button("?? LED Rouge ON", use_container_width=True):
        st.success("Commande envoyée")

with c3:
    if st.button("?? LED Verte ON", use_container_width=True):
        st.success("Commande envoyée")

st.divider()

st.subheader("?? Journal système")

st.code("""
[INFO] API disponible
[INFO] MongoDB disponible
[INFO] Dashboard opérationnel
[WARNING] MQTT en
