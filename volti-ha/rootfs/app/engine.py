"""
engine.py - Motore di analisi facciale.
Basato direttamente sulla pipeline di Nicola:
  - face_recognition per la detection e l'encoding dei volti
  - Classificatore SVM (scikit-learn) per l'identificazione
  
Prende forte spunto da analyze_faces_locally() in codeproject_analyzer_loop_nuovo.py
"""

import io
import os
import pickle
import logging
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import face_recognition
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("volti_ha.engine")

MODELS_DIR = "/data/models"
MODEL_FILE = os.path.join(MODELS_DIR, "classificatore_volti_HA.pkl")
CROPPED_DIR = "/data/cropped_faces"


@dataclass
class FaceResult:
    """Risultato dell'analisi di un singolo volto."""
    name: str
    confidence: float
    top: int
    right: int
    bottom: int
    left: int

    def to_dict(self):
        return {
            "name": self.name,
            "confidence": round(self.confidence, 4),
            "box": {
                "top": self.top,
                "right": self.right,
                "bottom": self.bottom,
                "left": self.left,
            },
        }


@dataclass
class AnalysisResult:
    """Risultato completo dell'analisi di un frame."""
    faces: list = field(default_factory=list)
    plates: list = field(default_factory=list)  # Predisposto per il futuro
    timestamp: str = ""
    annotated_image: bytes = b""

    def to_dict(self):
        return {
            "faces": [f.to_dict() for f in self.faces],
            "plates": self.plates,
            "timestamp": self.timestamp,
            "faces_count": len(self.faces),
        }


class AnalysisEngine:
    """
    Motore principale di analisi.
    Carica il modello SVM e analizza le immagini per riconoscere volti.
    """

    def __init__(self, detection_model: str = "hog", min_confidence: float = 0.7):
        self.classifier = None
        self.detection_model = detection_model
        self.min_confidence = min_confidence
        self.known_names: list[str] = []
        self.model_loaded = False
        self.model_load_time: str | None = None

        # Prova a caricare il modello se esiste
        if os.path.exists(MODEL_FILE):
            self.load_model(MODEL_FILE)

    def load_model(self, model_path: str = None) -> bool:
        """
        Carica il classificatore SVM dal file .pkl.
        Esattamente come nella riga 482-484 di codeproject_analyzer_loop_nuovo.py:
            with open(MODEL_FILE_PATH, 'rb') as f:
                face_classifier = pickle.load(f)
        """
        path = model_path or MODEL_FILE
        try:
            with open(path, "rb") as f:
                self.classifier = pickle.load(f)
            
            # Estrai i nomi delle persone che il modello conosce
            if hasattr(self.classifier, "classes_"):
                self.known_names = list(self.classifier.classes_)
            else:
                self.known_names = []
            
            self.model_loaded = True
            self.model_load_time = datetime.now().isoformat()
            logger.info(
                "Modello caricato con successo! Persone note: %s",
                ", ".join(self.known_names) if self.known_names else "nessuna",
            )
            return True

        except FileNotFoundError:
            logger.error("File modello non trovato: %s", path)
            self.model_loaded = False
            return False
        except Exception as e:
            logger.error("Errore nel caricamento del modello: %s", e)
            self.model_loaded = False
            return False

    def save_uploaded_model(self, file_data: bytes) -> bool:
        """Salva un modello caricato via upload e lo carica in memoria."""
        os.makedirs(MODELS_DIR, exist_ok=True)
        try:
            with open(MODEL_FILE, "wb") as f:
                f.write(file_data)
            logger.info("Modello salvato in %s (%d bytes).", MODEL_FILE, len(file_data))
            return self.load_model(MODEL_FILE)
        except Exception as e:
            logger.error("Errore nel salvataggio del modello: %s", e)
            return False

    def analyze_faces(self, image_bytes: bytes) -> list[FaceResult]:
        """
        Analizza un'immagine e restituisce i volti riconosciuti.
        
        Implementazione basata direttamente su analyze_faces_locally()
        del file codeproject_analyzer_loop_nuovo.py (righe 154-200):
            immagine = face_recognition.load_image_file(image_path)
            posizioni_volti = face_recognition.face_locations(immagine, model=FACE_DETECTION_MODEL)
            embeddings_live = face_recognition.face_encodings(immagine, posizioni_volti)
            nome_predetto = face_classifier.predict([embedding])[0]
            probabilita = face_classifier.predict_proba([embedding])[0]
            confidenza = max(probabilita)
        """
        if not self.model_loaded or self.classifier is None:
            logger.warning("Modello non caricato. Analisi volti saltata.")
            return []

        try:
            # 1. Carica l'immagine dai bytes
            image = face_recognition.load_image_file(io.BytesIO(image_bytes))

            # 2. Trova DOVE sono i volti
            face_locations = face_recognition.face_locations(
                image, model=self.detection_model
            )

            if not face_locations:
                return []

            # 3. Estrai gli embedding (vettori 128D) di tutti i volti trovati
            face_encodings = face_recognition.face_encodings(image, face_locations)

            # 4. Classifica ogni volto con il modello SVM
            results = []
            for (top, right, bottom, left), encoding in zip(face_locations, face_encodings):
                name = self.classifier.predict([encoding])[0]
                probabilities = self.classifier.predict_proba([encoding])[0]
                confidence = float(max(probabilities))

                # Se la confidenza è sotto la soglia, segna come Sconosciuto
                if confidence < self.min_confidence:
                    name = "Sconosciuto"

                results.append(
                    FaceResult(
                        name=name,
                        confidence=confidence,
                        top=top,
                        right=right,
                        bottom=bottom,
                        left=left,
                    )
                )

            return results

        except Exception as e:
            logger.error("Errore durante l'analisi volti: %s", e)
            return []

    def analyze_plates(self, image_bytes: bytes) -> list:
        """
        STUB: Predisposto per il riconoscimento targhe futuro.
        In futuro qui verrà implementato un modello locale per le targhe.
        """
        return []

    def analyze(self, image_bytes: bytes, modes: list[str] = None) -> AnalysisResult:
        """
        Esegue l'analisi completa su un'immagine.
        
        Args:
            image_bytes: Bytes dell'immagine JPEG
            modes: Lista di modalità da eseguire ["faces", "plates"]
        """
        if modes is None:
            modes = ["faces"]

        result = AnalysisResult(timestamp=datetime.now().isoformat())

        if "faces" in modes:
            result.faces = self.analyze_faces(image_bytes)

        if "plates" in modes:
            result.plates = self.analyze_plates(image_bytes)

        # Crea l'immagine annotata con i box
        if result.faces:
            result.annotated_image = self._create_annotated_image(
                image_bytes, result.faces
            )

        return result

    def _create_annotated_image(self, image_bytes: bytes, faces: list[FaceResult]) -> bytes:
        """
        Crea un'immagine annotata con box e nomi sovrapposti.
        Basato su create_annotated_image() del file codeproject_analyzer_loop_nuovo.py (righe 258-321).
        """
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            draw = ImageDraw.Draw(image)

            # Font - usa default se non disponibile
            try:
                font = ImageFont.truetype("/usr/share/fonts/ttf-dejavu/DejaVuSans-Bold.ttf", 20)
            except (IOError, OSError):
                font = ImageFont.load_default()

            for face in faces:
                box = (face.left, face.top, face.right, face.bottom)

                # Verde per riconosciuti, rosso per sconosciuti
                if face.name == "Sconosciuto":
                    color = "#FF4444"
                else:
                    color = "#44CC44"

                # Disegna il rettangolo
                draw.rectangle(box, outline=color, width=3)

                # Label con nome e percentuale
                label = f"{face.name} ({int(face.confidence * 100)}%)"
                
                # Sfondo per il testo
                bbox = font.getbbox(label)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
                padding = 4
                
                label_bg = (
                    face.left,
                    face.top - text_h - padding * 2,
                    face.left + text_w + padding * 2,
                    face.top,
                )
                draw.rectangle(label_bg, fill=color)
                draw.text(
                    (face.left + padding, face.top - text_h - padding),
                    label,
                    fill="white",
                    font=font,
                )

            # Converti in bytes JPEG
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=85)
            return output.getvalue()

        except Exception as e:
            logger.error("Errore nella creazione dell'immagine annotata: %s", e)
            return image_bytes  # Ritorna l'originale in caso di errore

    def save_cropped_face(self, image_bytes: bytes, face: FaceResult):
        """
        Salva il volto ritagliato per ri-addestramento futuro.
        Basato su save_cropped_face() del file codeproject_analyzer_loop_nuovo.py (righe 323-352).
        """
        try:
            person_folder = os.path.join(CROPPED_DIR, face.name)
            os.makedirs(person_folder, exist_ok=True)

            image = Image.open(io.BytesIO(image_bytes))
            img_width, img_height = image.size

            # Espandi l'area di ritaglio (2x) come nell'originale
            width = face.right - face.left
            height = face.bottom - face.top
            center_x = face.left + width / 2
            center_y = face.top + height / 2

            new_width = width * 2
            new_height = height * 2

            crop_box = (
                max(0, int(center_x - new_width / 2)),
                max(0, int(center_y - new_height / 2)),
                min(img_width, int(center_x + new_width / 2)),
                min(img_height, int(center_y + new_height / 2)),
            )

            cropped = image.crop(crop_box)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            save_path = os.path.join(person_folder, f"{timestamp}.jpg")
            cropped.save(save_path, "JPEG")

            logger.debug("Volto salvato: %s", save_path)

        except Exception as e:
            logger.error("Errore nel salvataggio del volto ritagliato: %s", e)

    def get_model_info(self) -> dict:
        """Restituisce informazioni sul modello caricato."""
        return {
            "loaded": self.model_loaded,
            "known_names": self.known_names,
            "load_time": self.model_load_time,
            "detection_model": self.detection_model,
            "min_confidence": self.min_confidence,
        }
