from datetime import datetime, UTC
import os
import psutil

from fastapi import FastAPI, Header, HTTPException, Depends
from pymongo import MongoClient

app = FastAPI()

API_KEY = os.getenv("API_KEY")

mongo = MongoClient("mongodb://mongodb:27017")
db = mongo.cyberjam


def verify_api_key(x_api_key: str = Header(...)):
    if not API_KEY or x_api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="API Key invalide"
        )

    return x_api_key


@app.get("/")
def root():
    return {"message": "API OK"}


# ==========================
# MONITORING / MCO
# ==========================

@app.get("/system/status")
def system_status(api_key: str = Depends(verify_api_key)):
    return {
        "cpu": round(psutil.cpu_percent(interval=1), 1),
        "ram": round(psutil.virtual_memory().percent, 1),
        "disk": round(psutil.disk_usage("/").percent, 1)
    }


@app.get("/system/health")
def system_health(api_key: str = Depends(verify_api_key)):
    return {
        "api": "OK",
        "mongodb": "OK",
        "mqtt": "OK"
    }


# ==========================
# TEST MONGODB
# ==========================

@app.get("/testdb")
def testdb(api_key: str = Depends(verify_api_key)):
    db.logs.insert_one(
        {
            "message": "test mongodb",
            "timestamp": datetime.now(UTC)
        }
    )

    return {"status": "document ajoute"}


# ==========================
# TELEMETRIE
# ==========================

@app.get("/telemetry/latest")
def telemetry_latest(api_key: str = Depends(verify_api_key)):
    doc = db.logs.find_one(
        {"device": "sentinel-x"},
        sort=[("_id", -1)]
    )

    if doc is None:
        return
    doc["_id"] = str(doc["_id"])
    return doc

@app.get("/telemetry/history")
def telemetry_history(
    limit: int = 20,
    api_key: str = Depends(verify_api_key)
    ):
    limit = min(max(limit, 1), 100)

    docs = list(
        db.logs.find(
            {"device": "sentinel-x"},
            {
                "_id": 0,
                "timestamp": 1,
                "temp": 1,
                "hum": 1,
                "gaz": 1,
                "mouvement": 1,
                "etat": 1,
            }
        )
        .sort("_id", -1)
        .limit(limit)
    )

    docs.reverse()

    return docs

@app.post("/analysis")
def create_alert(
    data: dict,
    api_key: str = Depends(verify_api_key)
):
    document = {
        "timestamp": datetime.now(UTC),
        "risk": data.get("risk"),
        "score": data.get("score"),
        "msg": data.get("msg")
    }

    result = db.alerts.insert_one(document)

    return {
        "status": "ok",
        "id": str(result.inserted_id)
    }
