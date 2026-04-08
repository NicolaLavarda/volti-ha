#!/bin/bash

echo "======================================"
echo " Volti HA - Face Recognition Add-on"
echo " Versione 1.0.1"
echo "======================================"

# Crea directory persistenti
mkdir -p /data/models
mkdir -p /data/snapshots
mkdir -p /data/config
mkdir -p /data/cropped_faces

echo "Directory dati verificate."

# Estrai opzioni da /data/options.json (file generato dal Supervisor)
if [ -f /data/options.json ]; then
    export VOLTI_MQTT_HOST=$(python3 -c "import json; print(json.load(open('/data/options.json')).get('mqtt_host', 'core-mosquitto'))")
    export VOLTI_MQTT_PORT=$(python3 -c "import json; print(json.load(open('/data/options.json')).get('mqtt_port', 1883))")
    export VOLTI_MQTT_USER=$(python3 -c "import json; print(json.load(open('/data/options.json')).get('mqtt_user', ''))")
    export VOLTI_MQTT_PASSWORD=$(python3 -c "import json; print(json.load(open('/data/options.json')).get('mqtt_password', ''))")
    export VOLTI_SCAN_INTERVAL=$(python3 -c "import json; print(json.load(open('/data/options.json')).get('scan_interval_seconds', 2))")
    export VOLTI_MIN_CONFIDENCE=$(python3 -c "import json; print(json.load(open('/data/options.json')).get('min_confidence', 0.70))")
    export VOLTI_DETECTION_MODEL=$(python3 -c "import json; print(json.load(open('/data/options.json')).get('face_detection_model', 'hog'))")
    export VOLTI_LOG_LEVEL=$(python3 -c "import json; print(json.load(open('/data/options.json')).get('log_level', 'info'))")
fi

echo "Configurazione caricata."
echo "MQTT Host: ${VOLTI_MQTT_HOST}:${VOLTI_MQTT_PORT}"
echo "Modello Detection: ${VOLTI_DETECTION_MODEL}"
echo "Intervallo Scansione: ${VOLTI_SCAN_INTERVAL}s"
echo "Confidenza Minima: ${VOLTI_MIN_CONFIDENCE}"

echo "Avvio server web..."

# Avvia il server Flask direttamente
exec python3 /app/server.py
