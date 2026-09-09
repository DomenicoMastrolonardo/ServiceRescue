# Validazione esterna

La cartella `rcaeval/` contiene l’estratto riproducibile del sottoinsieme **RCAEval RE2-OB** relativo a Online Boutique. Sono inclusi 90 casi di guasto con metriche selezionate, annotazioni del caso e archi ricavati dalle tracce completate prima dell’iniezione.

La fonte è il dataset pubblico [RCAEval](https://github.com/phamquiluan/RCAEval), pubblicato anche su [Hugging Face](https://huggingface.co/datasets/phamquiluan/RCAEval), con licenza MIT per i dati e il codice del progetto RCAEval. La pubblicazione scientifica è identificata dal DOI [10.1145/3701716.3715290](https://doi.org/10.1145/3701716.3715290).

I file `.csv.gz` contengono solo segnali selezionati (`cpu`, `mem`, `socket`, `workload`, `latency-90`) e il tempo. I file `.json` conservano le annotazioni del caso, gli hash delle sorgenti, l’hash del derivato e gli archi osservati. `manifest.json` fissa revisione, URL, licenza e regola di preparazione.

I sensori sono misure di un sistema in esecuzione con guasti introdotti sperimentalmente. Non sono incidenti spontanei di produzione. I valori non finiti sono conservati negli estratti: l’evaluatore li imputa con le mediane del solo training. Tutti i 90 casi vengono valutati; i due casi con periodo post-iniezione più corto restano inclusi.

Gli archi sono relazioni osservate nelle tracce completate prima dell’iniezione, non dipendenze obbligatorie. Non entrano nei detector. Tre regole in `kb/observed_calls.json` producono esempi successivi di possibili chiamanti interessati da un allarme, con prove Datalog; non producono etichette di indisponibilità e non validano causalmente le riparazioni.

La valutazione riparte da zero per ciascun caso: 60% dello storico nominale per fit, 20% per calibrazione e il restante 20% per test insieme a tutto il periodo post-iniezione. Le annotazioni della causa non sono feature. L’istante annotato di iniezione delimita lo storico nominale e il target sperimentale: lo studio assume che sia disponibile uno storico pulito. I risultati non misurano trasferimento tra infrastrutture né previsione del momento di iniezione.

Gli estratti inclusi e le dipendenze principali bastano per valutare e auditare senza rete:

```bash
python tools/external/evaluate.py
python tools/external/audit.py
```

Si conservano modelli, split temporali, 230.706 predizioni, metriche per caso e per tipo di guasto in `results/external/rcaeval/`. Le medie attribuiscono uguale peso ai 90 casi, con deviazione standard campionaria; non sono medie da CV annidata. Il protocollo supervisionato sintetico resta separato.

Per rigenerare i file:

```bash
python -m pip install -r requirements-external.txt
python tools/external/prepare.py --cache .cache/rcaeval
```
