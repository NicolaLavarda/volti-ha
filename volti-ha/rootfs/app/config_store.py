"""
config_store.py - Persistenza della configurazione telecamere e stato.
Salva e carica la configurazione da /data/config/cameras.json
"""

import json
import os
import logging
import uuid

logger = logging.getLogger("volti_ha.config")

CONFIG_DIR = "/data/config"
CAMERAS_FILE = os.path.join(CONFIG_DIR, "cameras.json")


def _ensure_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)


def load_cameras() -> list:
    """Carica la lista delle telecamere configurate."""
    _ensure_dir()
    if not os.path.exists(CAMERAS_FILE):
        return []
    try:
        with open(CAMERAS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("cameras", [])
    except Exception as e:
        logger.error("Errore nel caricamento della configurazione telecamere: %s", e)
        return []


def save_cameras(cameras: list):
    """Salva la lista delle telecamere configurate."""
    _ensure_dir()
    try:
        with open(CAMERAS_FILE, "w", encoding="utf-8") as f:
            json.dump({"cameras": cameras}, f, indent=2, ensure_ascii=False)
        logger.info("Configurazione telecamere salvata (%d telecamere).", len(cameras))
    except Exception as e:
        logger.error("Errore nel salvataggio della configurazione telecamere: %s", e)


def add_camera(name: str, source_type: str, source: str, interval: int = 2) -> dict:
    """
    Aggiunge una telecamera alla configurazione.
    
    Args:
        name: Nome visualizzato della telecamera
        source_type: 'ha_entity' o 'url'
        source: entity_id HA (es. 'camera.carraio') o URL snapshot diretto
        interval: Intervallo in secondi tra analisi
    
    Returns:
        dict con i dati della telecamera creata
    """
    cameras = load_cameras()

    # Genera un ID sicuro dal nome
    camera_id = name.lower().replace(" ", "_").replace("'", "")
    # Assicuriamoci che sia unico
    existing_ids = {c["id"] for c in cameras}
    if camera_id in existing_ids:
        camera_id = f"{camera_id}_{uuid.uuid4().hex[:4]}"

    camera = {
        "id": camera_id,
        "name": name,
        "source_type": source_type,  # 'ha_entity' o 'url'
        "source": source,
        "interval": interval,
        "enabled": False,
        "analysis_modes": ["faces"],  # Predisposto per ["faces", "plates"] in futuro
    }

    cameras.append(camera)
    save_cameras(cameras)
    logger.info("Telecamera aggiunta: %s (id=%s, source=%s)", name, camera_id, source)
    return camera


def remove_camera(camera_id: str) -> bool:
    """Rimuove una telecamera dalla configurazione."""
    cameras = load_cameras()
    original_len = len(cameras)
    cameras = [c for c in cameras if c["id"] != camera_id]

    if len(cameras) == original_len:
        logger.warning("Telecamera con id '%s' non trovata.", camera_id)
        return False

    save_cameras(cameras)
    logger.info("Telecamera rimossa: %s", camera_id)
    return True


def update_camera(camera_id: str, updates: dict) -> bool:
    """Aggiorna i campi di una telecamera esistente."""
    cameras = load_cameras()
    for cam in cameras:
        if cam["id"] == camera_id:
            cam.update(updates)
            save_cameras(cameras)
            logger.info("Telecamera aggiornata: %s -> %s", camera_id, updates)
            return True
    logger.warning("Telecamera con id '%s' non trovata per aggiornamento.", camera_id)
    return False


def get_camera(camera_id: str) -> dict | None:
    """Restituisce una telecamera per ID."""
    cameras = load_cameras()
    for cam in cameras:
        if cam["id"] == camera_id:
            return cam
    return None


def set_camera_enabled(camera_id: str, enabled: bool) -> bool:
    """Abilita o disabilita una telecamera."""
    return update_camera(camera_id, {"enabled": enabled})
