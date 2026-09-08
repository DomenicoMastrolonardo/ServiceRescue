# Risultati ServiceRescue-KB

Profilo **full**, seed 42; 960 esempi, 120 infrastrutture; prevalenza positiva 33.0%.

CV esterna 5 fold × 2 ripetizioni; CV interna 3 fold. Media ± deviazione standard campionaria sui fold esterni.

Gli stessi gruppi e split sono usati per ogni confronto. Le ripetizioni riusano il dataset: i fold non sono osservazioni indipendenti e la deviazione standard non è un intervallo di confidenza.

| Modello | Feature | F1 macro | Balanced accuracy | Average precision | Brier ↓ |
|---|---|---:|---:|---:|---:|
| DummyPrior | - | 0.401 ± 0.012 | 0.500 ± 0.000 | 0.330 ± 0.033 | 0.222 ± 0.012 |
| GradientBoosting | BASE | 0.489 ± 0.048 | 0.525 ± 0.028 | 0.448 ± 0.040 | 0.217 ± 0.016 |
| GradientBoosting | BASE+KB | 0.561 ± 0.026 | 0.569 ± 0.019 | 0.489 ± 0.043 | 0.211 ± 0.014 |
| GradientBoosting | BASE+LOCAL | 0.520 ± 0.035 | 0.543 ± 0.022 | 0.459 ± 0.030 | 0.216 ± 0.017 |
| LogicOnly | - | 0.627 ± 0.021 | 0.625 ± 0.021 | 0.417 ± 0.041 | 0.321 ± 0.021 |
| LogisticRegression | BASE | 0.573 ± 0.043 | 0.588 ± 0.049 | 0.464 ± 0.029 | 0.238 ± 0.011 |
| LogisticRegression | BASE+KB | 0.615 ± 0.032 | 0.622 ± 0.034 | 0.509 ± 0.045 | 0.221 ± 0.016 |
| LogisticRegression | BASE+LOCAL | 0.602 ± 0.048 | 0.621 ± 0.056 | 0.493 ± 0.042 | 0.234 ± 0.013 |
| RandomForest | BASE | 0.543 ± 0.034 | 0.556 ± 0.024 | 0.443 ± 0.048 | 0.221 ± 0.016 |
| RandomForest | BASE+KB | 0.574 ± 0.038 | 0.581 ± 0.028 | 0.499 ± 0.053 | 0.208 ± 0.014 |
| RandomForest | BASE+LOCAL | 0.536 ± 0.039 | 0.553 ± 0.025 | 0.483 ± 0.034 | 0.212 ± 0.016 |

LogicOnly emette valori 0/1: AP e Brier si riferiscono a tali valori, non a probabilità calibrate. La soglia dei classificatori è quella predefinita (0,5); la selezione interna ottimizza F1 macro.

## Contributo della conoscenza

| Modello | Confronto | Δ F1 macro | Fold con Δ > 0 |
|---|---|---:|---:|
| LogisticRegression | BASE+KB minus BASE | +0.041 ± 0.047 | 8/10 |
| LogisticRegression | BASE+KB minus BASE+LOCAL | +0.013 ± 0.046 | 7/10 |
| RandomForest | BASE+KB minus BASE | +0.031 ± 0.053 | 7/10 |
| RandomForest | BASE+KB minus BASE+LOCAL | +0.038 ± 0.042 | 8/10 |
| GradientBoosting | BASE+KB minus BASE | +0.072 ± 0.050 | 9/10 |
| GradientBoosting | BASE+KB minus BASE+LOCAL | +0.041 ± 0.035 | 9/10 |

Per LogisticRegression, aggiungere la BK alla baseline con aggregazioni aumenta F1 macro in media di 1.30 punti percentuali; il miglioramento compare in 7 dei 10 fold. Questo è un risultato descrittivo del benchmark, senza una conclusione di significatività statistica.

Per RandomForest, aggiungere la BK alla baseline con aggregazioni aumenta F1 macro in media di 3.78 punti percentuali; il miglioramento compare in 8 dei 10 fold. Questo è un risultato descrittivo del benchmark, senza una conclusione di significatività statistica.

Per GradientBoosting, aggiungere la BK alla baseline con aggregazioni aumenta F1 macro in media di 4.07 punti percentuali; il miglioramento compare in 9 dei 10 fold. Questo è un risultato descrittivo del benchmark, senza una conclusione di significatività statistica.


Il confronto con BASE+LOCAL isola il contributo delle feature relazionali rispetto ad aggregazioni globali degli stessi sensori. Un Δ negativo o instabile costituisce un limite osservato: non si assume che aggiungere conoscenza migliori sempre la previsione.

## Ragionamento

Accordo con simulatore indipendente: 960/960 casi.

| Misura per snapshot | Media | Dev. standard |
|---|---:|---:|
| input_facts | 16.276042 | 4.180975 |
| closure_facts | 84.907292 | 29.250647 |
| rounds | 4.806250 | 0.921283 |
| matches | 3874.431250 | 2727.022394 |
| seconds | 0.005923 | 0.003894 |
| derived_down | 3.770833 | 3.649044 |

## Ricerca del ripristino

| Strategia | Guasti | Casi | Costo | Eccesso su ottimo | Stati espansi | Secondi |
|---|---:|---:|---:|---:|---:|---:|
| ucs | 2 | 21 | 2.048 ± 2.819 | 0.000 ± 0.000 | 1.762 ± 0.944 | 0.000409 ± 0.000305 |
| ucs | 4 | 21 | 6.190 ± 4.191 | 0.000 ± 0.000 | 5.048 ± 2.617 | 0.002699 ± 0.003040 |
| ucs | 6 | 18 | 7.167 ± 5.854 | 0.000 ± 0.000 | 12.667 ± 12.228 | 0.006096 ± 0.006168 |
| cheapest | 2 | 21 | 2.143 ± 3.054 | 0.095 ± 0.436 | 1.667 ± 0.730 | 0.000376 ± 0.000228 |
| cheapest | 4 | 21 | 12.000 ± 7.931 | 5.810 ± 4.434 | 3.619 ± 1.396 | 0.001543 ± 0.001204 |
| cheapest | 6 | 18 | 17.167 ± 13.017 | 10.000 ± 8.189 | 4.889 ± 2.246 | 0.002109 ± 0.001572 |

Ogni piano è verificato con il simulatore; ogni costo UCS è confrontato con enumerazione esaustiva indipendente. I casi in cui il servizio critico è già operativo sono inclusi e hanno costo ottimo zero. I tempi dipendono dalla macchina.

## Limiti e interpretazione

Questo è un benchmark sintetico, non una validazione su incidenti reali. Generatore e KB condividono deliberatamente la semantica delle dipendenze: il confronto misura l’utilità di una BK corretta nel mondo simulato, non dimostra validità esterna. Il futuro contiene estrazioni casuali e shock di zona non osservati. Le riparazioni assumono guasti confermati, effetto certo e costi additivi; non sono decise sulla base delle probabilità del classificatore.

La pipeline collega ragionamento e ML tramite le feature e collega ragionamento e ricerca tramite l’oracolo di stato. Il ML non guida la ricerca. Una futura estensione potrebbe valutare decisioni sotto incertezza.

Durata totale misurata: 123.5 s. Configurazione, hash e versioni: `run.json`.

I risultati del profilo smoke servono solo a verificare l’esecuzione e non sostituiscono il profilo full.

## Verifica SWI-Prolog

Motore: SWI-Prolog version 9.0.4 for x86_64-linux. Tutti i sei predicati derivati coincidono con Datalog su 960 fotografie. Le feature del dataset finale sono materializzate dall’output di SWI-Prolog.

## Rete bayesiana con struttura appresa

Sei variabili binarie; ordine prefissato, fino a due genitori, selezione locale BIC. Mediane, struttura e CPD sono stimate nel training. Alpha e limite dei genitori sono scelti nei fold interni; inferenza esatta anche con evidenza parziale.

| F1 macro | Balanced accuracy | Average precision | Brier ↓ |
|---:|---:|---:|---:|
| 0.401 ± 0.012 | 0.500 ± 0.000 | 0.416 ± 0.047 | 0.216 ± 0.015 |

La rete usa cinque osservabili selezionati a priori, quindi il confronto con i classificatori a 17 feature è descrittivo. È una rete bayesiana proposizionale su feature relazionali aggregate, non un modello probabilistico relazionale.

## Analisi aggiuntive

learning_curve_summary.csv riporta curve su frazioni 0,4 / 0,7 / 1,0 dei gruppi di training, sugli stessi test esterni, con configurazioni fissate a priori. importance_summary.csv riporta permutation importance sui test: tre permutazioni mediate entro fold, poi media e deviazione standard fra fold. Queste analisi sono diagnostiche e non selezionano feature o iperparametri. Le feature correlate possono dividere l’importanza; le permutazioni non provano causalità.

## Apprendimento non supervisionato e monitoraggio

K-Means identifica regimi nei sensori nominali (cpu, errors, latency), su dati separati dal task supervisionato. Scelta di k fra 2 e 7 mediante silhouette nel training; scaler e centroidi non leggono i test. Il 20% dei gruppi di training calibra la soglia al quantile 0,95 della distanza dal centro più vicino. Il riferimento nominale è un’assunzione: non si impara da uno storico contaminato da guasti.

Le anomalie diventano fatti alarm e la KB ne deduce le conseguenze. Si valutano guasti locali iniettati e indisponibilità critica su infrastrutture esterne; le verità del simulatore non partecipano al fit, alla silhouette o alla calibrazione. Split a gruppi indipendenti dal task predittivo, 5 fold × 2 ripetizioni nel profilo full. Baseline: soglie manuali e distanza da un singolo centro, con la stessa calibrazione.

| Metodo | F1 guasti locali | Falsi allarmi locali | F1 macro servizio critico | Balanced accuracy critica |
|---|---:|---:|---:|---:|
| FixedThreshold | 0.505 ± 0.036 | 0.000 ± 0.000 | 0.709 ± 0.050 | 0.664 ± 0.042 |
| SingleCenter | 0.773 ± 0.027 | 0.053 ± 0.008 | 0.847 ± 0.034 | 0.933 ± 0.015 |
| KMeans | 0.776 ± 0.027 | 0.052 ± 0.006 | 0.864 ± 0.035 | 0.941 ± 0.016 |

Il benchmark di monitoraggio assume due modi di carico nominale e perturbazioni additive note al simulatore. Le prestazioni dipendono da queste ipotesi. La silhouette misura separazione geometrica; il confronto con il centro unico verifica separatamente se più regimi aiutino il monitoraggio. Non si interpreta un cluster come classe di guasto e non si trasferiscono le etichette dei cluster fra fit differenti. Modelli, partizioni e predizioni sono salvati nei file monitoring_*.
