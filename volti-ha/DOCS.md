# Volti HA - Documentazione

## Descrizione

**Volti HA** è un add-on per Home Assistant che esegue il riconoscimento facciale in tempo reale sulle tue telecamere, utilizzando un modello SVM addestrato con le tue foto personali.

## Come funziona

1. **Addestra il modello** sul tuo PC usando gli script `extract_embeddings.py` e `train_from_embeddings.py`
2. **Carica il modello** (file `.pkl`) nell'add-on tramite l'interfaccia web
3. **Aggiungi le telecamere** selezionandole dalle entità HA o inserendo l'URL diretto
4. **Attiva l'analisi** con lo switch creato automaticamente per ogni telecamera
5. **Crea automazioni** basate sulle entità sensore create automaticamente

## Entità Create

Per ogni telecamera configurata, l'add-on crea automaticamente via MQTT:

| Entità | Descrizione |
|--------|-------------|
| `switch.volti_ha_<nome>_analisi` | ON/OFF per avviare/fermare l'analisi |
| `sensor.volti_ha_<nome>_persone` | Nomi delle persone riconosciute |
| `binary_sensor.volti_ha_<nome>_volto` | ON se almeno un volto rilevato |
| `camera.volti_ha_<nome>_annotata` | Immagine con box e nomi sovrapposti |

## Requisiti

- Add-on **Mosquitto Broker** installato e configurato
- Integrazione **MQTT** configurata in Home Assistant
- File modello `classificatore_volti_HA.pkl` addestrato

## Esempio Automazione

```yaml
automation:
  - alias: "Apri cancello persona nota"
    trigger:
      - platform: state
        entity_id: sensor.volti_ha_carraio_persone
    condition:
      - condition: template
        value_template: >
          {{ state_attr('sensor.volti_ha_carraio_persone', 'faces')
             | selectattr('name', 'in', ['Nicola', 'Papà', 'Mamma'])
             | selectattr('confidence', '>=', 0.85)
             | list | count > 0 }}
    action:
      - service: switch.turn_on
        entity_id: switch.cancello
```

## Supporto

Per problemi o richieste: [GitHub Issues](https://github.com/NicolaLavarda/volti-ha/issues)
