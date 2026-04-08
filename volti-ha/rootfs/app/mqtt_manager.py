"""
mqtt_manager.py - Gestione MQTT e Auto-Discovery per Home Assistant.
Pubblica i risultati dell'analisi come entità HA native via MQTT.
Gestisce anche i comandi switch (on/off) ricevuti da HA.
"""

import json
import time
import logging
import threading

import paho.mqtt.client as mqtt

logger = logging.getLogger("volti_ha.mqtt")

DISCOVERY_PREFIX = "homeassistant"
DEVICE_MANUFACTURER = "Volti HA"
DEVICE_MODEL = "Face Recognition Add-on"
NODE_ID = "volti_ha"


class MQTTManager:
    """
    Gestisce la connessione MQTT, la pubblicazione dei risultati
    e la creazione automatica delle entità via MQTT Auto-Discovery.
    """

    def __init__(self, host: str, port: int, user: str = "", password: str = ""):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.client: mqtt.Client | None = None
        self.connected = False
        self._on_switch_callback = None  # Callback quando un switch viene premuto
        self._lock = threading.Lock()

    def set_switch_callback(self, callback):
        """
        Registra un callback per quando HA invia un comando switch.
        Il callback riceve (camera_id: str, state: bool).
        """
        self._on_switch_callback = callback

    def connect(self) -> bool:
        """Connessione al broker MQTT."""
        try:
            self.client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2,
                client_id=f"volti_ha_{int(time.time())}",
            )

            if self.user:
                self.client.username_pw_set(self.user, self.password)

            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message

            self.client.will_set(
                f"{NODE_ID}/status", payload="offline", qos=1, retain=True
            )

            logger.info("Connessione a MQTT %s:%d...", self.host, self.port)
            self.client.connect(self.host, self.port, keepalive=60)
            self.client.loop_start()

            # Attendi la connessione (max 10 sec)
            for _ in range(20):
                if self.connected:
                    return True
                time.sleep(0.5)

            logger.error("Timeout connessione MQTT.")
            return False

        except Exception as e:
            logger.error("Errore connessione MQTT: %s", e)
            return False

    def disconnect(self):
        """Disconnessione pulita."""
        if self.client:
            self.client.publish(f"{NODE_ID}/status", "offline", qos=1, retain=True)
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False
            logger.info("Disconnesso da MQTT.")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self.connected = True
            logger.info("Connesso a MQTT con successo!")
            # Pubblica stato online
            client.publish(f"{NODE_ID}/status", "online", qos=1, retain=True)
            # Sottoscrivi ai comandi switch
            client.subscribe(f"{NODE_ID}/+/switch/set")
            logger.info("Sottoscritto a %s/+/switch/set", NODE_ID)
        else:
            logger.error("Connessione MQTT fallita con codice: %s", rc)

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        self.connected = False
        if rc != 0:
            logger.warning("Disconnessione MQTT inattesa (codice=%s). Tentativo di riconnessione...", rc)

    def _on_message(self, client, userdata, msg):
        """Gestisce i comandi ricevuti da HA (es. switch on/off)."""
        try:
            topic = msg.topic
            payload = msg.payload.decode("utf-8").upper()
            logger.debug("Messaggio MQTT ricevuto: %s = %s", topic, payload)

            # Formato atteso: volti_ha/<camera_id>/switch/set
            parts = topic.split("/")
            if len(parts) >= 4 and parts[2] == "switch" and parts[3] == "set":
                camera_id = parts[1]
                state = payload == "ON"
                logger.info("Comando switch per '%s': %s", camera_id, "ON" if state else "OFF")

                if self._on_switch_callback:
                    self._on_switch_callback(camera_id, state)

                # Conferma lo stato
                state_topic = f"{NODE_ID}/{camera_id}/switch/state"
                client.publish(state_topic, "ON" if state else "OFF", qos=1, retain=True)

        except Exception as e:
            logger.error("Errore nella gestione del messaggio MQTT: %s", e)

    def register_camera_entities(self, camera_id: str, camera_name: str):
        """
        Pubblica le configurazioni MQTT Auto-Discovery per creare
        tutte le entità HA di una telecamera.
        """
        if not self.connected:
            logger.error("MQTT non connesso. Impossibile registrare le entità.")
            return

        device_info = {
            "identifiers": [f"{NODE_ID}_{camera_id}"],
            "name": f"Volti HA - {camera_name}",
            "manufacturer": DEVICE_MANUFACTURER,
            "model": DEVICE_MODEL,
            "sw_version": "1.0.0",
        }

        self._register_switch(camera_id, camera_name, device_info)
        self._register_person_sensor(camera_id, camera_name, device_info)
        self._register_face_binary_sensor(camera_id, camera_name, device_info)
        self._register_annotated_camera(camera_id, camera_name, device_info)

        logger.info("Entità MQTT registrate per telecamera '%s'.", camera_name)

    def _register_switch(self, camera_id: str, camera_name: str, device: dict):
        """Switch ON/OFF per avviare/fermare l'analisi."""
        config = {
            "name": f"{camera_name} Analisi",
            "unique_id": f"{NODE_ID}_{camera_id}_switch",
            "command_topic": f"{NODE_ID}/{camera_id}/switch/set",
            "state_topic": f"{NODE_ID}/{camera_id}/switch/state",
            "availability_topic": f"{NODE_ID}/status",
            "icon": "mdi:face-recognition",
            "device": device,
        }
        topic = f"{DISCOVERY_PREFIX}/switch/{NODE_ID}/{camera_id}_analisi/config"
        self.client.publish(topic, json.dumps(config), qos=1, retain=True)

    def _register_person_sensor(self, camera_id: str, camera_name: str, device: dict):
        """Sensore con i nomi delle persone riconosciute."""
        config = {
            "name": f"{camera_name} Persone",
            "unique_id": f"{NODE_ID}_{camera_id}_persone",
            "state_topic": f"{NODE_ID}/{camera_id}/persone/state",
            "json_attributes_topic": f"{NODE_ID}/{camera_id}/persone/attributes",
            "availability_topic": f"{NODE_ID}/status",
            "icon": "mdi:account-group",
            "device": device,
        }
        topic = f"{DISCOVERY_PREFIX}/sensor/{NODE_ID}/{camera_id}_persone/config"
        self.client.publish(topic, json.dumps(config), qos=1, retain=True)

    def _register_face_binary_sensor(self, camera_id: str, camera_name: str, device: dict):
        """Binary sensor: ON se almeno un volto è rilevato."""
        config = {
            "name": f"{camera_name} Volto Rilevato",
            "unique_id": f"{NODE_ID}_{camera_id}_volto",
            "state_topic": f"{NODE_ID}/{camera_id}/volto/state",
            "availability_topic": f"{NODE_ID}/status",
            "device_class": "occupancy",
            "payload_on": "ON",
            "payload_off": "OFF",
            "icon": "mdi:face-agent",
            "device": device,
        }
        topic = f"{DISCOVERY_PREFIX}/binary_sensor/{NODE_ID}/{camera_id}_volto/config"
        self.client.publish(topic, json.dumps(config), qos=1, retain=True)

    def _register_annotated_camera(self, camera_id: str, camera_name: str, device: dict):
        """Camera MQTT per l'immagine annotata con i box."""
        config = {
            "name": f"{camera_name} Annotata",
            "unique_id": f"{NODE_ID}_{camera_id}_annotata",
            "topic": f"{NODE_ID}/{camera_id}/camera/image",
            "availability_topic": f"{NODE_ID}/status",
            "device": device,
        }
        topic = f"{DISCOVERY_PREFIX}/camera/{NODE_ID}/{camera_id}_annotata/config"
        self.client.publish(topic, json.dumps(config), qos=1, retain=True)

    def unregister_camera_entities(self, camera_id: str):
        """Rimuove tutte le entità MQTT di una telecamera (payload vuoto)."""
        if not self.connected:
            return

        topics = [
            f"{DISCOVERY_PREFIX}/switch/{NODE_ID}/{camera_id}_analisi/config",
            f"{DISCOVERY_PREFIX}/sensor/{NODE_ID}/{camera_id}_persone/config",
            f"{DISCOVERY_PREFIX}/binary_sensor/{NODE_ID}/{camera_id}_volto/config",
            f"{DISCOVERY_PREFIX}/camera/{NODE_ID}/{camera_id}_annotata/config",
        ]
        for topic in topics:
            self.client.publish(topic, "", qos=1, retain=True)

        logger.info("Entità MQTT rimosse per telecamera '%s'.", camera_id)

    def publish_results(self, camera_id: str, analysis_result):
        """
        Pubblica i risultati dell'analisi su tutti i topic della telecamera.
        
        Args:
            camera_id: ID della telecamera
            analysis_result: Oggetto AnalysisResult dal motore
        """
        if not self.connected:
            return

        with self._lock:
            faces = analysis_result.faces
            min_conf = 0.0  # Pubblica tutto, è HA che filtra

            # 1. Binary sensor: volto rilevato
            has_face = "ON" if len(faces) > 0 else "OFF"
            self.client.publish(
                f"{NODE_ID}/{camera_id}/volto/state", has_face, qos=1, retain=True
            )

            # 2. Sensore persone
            if faces:
                known = [f for f in faces if f.name != "Sconosciuto"]
                unknown_count = len(faces) - len(known)

                # Ordina per confidenza decrescente
                known.sort(key=lambda f: f.confidence, reverse=True)
                names = [f.name for f in known]
                if unknown_count > 0:
                    names.extend(["Sconosciuto"] * unknown_count)

                state = ", ".join(names) if names else "Nessuno"

                # Attributi dettagliati (utili per le automazioni)
                attributes = {
                    "faces": [f.to_dict() for f in faces],
                    "faces_count": len(faces),
                    "known_count": len(known),
                    "unknown_count": unknown_count,
                    "last_update": analysis_result.timestamp,
                    "max_confidence": max(f.confidence for f in faces) if faces else 0,
                }
            else:
                state = "Nessuno"
                attributes = {
                    "faces": [],
                    "faces_count": 0,
                    "known_count": 0,
                    "unknown_count": 0,
                    "last_update": analysis_result.timestamp,
                    "max_confidence": 0,
                }

            self.client.publish(
                f"{NODE_ID}/{camera_id}/persone/state", state, qos=1, retain=True
            )
            self.client.publish(
                f"{NODE_ID}/{camera_id}/persone/attributes",
                json.dumps(attributes),
                qos=1,
                retain=True,
            )

            # 3. Camera annotata (immagine JPEG binaria)
            if analysis_result.annotated_image:
                self.client.publish(
                    f"{NODE_ID}/{camera_id}/camera/image",
                    analysis_result.annotated_image,
                    qos=0,
                    retain=False,
                )

    def publish_switch_state(self, camera_id: str, enabled: bool):
        """Pubblica lo stato dello switch di una telecamera."""
        if not self.connected:
            return
        self.client.publish(
            f"{NODE_ID}/{camera_id}/switch/state",
            "ON" if enabled else "OFF",
            qos=1,
            retain=True,
        )
