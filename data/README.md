# Scheda del dataset sintetico

**Origine:** generatore originale in `src/servicerescue/domain.py`. Non deriva da un dataset standard e non contiene dati personali. Tutti i valori sono ipotesi del benchmark, non misure o parametri stimati su infrastrutture reali.

**Unità statistica:** una fotografia dei sensori di un’infrastruttura e l’esito futuro del suo servizio critico. Le fotografie della stessa infrastruttura condividono la topologia; sono campionamenti di scenario, non una serie temporale. La generalizzazione valutata riguarda infrastrutture mai viste, campionate dalla stessa famiglia del generatore.

## Generazione

La descrizione seguente riguarda lo scenario `standard`. La valutazione completa include anche `redundant` (stessa dimensione, probabilità di repliche 0,80 e di seconda dipendenza 0,15) e `dense` (20–30 nodi, probabilità 0,15 e 0,75). Ogni dataset contiene 120 infrastrutture e 960 fotografie. I seed sono rispettivamente 42, 73 e 101, prefissati; sensori e futuro usano le stesse equazioni. La seconda probabilità è condizionata all’assenza di repliche. Ogni famiglia ha la propria CV annidata: non si misura trasferimento tra famiglie. Dati completi nelle tre cartelle `results/full*`, sintesi in `results/scenarios/`.

Il profilo `full` crea 120 topologie, ciascuna con 10–18 nodi, e 8 fotografie per topologia. I primi tre nodi non dipendono da altri. Ogni nodo successivo estrae due predecessori distinti: con probabilità 0,45 li usa come repliche; altrimenti richiede il primo e, con probabilità 0,35, anche il secondo. Gli archi puntano verso indici inferiori. Il nodo finale è critico; nodi non raggiungibili da esso fungono da informazione irrilevante rispetto al suo guasto. Non si selezionano solo topologie o osservazioni che favoriscono la KB.

Per ogni fotografia si estrae uno stress comune uniforme in [0; 0,32]. La severità di ciascun nodo è una Beta(1,3; 4,5) più lo stress, troncata in [0; 1]. I sensori sono versioni rumorose della severità: errors = severità + rumore normale con σ=0,09; cpu = 0,2 + 0,72×severità + rumore con σ=0,09; latency = 25 + 180×severità + rumore con σ=12. Cpu ed errors sono normalizzati e troncati in [0; 1], latency ha minimo 1. Non rappresentano unità operative validate.

La probabilità di guasto futuro di un nodo è `0.015 + 0.60 * severity**2`. Ogni nodo appartiene a una delle tre zone, fissata per topologia; ogni zona subisce uno shock con probabilità 0,025 per fotografia, che guasta tutti i suoi nodi. Lo stato futuro si propaga con dipendenze obbligatorie e repliche. Il target è 1 se il servizio critico risulta indisponibile. Severità latente, shock e guasti futuri non entrano nelle feature. La zona non è usata dai classificatori: la causa comune resta parzialmente non osservata.

La logica usa allarmi con `errors >= 0.60 OR cpu >= 0.85`, fissati prima dell’esperimento. Il target **non è** la soglia sugli allarmi e non è una copia di `root_down`: dipende da estrazioni future. Generatore e KB condividono comunque le ipotesi strutturali: un eventuale guadagno predittivo resta condizionato a una BK corretta nel mondo simulato.

## Feature

Il ramo di clustering usa un dataset separato: `monitoring_nominal.csv` contiene riferimento e calibrazione senza etichette, `monitoring_observed.csv` contiene i sensori del monitoraggio, `monitoring_truth.json` conserva soltanto l’oracolo per i test. Le tre feature sono cpu, errors e latency. Scaler, centroidi e soglie sono stimati per fold su infrastrutture distinte dai test. Gli allarmi derivati alimentano la KB per dedurre l’indisponibilità critica. Non si raggruppa il target di previsione futura e gli identificativi dei cluster non diventano etichette supervisionate. Le formule del generatore nominale e dei guasti sono documentate nel Word e in `src/servicerescue/unsupervised.py`.

| Insieme | Variabili aggiunte | Informazione |
|---|---|---|
| BASE (6) | root_cpu, root_errors, root_latency, n_nodes, n_requires, n_replicas | Sensori del servizio critico e dimensioni dell’infrastruttura |
| BASE+LOCAL (11 totali) | mean_cpu, max_cpu, mean_errors, max_errors, alarm_fraction | Aggregazioni dei sensori di tutti i nodi senza usare i percorsi |
| BASE+KB (17 totali) | root_down, down_fraction, reachable_fraction, exposed_fraction, reachable_down_fraction, degraded_fraction | Conseguenze della KB e aggregazioni delle relazioni derivate |

`exposed_fraction` e `reachable_down_fraction` sono frazioni dei nodi raggiungibili dal servizio critico; usano denominatore almeno 1. Le altre frazioni hanno come denominatore il numero totale di nodi. `root_down` è binario. Gli identificativi, il gruppo, la fotografia, il target e i costi non sono feature.

## File prodotti in `results/<profilo>/`

- `topologies.json`: inventario strutturale, zone e costi per gruppo.
- `observations.jsonl`: sensori originali, identificativi e target per fotografia.
- `dataset.csv`: feature materializzate, gruppo e target.
- `splits.json`: indici globali dei train/test esterni e dei train/validation interni.
- `run.json`: seed, configurazione, versioni, hash del codice e del dataset.

Gli stream pseudo-casuali di topologie, sensori ed esiti sono separati. Il seed predefinito è 42, senza ricerca di un seed favorevole. Tutte le osservazioni generate vengono conservate, senza bilanciamenti globali, filtri sul target o selezione dei casi migliori.

**Limiti:** topologie piccole e prevalentemente semplici, nessun drift o misura reale, nessuna modellazione della durata dell’incidente, dei tentativi di retry, della capacità residua o degli effetti collaterali delle riparazioni. Il rumore è una scelta del simulatore; non misura l’incertezza di strumenti reali.
