"""
ha_api.py - Client per la Home Assistant Core API.
Comunica con HA tramite il proxy interno del Supervisor per ottenere
la lista delle telecamere disponibili e catturare snapshot.
"""

import os
import logging
import requests

logger = logging.getLogger("volti_ha.ha_api")

# URL interno del Supervisor per accedere alla Core API
HA_API_BASE = "http://supervisor/core/api"

# Il token viene fornito automaticamente dal Supervisor
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")


def _headers():
    """Headers di autenticazione per le chiamate alla Core API."""
    return {
        "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
        "Content-Type": "application/json",
    }


def get_available_cameras() -> list:
    """
    Recupera la lista di tutte le entità telecamera disponibili in HA.
    
    Returns:
        Lista di dict con 'entity_id', 'friendly_name' e 'state' per ogni telecamera.
    """
    try:
        response = requests.get(f"{HA_API_BASE}/states", headers=_headers(), timeout=10)
        response.raise_for_status()
        all_states = response.json()

        cameras = []
        for entity in all_states:
            entity_id = entity.get("entity_id", "")
            if entity_id.startswith("camera."):
                cameras.append({
                    "entity_id": entity_id,
                    "friendly_name": entity.get("attributes", {}).get("friendly_name", entity_id),
                    "state": entity.get("state", "unknown"),
                })

        logger.info("Trovate %d telecamere HA disponibili.", len(cameras))
        return cameras

    except requests.exceptions.ConnectionError:
        logger.error("Impossibile connettersi alla Core API di HA. Verifica homeassistant_api: true nel config.yaml.")
        return []
    except Exception as e:
        logger.error("Errore nel recupero delle telecamere HA: %s", e)
        return []


def get_camera_snapshot(entity_id: str) -> bytes | None:
    """
    Ottiene uno snapshot JPEG dalla telecamera tramite la Core API.
    
    Args:
        entity_id: L'entity_id della telecamera (es. 'camera.carraio')
    
    Returns:
        Bytes dell'immagine JPEG, o None in caso di errore.
    """
    try:
        url = f"{HA_API_BASE}/camera_proxy/{entity_id}"
        response = requests.get(url, headers={
            "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
        }, timeout=10)
        response.raise_for_status()

        if response.headers.get("Content-Type", "").startswith("image/"):
            return response.content
        else:
            logger.warning("Risposta non è un'immagine per %s: %s", entity_id, response.headers.get("Content-Type"))
            return None

    except Exception as e:
        logger.error("Errore nello snapshot di %s: %s", entity_id, e)
        return None


def get_url_snapshot(url: str) -> bytes | None:
    """
    Ottiene uno snapshot JPEG da un URL diretto.
    
    Args:
        url: URL completo per ottenere lo snapshot (es. URL Reolink)
    
    Returns:
        Bytes dell'immagine JPEG, o None in caso di errore.
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.content
    except Exception as e:
        logger.error("Errore nello snapshot da URL %s: %s", url, e)
        return None
