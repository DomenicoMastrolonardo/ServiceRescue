# Risultati ServiceRescue-KB

Profilo **full**, seed 101; 960 esempi, 120 infrastrutture; prevalenza positiva 58.1%.

CV esterna 5 fold × 2 ripetizioni; CV interna 3 fold. Media ± deviazione standard campionaria sui fold esterni.

Gli stessi gruppi e split sono usati per ogni confronto. Le ripetizioni riusano il dataset: i fold non sono osservazioni indipendenti e la deviazione standard non è un intervallo di confidenza.

| Modello | Feature | F1 macro | Balanced accuracy | Average precision | Brier ↓ |
|---|---|---:|---:|---:|---:|
| DummyPrior | - | 0.367 ± 0.013 | 0.500 ± 0.000 | 0.581 ± 0.031 | 0.244 ± 0.005 |
| GradientBoosting | BASE | 0.551 ± 0.040 | 0.562 ± 0.040 | 0.697 ± 0.032 | 0.232 ± 0.006 |
| GradientBoosting | BASE+KB | 0.646 ± 0.041 | 0.647 ± 0.039 | 0.758 ± 0.041 | 0.213 ± 0.011 |
| GradientBoosting | BASE+LOCAL | 0.591 ± 0.050 | 0.595 ± 0.050 | 0.703 ± 0.028 | 0.230 ± 0.009 |
| LogicOnly | - | 0.655 ± 0.038 | 0.656 ± 0.039 | 0.676 ± 0.034 | 0.335 ± 0.033 |
| LogisticRegression | BASE | 0.580 ± 0.044 | 0.585 ± 0.044 | 0.717 ± 0.032 | 0.233 ± 0.010 |
| LogisticRegression | BASE+KB | 0.665 ± 0.032 | 0.669 ± 0.035 | 0.777 ± 0.037 | 0.210 ± 0.011 |
| LogisticRegression | BASE+LOCAL | 0.614 ± 0.049 | 0.616 ± 0.049 | 0.737 ± 0.027 | 0.227 ± 0.013 |
| RandomForest | BASE | 0.555 ± 0.036 | 0.565 ± 0.037 | 0.702 ± 0.021 | 0.232 ± 0.005 |
| RandomForest | BASE+KB | 0.658 ± 0.039 | 0.658 ± 0.038 | 0.759 ± 0.046 | 0.213 ± 0.013 |
| RandomForest | BASE+LOCAL | 0.600 ± 0.055 | 0.602 ± 0.055 | 0.716 ± 0.023 | 0.229 ± 0.012 |

LogicOnly emette valori 0/1: AP e Brier si riferiscono a tali valori, non a probabilità calibrate. La soglia dei classificatori è quella predefinita (0,5); la selezione interna ottimizza F1 macro.

## Contributo della conoscenza

| Modello | Confronto | Δ F1 macro | Fold con Δ > 0 |
|---|---|---:|---:|
| LogisticRegression | BASE+KB minus BASE | +0.085 ± 0.034 | 10/10 |
| LogisticRegression | BASE+KB minus BASE+LOCAL | +0.052 ± 0.034 | 9/10 |
| RandomForest | BASE+KB minus BASE | +0.103 ± 0.031 | 10/10 |
| RandomForest | BASE+KB minus BASE+LOCAL | +0.058 ± 0.037 | 9/10 |
| GradientBoosting | BASE+KB minus BASE | +0.096 ± 0.029 | 10/10 |
| GradientBoosting | BASE+KB minus BASE+LOCAL | +0.055 ± 0.045 | 9/10 |

Per LogisticRegression, aggiungere la BK alla baseline con aggregazioni aumenta F1 macro in media di 5.15 punti percentuali; il miglioramento compare in 9 dei 10 fold. Questo è un risultato descrittivo del benchmark, senza una conclusione di significatività statistica.

Per RandomForest, aggiungere la BK alla baseline con aggregazioni aumenta F1 macro in media di 5.79 punti percentuali; il miglioramento compare in 9 dei 10 fold. Questo è un risultato descrittivo del benchmark, senza una conclusione di significatività statistica.

Per GradientBoosting, aggiungere la BK alla baseline con aggregazioni aumenta F1 macro in media di 5.46 punti percentuali; il miglioramento compare in 9 dei 10 fold. Questo è un risultato descrittivo del benchmark, senza una conclusione di significatività statistica.


Il confronto con BASE+LOCAL isola il contributo delle feature relazionali rispetto ad aggregazioni globali degli stessi sensori. Un Δ negativo o instabile costituisce un limite osservato: non si assume che aggiungere conoscenza migliori sempre la previsione.

## Ragionamento

Accordo con simulatore indipendente: 960/960 casi.

| Misura per snapshot | Media | Dev. standard |
|---|---:|---:|
| input_facts | 42.228125 | 6.667669 |
| closure_facts | 238.388542 | 57.007693 |
| rounds | 6.010417 | 0.870017 |
| matches | 27435.664583 | 13324.216220 |
| seconds | 0.036728 | 0.017140 |
| derived_down | 11.821875 | 8.431688 |

## Ricerca del ripristino

| Strategia | Guasti | Casi | Costo | Eccesso su ottimo | Stati espansi | Secondi |
|---|---:|---:|---:|---:|---:|---:|
| ucs | 2 | 21 | 3.238 ± 4.073 | 0.000 ± 0.000 | 2.143 ± 1.108 | 0.000515 ± 0.000417 |
| ucs | 4 | 21 | 2.952 ± 2.801 | 0.000 ± 0.000 | 3.286 ± 2.452 | 0.001083 ± 0.000763 |
| ucs | 6 | 18 | 8.444 ± 4.890 | 0.000 ± 0.000 | 16.222 ± 14.719 | 0.007518 ± 0.006973 |
| cheapest | 2 | 21 | 4.143 ± 4.892 | 0.905 ± 1.814 | 2.048 ± 0.973 | 0.000422 ± 0.000359 |
| cheapest | 4 | 21 | 6.000 ± 7.197 | 3.048 ± 4.717 | 2.762 ± 1.480 | 0.000821 ± 0.000464 |
| cheapest | 6 | 18 | 20.000 ± 10.538 | 11.556 ± 8.046 | 5.556 ± 1.886 | 0.002386 ± 0.001581 |

Ogni piano è verificato con il simulatore; ogni costo UCS è confrontato con enumerazione esaustiva indipendente. I casi in cui il servizio critico è già operativo sono inclusi e hanno costo ottimo zero. I tempi dipendono dalla macchina.

## Limiti e interpretazione

Questo è un benchmark sintetico, non una validazione su incidenti reali. Generatore e KB condividono deliberatamente la semantica delle dipendenze: il confronto misura l’utilità di una BK corretta nel mondo simulato, non dimostra validità esterna. Il futuro contiene estrazioni casuali e shock di zona non osservati. Le riparazioni assumono guasti confermati, effetto certo e costi additivi; non sono decise sulla base delle probabilità del classificatore.

La pipeline collega ragionamento e ML tramite le feature e collega ragionamento e ricerca tramite l’oracolo di stato. Il ML non guida la ricerca. Una futura estensione potrebbe valutare decisioni sotto incertezza.

Durata totale misurata: 193.4 s. Configurazione, hash e versioni: `run.json`.

I risultati del profilo smoke servono solo a verificare l’esecuzione e non sostituiscono il profilo full.

## Verifica SWI-Prolog

Motore: SWI-Prolog version 9.0.4 for x86_64-linux. Tutti i sei predicati derivati coincidono con Datalog su 960 fotografie. Le feature del dataset finale sono materializzate dall’output di SWI-Prolog.

## Rete bayesiana con struttura appresa

Sei variabili binarie; ordine prefissato, fino a due genitori, selezione locale BIC. Mediane, struttura e CPD sono stimate nel training. Alpha e limite dei genitori sono scelti nei fold interni; inferenza esatta anche con evidenza parziale.

| F1 macro | Balanced accuracy | Average precision | Brier ↓ |
|---:|---:|---:|---:|
| 0.578 ± 0.056 | 0.581 ± 0.053 | 0.668 ± 0.041 | 0.237 ± 0.013 |

La rete usa cinque osservabili selezionati a priori, quindi il confronto con i classificatori a 17 feature è descrittivo. È una rete bayesiana proposizionale su feature relazionali aggregate, non un modello probabilistico relazionale.

## Analisi aggiuntive

learning_curve_summary.csv riporta curve su frazioni 0,4 / 0,7 / 1,0 dei gruppi di training, sugli stessi test esterni, con configurazioni fissate a priori. importance_summary.csv riporta permutation importance sui test: tre permutazioni mediate entro fold, poi media e deviazione standard fra fold. Queste analisi sono diagnostiche e non selezionano feature o iperparametri. Le feature correlate possono dividere l’importanza; le permutazioni non provano causalità.

## Apprendimento non supervisionato e monitoraggio

K-Means identifica regimi nei sensori nominali (cpu, errors, latency), su dati separati dal task supervisionato. Scelta di k fra 2 e 7 mediante silhouette nel training; scaler e centroidi non leggono i test. Il 20% dei gruppi di training calibra la soglia al quantile 0,95 della distanza dal centro più vicino. Il riferimento nominale è un’assunzione: non si impara da uno storico contaminato da guasti.

Le anomalie diventano fatti alarm e la KB ne deduce le conseguenze. Si valutano guasti locali iniettati e indisponibilità critica su infrastrutture esterne; le verità del simulatore non partecipano al fit, alla silhouette o alla calibrazione. Split a gruppi indipendenti dal task predittivo, 5 fold × 2 ripetizioni nel profilo full. Baseline: soglie manuali e distanza da un singolo centro, con la stessa calibrazione.

| Metodo | F1 guasti locali | Falsi allarmi locali | F1 macro servizio critico | Balanced accuracy critica |
|---|---:|---:|---:|---:|
| FixedThreshold | 0.521 ± 0.035 | 0.001 ± 0.000 | 0.687 ± 0.024 | 0.695 ± 0.020 |
| SingleCenter | 0.770 ± 0.019 | 0.052 ± 0.005 | 0.844 ± 0.022 | 0.863 ± 0.021 |
| KMeans | 0.755 ± 0.023 | 0.057 ± 0.007 | 0.824 ± 0.034 | 0.846 ± 0.030 |

Il benchmark di monitoraggio assume due modi di carico nominale e perturbazioni additive note al simulatore. Le prestazioni dipendono da queste ipotesi. La silhouette misura separazione geometrica; il confronto con il centro unico verifica separatamente se più regimi aiutino il monitoraggio. Non si interpreta un cluster come classe di guasto e non si trasferiscono le etichette dei cluster fra fit differenti. Modelli, partizioni e predizioni sono salvati nei file monitoring_*.
