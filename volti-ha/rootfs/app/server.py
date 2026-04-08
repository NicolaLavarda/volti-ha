"""
server.py - Server Flask principale per l'interfaccia web Ingress.
Espone l'API REST per la gestione delle telecamere e del modello,
e serve l'interfaccia web HTML.
"""

import os
import sys
import json
import signal
import logging
import base64
from datetime import datetime

from flask import Flask, render_template, request, jsonify, send_from_directory

from engine import AnalysisEngine
from mqtt_manager import MQTTManager
from camera_manager import CameraManager
from ha_api import get_available_cameras as ha_get_cameras
import config_store

# --- Configurazione da variabili d'ambiente (impostate da run.sh) ---
MQTT_HOST = os.environ.get("VOLTI_MQTT_HOST", "core-mosquitto")
MQTT_PORT = int(os.environ.get("VOLTI_MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("VOLTI_MQTT_USER", "")
MQTT_PASSWORD = os.environ.get("VOLTI_MQTT_PASSWORD", "")
SCAN_INTERVAL = int(os.environ.get("VOLTI_SCAN_INTERVAL", "2"))
MIN_CONFIDENCE = float(os.environ.get("VOLTI_MIN_CONFIDENCE", "0.7"))
DETECTION_MODEL = os.environ.get("VOLTI_DETECTION_MODEL", "hog")
LOG_LEVEL = os.environ.get("VOLTI_LOG_LEVEL", "info").upper()

# --- Logging ---
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("volti_ha.server")

# --- Ring buffer per log recenti (visibili nell'UI) ---
class LogBuffer(logging.Handler):
    def __init__(self, max_lines=200):
        super().__init__()
        self.buffer = []
        self.max_lines = max_lines

    def emit(self, record):
        msg = self.format(record)
        self.buffer.append(msg)
        if len(self.buffer) > self.max_lines:
            self.buffer = self.buffer[-self.max_lines:]

    def get_logs(self):
        return list(self.buffer)

log_buffer = LogBuffer()
log_buffer.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
logging.getLogger().addHandler(log_buffer)

# --- Inizializzazione componenti ---
logger.info("=" * 50)
logger.info("Volti HA - Server in avvio...")
logger.info("=" * 50)

# Motore di analisi
engine = AnalysisEngine(
    detection_model=DETECTION_MODEL,
    min_confidence=MIN_CONFIDENCE,
)

# MQTT
mqtt_manager = MQTTManager(
    host=MQTT_HOST,
    port=MQTT_PORT,
    user=MQTT_USER,
    password=MQTT_PASSWORD,
)
mqtt_connected = mqtt_manager.connect()
if mqtt_connected:
    logger.info("MQTT connesso con successo.")
else:
    logger.warning("MQTT non connesso. Le entità HA non saranno disponibili.")

# Camera Manager
camera_manager = CameraManager(engine=engine, mqtt=mqtt_manager)
camera_manager.initialize()

# --- Flask App ---
app = Flask(
    __name__,
    template_folder="/app/templates",
    static_folder="/app/static",
)


def _get_ingress_path():
    """Ottieni il path base Ingress dall'header HA."""
    return request.headers.get("X-Ingress-Path", "")


# ============================
# PAGINA PRINCIPALE
# ============================

@app.route("/")
def index():
    ingress_path = _get_ingress_path()
    return render_template("index.html", ingress_path=ingress_path)


# ============================
# API - TELECAMERE
# ============================

@app.route("/api/cameras", methods=["GET"])
def api_get_cameras():
    """Restituisce la lista di telecamere configurate con il loro stato."""
    statuses = camera_manager.get_all_status()
    return jsonify({"cameras": statuses})


@app.route("/api/cameras", methods=["POST"])
def api_add_camera():
    """Aggiunge una nuova telecamera."""
    data = request.json
    name = data.get("name", "").strip()
    source_type = data.get("source_type", "url")
    source = data.get("source", "").strip()
    interval = data.get("interval", SCAN_INTERVAL)

    if not name or not source:
        return jsonify({"error": "Nome e sorgente sono obbligatori."}), 400

    # Salva nella configurazione persistente
    cam = config_store.add_camera(name, source_type, source, interval)

    # Registra nel camera manager (crea worker + entità MQTT)
    camera_manager.add_camera(cam)

    return jsonify({"camera": cam, "message": f"Telecamera '{name}' aggiunta con successo."})


@app.route("/api/cameras/<camera_id>", methods=["DELETE"])
def api_delete_camera(camera_id):
    """Rimuove una telecamera."""
    camera_manager.remove_camera(camera_id)
    config_store.remove_camera(camera_id)
    return jsonify({"message": f"Telecamera '{camera_id}' rimossa."})


@app.route("/api/cameras/<camera_id>", methods=["PUT"])
def api_update_camera(camera_id):
    """Aggiorna la configurazione di una telecamera."""
    data = request.json
    
    # Recupera configurazione attuale
    cam = config_store.get_camera(camera_id)
    if not cam:
        return jsonify({"error": "Telecamera non trovata."}), 404

    # Aggiorna campi
    updates = {}
    if "name" in data: updates["name"] = data["name"].strip()
    if "source_type" in data: updates["source_type"] = data["source_type"]
    if "source" in data: updates["source"] = data["source"].strip()
    if "interval" in data: updates["interval"] = int(data["interval"])
    
    if "analysis_modes" in data: updates["analysis_modes"] = data["analysis_modes"]

    # Salva in config_store
    config_store.update_camera(camera_id, updates)
    
    # Ricarica la configurazione completa
    new_cam_config = config_store.get_camera(camera_id)
    
    # Aggiorna nel camera manager
    camera_manager.update_camera(camera_id, new_cam_config)
    
    return jsonify({"camera": new_cam_config, "message": "Configurazione aggiornata."})


@app.route("/api/cameras/<camera_id>/toggle", methods=["PUT"])
def api_toggle_camera(camera_id):
    """Accende/spegne l'analisi per una telecamera."""
    data = request.json
    enabled = data.get("enabled", False)
    camera_manager.toggle_camera(camera_id, enabled)
    return jsonify({"camera_id": camera_id, "enabled": enabled})


# ============================
# API - TELECAMERE HA DISPONIBILI
# ============================

@app.route("/api/ha-cameras", methods=["GET"])
def api_ha_cameras():
    """Restituisce le entità telecamera disponibili in HA."""
    cameras = ha_get_cameras()
    return jsonify({"cameras": cameras})


# ============================
# API - MODELLO
# ============================

@app.route("/api/model/upload", methods=["POST"])
def api_upload_model():
    """Upload del file .pkl del classificatore."""
    if "model" not in request.files:
        return jsonify({"error": "Nessun file caricato."}), 400

    file = request.files["model"]
    if not file.filename.endswith(".pkl"):
        return jsonify({"error": "Il file deve essere un .pkl"}), 400

    file_data = file.read()
    success = engine.save_uploaded_model(file_data)

    if success:
        return jsonify({
            "message": "Modello caricato con successo!",
            "info": engine.get_model_info(),
        })
    else:
        return jsonify({"error": "Errore nel caricamento del modello."}), 500


@app.route("/api/model/info", methods=["GET"])
def api_model_info():
    """Info sul modello caricato."""
    return jsonify(engine.get_model_info())


# ============================
# API - STATO E LOG
# ============================

@app.route("/api/status", methods=["GET"])
def api_status():
    """Stato generale del sistema."""
    cameras = camera_manager.get_all_status()
    active = sum(1 for c in cameras if c["running"])
    return jsonify({
        "mqtt_connected": mqtt_manager.connected,
        "model_loaded": engine.model_loaded,
        "total_cameras": len(cameras),
        "active_cameras": active,
        "model_info": engine.get_model_info(),
    })


@app.route("/api/logs", methods=["GET"])
def api_logs():
    """Restituisce gli ultimi log."""
    return jsonify({"logs": log_buffer.get_logs()})


# ============================
# SHUTDOWN PULITO
# ============================

def shutdown_handler(signum, frame):
    logger.info("Segnale di terminazione ricevuto. Spegnimento...")
    camera_manager.shutdown()
    mqtt_manager.disconnect()
    sys.exit(0)


signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)


# ============================
# AVVIO
# ============================

if __name__ == "__main__":
    logger.info("Server Flask in ascolto su porta 8099...")
    app.run(
        host="0.0.0.0",
        port=8099,
        debug=False,
        use_reloader=False,
    )
