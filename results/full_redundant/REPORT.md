# Risultati ServiceRescue-KB

Profilo **full**, seed 73; 960 esempi, 120 infrastrutture; prevalenza positiva 21.1%.

CV esterna 5 fold × 2 ripetizioni; CV interna 3 fold. Media ± deviazione standard campionaria sui fold esterni.

Gli stessi gruppi e split sono usati per ogni confronto. Le ripetizioni riusano il dataset: i fold non sono osservazioni indipendenti e la deviazione standard non è un intervallo di confidenza.

| Modello | Feature | F1 macro | Balanced accuracy | Average precision | Brier ↓ |
|---|---|---:|---:|---:|---:|
| DummyPrior | - | 0.441 ± 0.011 | 0.500 ± 0.000 | 0.212 ± 0.034 | 0.167 ± 0.020 |
| GradientBoosting | BASE | 0.491 ± 0.037 | 0.519 ± 0.022 | 0.341 ± 0.061 | 0.163 ± 0.023 |
| GradientBoosting | BASE+KB | 0.476 ± 0.028 | 0.511 ± 0.014 | 0.334 ± 0.059 | 0.163 ± 0.021 |
| GradientBoosting | BASE+LOCAL | 0.481 ± 0.041 | 0.514 ± 0.025 | 0.344 ± 0.062 | 0.162 ± 0.019 |
| LogicOnly | - | 0.601 ± 0.053 | 0.613 ± 0.060 | 0.281 ± 0.047 | 0.283 ± 0.046 |
| LogisticRegression | BASE | 0.581 ± 0.035 | 0.629 ± 0.051 | 0.389 ± 0.093 | 0.225 ± 0.013 |
| LogisticRegression | BASE+KB | 0.553 ± 0.038 | 0.589 ± 0.048 | 0.387 ± 0.092 | 0.213 ± 0.026 |
| LogisticRegression | BASE+LOCAL | 0.568 ± 0.031 | 0.619 ± 0.049 | 0.393 ± 0.095 | 0.226 ± 0.013 |
| RandomForest | BASE | 0.487 ± 0.037 | 0.514 ± 0.024 | 0.325 ± 0.076 | 0.165 ± 0.020 |
| RandomForest | BASE+KB | 0.501 ± 0.033 | 0.523 ± 0.021 | 0.335 ± 0.076 | 0.164 ± 0.020 |
| RandomForest | BASE+LOCAL | 0.493 ± 0.025 | 0.519 ± 0.017 | 0.332 ± 0.087 | 0.165 ± 0.018 |

LogicOnly emette valori 0/1: AP e Brier si riferiscono a tali valori, non a probabilità calibrate. La soglia dei classificatori è quella predefinita (0,5); la selezione interna ottimizza F1 macro.

## Contributo della conoscenza

| Modello | Confronto | Δ F1 macro | Fold con Δ > 0 |
|---|---|---:|---:|
| LogisticRegression | BASE+KB minus BASE | -0.027 ± 0.040 | 2/10 |
| LogisticRegression | BASE+KB minus BASE+LOCAL | -0.014 ± 0.021 | 3/10 |
| RandomForest | BASE+KB minus BASE | +0.014 ± 0.030 | 7/10 |
| RandomForest | BASE+KB minus BASE+LOCAL | +0.007 ± 0.030 | 4/10 |
| GradientBoosting | BASE+KB minus BASE | -0.015 ± 0.047 | 3/10 |
| GradientBoosting | BASE+KB minus BASE+LOCAL | -0.005 ± 0.049 | 4/10 |

Per LogisticRegression, aggiungere la BK alla baseline con aggregazioni diminuisce F1 macro in media di 1.44 punti percentuali; il miglioramento compare in 3 dei 10 fold. Questo è un risultato descrittivo del benchmark, senza una conclusione di significatività statistica.

Per RandomForest, aggiungere la BK alla baseline con aggregazioni aumenta F1 macro in media di 0.74 punti percentuali; il miglioramento compare in 4 dei 10 fold. Questo è un risultato descrittivo del benchmark, senza una conclusione di significatività statistica.

Per GradientBoosting, aggiungere la BK alla baseline con aggregazioni diminuisce F1 macro in media di 0.52 punti percentuali; il miglioramento compare in 4 dei 10 fold. Questo è un risultato descrittivo del benchmark, senza una conclusione di significatività statistica.


Il confronto con BASE+LOCAL isola il contributo delle feature relazionali rispetto ad aggregazioni globali degli stessi sensori. Un Δ negativo o instabile costituisce un limite osservato: non si assume che aggiungere conoscenza migliori sempre la previsione.

## Ragionamento

Accordo con simulatore indipendente: 960/960 casi.

| Misura per snapshot | Media | Dev. standard |
|---|---:|---:|
| input_facts | 15.263542 | 3.677047 |
| closure_facts | 98.590625 | 32.406666 |
| rounds | 5.042708 | 0.812602 |
| matches | 5433.920833 | 3264.828175 |
| seconds | 0.007987 | 0.004658 |
| derived_down | 3.152083 | 3.251982 |

## Ricerca del ripristino

| Strategia | Guasti | Casi | Costo | Eccesso su ottimo | Stati espansi | Secondi |
|---|---:|---:|---:|---:|---:|---:|
| ucs | 2 | 21 | 1.810 ± 2.400 | 0.000 ± 0.000 | 1.667 ± 0.730 | 0.000507 ± 0.000606 |
| ucs | 4 | 21 | 4.667 ± 5.247 | 0.000 ± 0.000 | 4.095 ± 3.714 | 0.001801 ± 0.002357 |
| ucs | 6 | 18 | 6.778 ± 4.821 | 0.000 ± 0.000 | 13.611 ± 13.776 | 0.005669 ± 0.004810 |
| cheapest | 2 | 21 | 2.286 ± 3.349 | 0.476 ± 1.365 | 1.667 ± 0.730 | 0.000470 ± 0.000566 |
| cheapest | 4 | 21 | 7.333 ± 8.452 | 2.667 ± 4.247 | 2.762 ± 1.609 | 0.000841 ± 0.000646 |
| cheapest | 6 | 18 | 13.556 ± 12.200 | 6.778 ± 8.842 | 4.444 ± 2.229 | 0.001885 ± 0.001470 |

Ogni piano è verificato con il simulatore; ogni costo UCS è confrontato con enumerazione esaustiva indipendente. I casi in cui il servizio critico è già operativo sono inclusi e hanno costo ottimo zero. I tempi dipendono dalla macchina.

## Limiti e interpretazione

Questo è un benchmark sintetico, non una validazione su incidenti reali. Generatore e KB condividono deliberatamente la semantica delle dipendenze: il confronto misura l’utilità di una BK corretta nel mondo simulato, non dimostra validità esterna. Il futuro contiene estrazioni casuali e shock di zona non osservati. Le riparazioni assumono guasti confermati, effetto certo e costi additivi; non sono decise sulla base delle probabilità del classificatore.

La pipeline collega ragionamento e ML tramite le feature e collega ragionamento e ricerca tramite l’oracolo di stato. Il ML non guida la ricerca. Una futura estensione potrebbe valutare decisioni sotto incertezza.

Durata totale misurata: 124.8 s. Configurazione, hash e versioni: `run.json`.

I risultati del profilo smoke servono solo a verificare l’esecuzione e non sostituiscono il profilo full.

## Verifica SWI-Prolog

Motore: SWI-Prolog version 9.0.4 for x86_64-linux. Tutti i sei predicati derivati coincidono con Datalog su 960 fotografie. Le feature del dataset finale sono materializzate dall’output di SWI-Prolog.

## Rete bayesiana con struttura appresa

Sei variabili binarie; ordine prefissato, fino a due genitori, selezione locale BIC. Mediane, struttura e CPD sono stimate nel training. Alpha e limite dei genitori sono scelti nei fold interni; inferenza esatta anche con evidenza parziale.

| F1 macro | Balanced accuracy | Average precision | Brier ↓ |
|---:|---:|---:|---:|
| 0.441 ± 0.011 | 0.500 ± 0.000 | 0.292 ± 0.046 | 0.159 ± 0.020 |

La rete usa cinque osservabili selezionati a priori, quindi il confronto con i classificatori a 17 feature è descrittivo. È una rete bayesiana proposizionale su feature relazionali aggregate, non un modello probabilistico relazionale.

## Analisi aggiuntive

learning_curve_summary.csv riporta curve su frazioni 0,4 / 0,7 / 1,0 dei gruppi di training, sugli stessi test esterni, con configurazioni fissate a priori. importance_summary.csv riporta permutation importance sui test: tre permutazioni mediate entro fold, poi media e deviazione standard fra fold. Queste analisi sono diagnostiche e non selezionano feature o iperparametri. Le feature correlate possono dividere l’importanza; le permutazioni non provano causalità.

## Apprendimento non supervisionato e monitoraggio

K-Means identifica regimi nei sensori nominali (cpu, errors, latency), su dati separati dal task supervisionato. Scelta di k fra 2 e 7 mediante silhouette nel training; scaler e centroidi non leggono i test. Il 20% dei gruppi di training calibra la soglia al quantile 0,95 della distanza dal centro più vicino. Il riferimento nominale è un’assunzione: non si impara da uno storico contaminato da guasti.

Le anomalie diventano fatti alarm e la KB ne deduce le conseguenze. Si valutano guasti locali iniettati e indisponibilità critica su infrastrutture esterne; le verità del simulatore non partecipano al fit, alla silhouette o alla calibrazione. Split a gruppi indipendenti dal task predittivo, 5 fold × 2 ripetizioni nel profilo full. Baseline: soglie manuali e distanza da un singolo centro, con la stessa calibrazione.

| Metodo | F1 guasti locali | Falsi allarmi locali | F1 macro servizio critico | Balanced accuracy critica |
|---|---:|---:|---:|---:|
| FixedThreshold | 0.487 ± 0.062 | 0.001 ± 0.001 | 0.738 ± 0.025 | 0.678 ± 0.025 |
| SingleCenter | 0.777 ± 0.023 | 0.053 ± 0.008 | 0.863 ± 0.032 | 0.956 ± 0.016 |
| KMeans | 0.788 ± 0.016 | 0.049 ± 0.004 | 0.878 ± 0.032 | 0.961 ± 0.016 |

Il benchmark di monitoraggio assume due modi di carico nominale e perturbazioni additive note al simulatore. Le prestazioni dipendono da queste ipotesi. La silhouette misura separazione geometrica; il confronto con il centro unico verifica separatamente se più regimi aiutino il monitoraggio. Non si interpreta un cluster come classe di guasto e non si trasferiscono le etichette dei cluster fra fit differenti. Modelli, partizioni e predizioni sono salvati nei file monitoring_*.
