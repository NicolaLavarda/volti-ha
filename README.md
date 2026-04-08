# Volti HA - Face Recognition Add-on per Home Assistant

[![Home Assistant Add-on](https://img.shields.io/badge/Home%20Assistant-Add--on-blue.svg)](https://www.home-assistant.io/)

Riconoscimento facciale in tempo reale per le telecamere di Home Assistant, basato su un modello SVM addestrato con le tue foto personali.

## Funzionalità

- 🎥 **Analisi telecamere** in tempo reale con intervallo configurabile
- 🧑 **Riconoscimento facciale** tramite modello SVM personalizzato (face_recognition + scikit-learn)
- 🔌 **Integrazione nativa HA** via MQTT auto-discovery (entità create automaticamente)
- 🌐 **Interfaccia web** integrata nel pannello laterale di Home Assistant
- 📸 **Salvataggio automatico** dei volti per ri-addestramento del modello
- 🚗 **Predisposto** per riconoscimento targhe (prossimamente)

## Installazione

1. Aggiungi questa repository al tuo Home Assistant:
   - Vai su **Impostazioni** → **Add-on** → **Store Add-on** → **⋮** → **Repository**
   - Inserisci: `https://github.com/NicolaLavarda/volti-ha`
2. Installa l'add-on **Volti HA**
3. Configura le opzioni MQTT nella tab Configurazione
4. Avvia l'add-on
5. Accedi all'interfaccia dal pannello laterale

## Requisiti

- Home Assistant con Supervisor
- Add-on Mosquitto Broker installato
- Integrazione MQTT configurata
- Modello addestrato (`classificatore_volti_HA.pkl`)

## Addestramento Modello

Il modello va addestrato sul tuo PC:

```bash
# 1. Estrai embeddings dalle foto
python extract_embeddings.py "Volti totali"

# 2. Addestra il classificatore SVM
python train_from_embeddings.py
```

Poi carica il file `classificatore_volti_HA.pkl` risultante nell'add-on tramite l'interfaccia web.

## Licenza

MIT License
