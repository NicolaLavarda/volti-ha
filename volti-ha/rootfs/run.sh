#!/usr/bin/with-contenv bashio

bashio::log.info "======================================"
bashio::log.info " Volti HA - Face Recognition Add-on"
bashio::log.info " Versione 1.0.2"
bashio::log.info "======================================"

# Crea directory persistenti
mkdir -p /data/models
mkdir -p /data/snapshots
mkdir -p /data/config
mkdir -p /data/cropped_faces

bashio::log.info "Directory dati verificate."

# Esporta la configurazione come variabili d'ambiente per Python
export VOLTI_MQTT_HOST="$(bashio::config 'mqtt_host')"
export VOLTI_MQTT_PORT="$(bashio::config 'mqtt_port')"
export VOLTI_MQTT_USER="$(bashio::config 'mqtt_user')"
export VOLTI_MQTT_PASSWORD="$(bashio::config 'mqtt_password')"
export VOLTI_SCAN_INTERVAL="$(bashio::config 'scan_interval_seconds')"
export VOLTI_MIN_CONFIDENCE="$(bashio::config 'min_confidence')"
export VOLTI_DETECTION_MODEL="$(bashio::config 'face_detection_model')"
export VOLTI_LOG_LEVEL="$(bashio::config 'log_level')"

bashio::log.info "Configurazione caricata."
bashio::log.info "MQTT Host: ${VOLTI_MQTT_HOST}:${VOLTI_MQTT_PORT}"
bashio::log.info "Modello Detection: ${VOLTI_DETECTION_MODEL}"
bashio::log.info "Intervallo Scansione: ${VOLTI_SCAN_INTERVAL}s"
bashio::log.info "Confidenza Minima: ${VOLTI_MIN_CONFIDENCE}"

bashio::log.info "Avvio server web..."

# Avvia il server Flask
exec python3 /app/server.py
