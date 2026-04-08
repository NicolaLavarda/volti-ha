"""
camera_manager.py - Gestione telecamere e loop di analisi.
Coordina la cattura degli snapshot e l'analisi per ogni telecamera configurata.
Si ispira al loop principale di codeproject_analyzer_loop_nuovo.py (righe 500-525).
"""

import time
import logging
import threading
import requests
from datetime import datetime

from engine import AnalysisEngine, AnalysisResult
from mqtt_manager import MQTTManager
from ha_api import get_camera_snapshot, get_url_snapshot
from config_store import load_cameras, set_camera_enabled, get_camera

logger = logging.getLogger("volti_ha.cameras")


class CameraWorker:
    """Un worker thread per una singola telecamera."""

    def __init__(
        self,
        camera_config: dict,
        engine: AnalysisEngine,
        mqtt: MQTTManager,
    ):
        self.config = camera_config
        self.engine = engine
        self.mqtt = mqtt
        self.running = False
        self.thread: threading.Thread | None = None
        self.last_result: AnalysisResult | None = None
        self.last_snapshot: bytes | None = None
        self.last_error: str | None = None
        self.frames_analyzed = 0
        self._stop_event = threading.Event()
        self.session: requests.Session | None = None

    @property
    def camera_id(self) -> str:
        return self.config["id"]

    @property
    def camera_name(self) -> str:
        return self.config["name"]

    def start(self):
        """Avvia il loop di analisi."""
        if self.running:
            logger.warning("Camera '%s' è già in esecuzione.", self.camera_name)
            return

        self.running = True
        self._stop_event.clear()
        
        # Inizializza la sessione come in codeproject_analyzer_loop_nuovo.py
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(max_retries=3)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

        self.thread = threading.Thread(
            target=self._analysis_loop,
            name=f"cam_{self.camera_id}",
            daemon=True,
        )
        self.thread.start()
        logger.info("Loop analisi avviato per '%s'.", self.camera_name)

    def stop(self):
        """Ferma il loop di analisi."""
        self.running = False
        self._stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=10)
        logger.info("Loop analisi fermato per '%s'.", self.camera_name)

    def _get_snapshot(self) -> bytes | None:
        """
        Ottiene uno snapshot dalla telecamera.
        Come download_direct_camera_snapshot() nell'originale (righe 203-213).
        """
        try:
            source_type = self.config.get("source_type", "url")
            source = self.config.get("source", "")

            if source_type == "ha_entity":
                return get_camera_snapshot(source, session=self.session)
            else:
                return get_url_snapshot(source, session=self.session)

        except Exception as e:
            self.last_error = str(e)
            logger.error("Errore snapshot per '%s': %s", self.camera_name, e)
            return None

    def _analysis_loop(self):
        """
        Loop principale di analisi. Si ispira al while True
        del codeproject_analyzer_loop_nuovo.py (righe 500-521).
        """
        interval = self.config.get("interval", 2)
        modes = self.config.get("analysis_modes", ["faces"])

        logger.info(
            "Camera '%s' - Inizio loop (intervallo=%ds, modalità=%s)",
            self.camera_name, interval, modes,
        )

        while self.running and not self._stop_event.is_set():
            start_time = time.time()
            try:
                # 1. Cattura snapshot
                snapshot = self._get_snapshot()
                if not snapshot:
                    logger.debug("Nessuno snapshot da '%s', attendo...", self.camera_name)
                    self._stop_event.wait(timeout=interval)
                    continue

                self.last_snapshot = snapshot

                # 2. Analizza l'immagine
                result = self.engine.analyze(snapshot, modes=modes)
                self.last_result = result
                self.frames_analyzed += 1
                self.last_error = None

                # 3. Salva i volti ritagliati per ri-addestramento
                for face in result.faces:
                    self.engine.save_cropped_face(snapshot, face)

                # 4. Pubblica risultati via MQTT
                self.mqtt.publish_results(self.camera_id, result)

                # Log dei risultati
                if result.faces:
                    face_summary = ", ".join(
                        f"{f.name}({int(f.confidence*100)}%)"
                        for f in result.faces
                    )
                    logger.info(
                        "Camera '%s' frame #%d: %s",
                        self.camera_name, self.frames_analyzed, face_summary,
                    )
                else:
                    logger.debug(
                        "Camera '%s' frame #%d: nessun volto.",
                        self.camera_name, self.frames_analyzed,
                    )

            except Exception as e:
                self.last_error = str(e)
                logger.error(
                    "Errore nel loop di '%s': %s", self.camera_name, e
                )

            # Calcola il tempo di analisi e determina l'attesa
            elapsed = time.time() - start_time
            # Se interval è 0, wait_time sarà 0.03 (delay minimo di sicurezza di 30ms)
            wait_time = max(0.03, interval - elapsed)
            
            logger.debug("Camera '%s' - Tempo analisi: %.2fs, Attesa: %.2fs", self.camera_name, elapsed, wait_time)
            self._stop_event.wait(timeout=wait_time)

        if self.session:
            self.session.close()
            self.session = None
            
        logger.info("Loop terminato per '%s'.", self.camera_name)

    def get_status(self) -> dict:
        """Restituisce lo stato corrente del worker."""
        return {
            "id": self.camera_id,
            "name": self.camera_name,
            "running": self.running,
            "frames_analyzed": self.frames_analyzed,
            "last_error": self.last_error,
            "last_result": self.last_result.to_dict() if self.last_result else None,
            "config": self.config,
        }


class CameraManager:
    """
    Gestisce tutti i CameraWorker e coordina accensione/spegnimento
    delle telecamere in risposta ai comandi dell'utente o di HA via MQTT.
    """

    def __init__(self, engine: AnalysisEngine, mqtt: MQTTManager):
        self.engine = engine
        self.mqtt = mqtt
        self.workers: dict[str, CameraWorker] = {}
        self._lock = threading.Lock()

        # Registra il callback per i comandi switch da HA
        self.mqtt.set_switch_callback(self._handle_switch_command)

    def initialize(self):
        """
        Carica le telecamere dalla configurazione e registra le entità MQTT.
        Avvia automaticamente le telecamere che erano abilitate.
        """
        cameras = load_cameras()
        logger.info("Inizializzazione: %d telecamere configurate.", len(cameras))

        for cam_config in cameras:
            camera_id = cam_config["id"]
            camera_name = cam_config["name"]

            # Registra le entità MQTT per questa telecamera
            self.mqtt.register_camera_entities(camera_id, camera_name)

            # Crea il worker
            worker = CameraWorker(cam_config, self.engine, self.mqtt)
            self.workers[camera_id] = worker

            # Se la telecamera era abilitata, avviala
            if cam_config.get("enabled", False):
                worker.start()
                self.mqtt.publish_switch_state(camera_id, True)
            else:
                self.mqtt.publish_switch_state(camera_id, False)

    def add_camera(self, camera_config: dict):
        """Aggiunge e registra una nuova telecamera."""
        camera_id = camera_config["id"]
        camera_name = camera_config["name"]

        with self._lock:
            # Registra entità MQTT
            self.mqtt.register_camera_entities(camera_id, camera_name)

            # Crea worker
            worker = CameraWorker(camera_config, self.engine, self.mqtt)
            self.workers[camera_id] = worker

            # Pubblica stato switch OFF
            self.mqtt.publish_switch_state(camera_id, False)

        logger.info("Telecamera '%s' aggiunta e registrata.", camera_name)

    def remove_camera(self, camera_id: str):
        """Rimuove una telecamera e le sue entità MQTT."""
        with self._lock:
            if camera_id in self.workers:
                self.workers[camera_id].stop()
                del self.workers[camera_id]

            self.mqtt.unregister_camera_entities(camera_id)

        logger.info("Telecamera '%s' rimossa.", camera_id)

    def toggle_camera(self, camera_id: str, enabled: bool):
        """Accende o spegne l'analisi per una telecamera."""
        with self._lock:
            if camera_id not in self.workers:
                # Tenta di ricaricare dalla configurazione
                cam_config = get_camera(camera_id)
                if cam_config:
                    worker = CameraWorker(cam_config, self.engine, self.mqtt)
                    self.workers[camera_id] = worker
                else:
                    logger.error("Telecamera '%s' non trovata.", camera_id)
                    return

            worker = self.workers[camera_id]

            if enabled and not worker.running:
                worker.start()
                set_camera_enabled(camera_id, True)
                self.mqtt.publish_switch_state(camera_id, True)
                logger.info("Telecamera '%s' ACCESA.", camera_id)
            elif not enabled and worker.running:
                worker.stop()
                set_camera_enabled(camera_id, False)
                self.mqtt.publish_switch_state(camera_id, False)
                logger.info("Telecamera '%s' SPENTA.", camera_id)

    def _handle_switch_command(self, camera_id: str, state: bool):
        """Callback invocato da MQTT quando HA invia un comando switch."""
        logger.info("Comando switch da HA: %s -> %s", camera_id, "ON" if state else "OFF")
        self.toggle_camera(camera_id, state)

    def update_camera(self, camera_id: str, new_config: dict):
        """Aggiorna la configurazione di una telecamera e riavvia il worker se necessario."""
        with self._lock:
            if camera_id not in self.workers:
                return

            worker = self.workers[camera_id]
            was_running = worker.running
            
            if was_running:
                logger.info("Riavvio worker '%s' per aggiornamento configurazione...", camera_id)
                worker.stop()
            
            # Crea un nuovo worker con la nuova configurazione
            new_worker = CameraWorker(new_config, self.engine, self.mqtt)
            self.workers[camera_id] = new_worker
            
            if was_running:
                new_worker.start()

    def get_all_status(self) -> list:
        """Restituisce lo stato di tutte le telecamere."""
        statuses = []
        # Include anche le telecamere configurate ma senza worker attivo
        cameras = load_cameras()
        active_ids = set(self.workers.keys())

        for cam in cameras:
            cam_id = cam["id"]
            if cam_id in self.workers:
                statuses.append(self.workers[cam_id].get_status())
            else:
                statuses.append({
                    "id": cam_id,
                    "name": cam["name"],
                    "running": False,
                    "frames_analyzed": 0,
                    "last_error": None,
                    "last_result": None,
                    "config": cam,
                })

        return statuses

    def shutdown(self):
        """Ferma tutti i worker."""
        logger.info("Spegnimento di tutte le telecamere...")
        for worker in self.workers.values():
            worker.stop()
        self.workers.clear()
