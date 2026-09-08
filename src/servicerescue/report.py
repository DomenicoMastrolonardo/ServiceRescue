"""Rapporto generato esclusivamente dai risultati effettivi del run."""
import numpy as np


def pm(row, metric):
    return f"{row[metric + '_mean']:.3f} ± {row[metric + '_std']:.3f}"


def report(output, metadata, summary, deltas, reasoning, planning):
    text = [
        '# Risultati ServiceRescue-KB', '',
        f"Profilo **{metadata['profile']}**, seed {metadata['seed']}; {metadata['samples']} esempi, "
        f"{metadata['groups']} infrastrutture; prevalenza positiva {metadata['prevalence']:.1%}.", '',
        f"CV esterna {metadata['outer']} fold × {metadata['repeats']} ripetizioni; "
        f"CV interna {metadata['inner']} fold. Media ± deviazione standard campionaria sui fold esterni.", '',
        'Gli stessi gruppi e split sono usati per ogni confronto. Le ripetizioni riusano il dataset: '
        'i fold non sono osservazioni indipendenti e la deviazione standard non è un intervallo di confidenza.', '',
        '| Modello | Feature | F1 macro | Balanced accuracy | Average precision | Brier ↓ |',
        '|---|---|---:|---:|---:|---:|',
    ]
    for r in summary:
        text.append(f"| {r['model']} | {r['feature_set']} | {pm(r, 'f1_macro')} | "
                    f"{pm(r, 'balanced_accuracy')} | {pm(r, 'average_precision')} | {pm(r, 'brier')} |")
    text += ['', 'LogicOnly emette valori 0/1: AP e Brier si riferiscono a tali valori, '
             'non a probabilità calibrate. La soglia dei classificatori è quella predefinita (0,5); '
             'la selezione interna ottimizza F1 macro.', '',
             '## Contributo della conoscenza', '',
             '| Modello | Confronto | Δ F1 macro | Fold con Δ > 0 |', '|---|---|---:|---:|']
    for r in deltas:
        text.append(f"| {r['model']} | {r['comparison']} | "
                    f"{r['f1_delta_mean']:+.3f} ± {r['f1_delta_std']:.3f} | {r['positive_folds']}/{r['n_folds']} |")
    text.append('')
    for r in deltas:
        if r['comparison'] == 'BASE+KB minus BASE+LOCAL':
            direction = 'aumenta' if r['f1_delta_mean'] > 0 else 'diminuisce'
            text.append(f"Per {r['model']}, aggiungere la BK alla baseline con aggregazioni "
                        f"{direction} F1 macro in media di {abs(r['f1_delta_mean'])*100:.2f} punti "
                        f"percentuali; il miglioramento compare in {r['positive_folds']} "
                        f"dei {r['n_folds']} fold. Questo è un risultato descrittivo del benchmark, "
                        'senza una conclusione di significatività statistica.')
            text.append('')
    text += ['', 'Il confronto con BASE+LOCAL isola il contributo delle feature relazionali rispetto '
             'ad aggregazioni globali degli stessi sensori. Un Δ negativo o instabile costituisce '
             'un limite osservato: non si assume che aggiungere conoscenza migliori sempre la previsione.', '',
             '## Ragionamento', '',
             f"Accordo con simulatore indipendente: {sum(r['oracle_agreement'] for r in reasoning)}/{len(reasoning)} casi.", '',
             '| Misura per snapshot | Media | Dev. standard |', '|---|---:|---:|']
    for key in ['input_facts', 'closure_facts', 'rounds', 'matches', 'seconds', 'derived_down']:
        vals = [r[key] for r in reasoning]
        text.append(f'| {key} | {np.mean(vals):.6f} | {np.std(vals, ddof=1):.6f} |')
    text += ['', '## Ricerca del ripristino', '',
             '| Strategia | Guasti | Casi | Costo | Eccesso su ottimo | Stati espansi | Secondi |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for r in planning:
        text.append(f"| {r['strategy']} | {r['n_failures']} | {r['cases']} | {pm(r, 'cost')} | "
                    f"{pm(r, 'excess_cost')} | {pm(r, 'expanded')} | "
                    f"{r['seconds_mean']:.6f} ± {r['seconds_std']:.6f} |")
    text += ['', 'Ogni piano è verificato con il simulatore; ogni costo UCS è confrontato con '
             'enumerazione esaustiva indipendente. I casi in cui il servizio critico è già operativo '
             'sono inclusi e hanno costo ottimo zero. I tempi dipendono dalla macchina.', '',
             '## Limiti e interpretazione', '',
             'Questo è un benchmark sintetico, non una validazione su incidenti reali. Generatore '
             'e KB condividono deliberatamente la semantica delle dipendenze: il confronto misura '
             'l’utilità di una BK corretta nel mondo simulato, non dimostra validità esterna. '
             'Il futuro contiene estrazioni casuali e shock di zona non osservati. '
             'Le riparazioni assumono guasti confermati, effetto certo e costi additivi; '
             'non sono decise sulla base delle probabilità del classificatore.', '',
             'La pipeline collega ragionamento e ML tramite le feature e collega ragionamento '
             'e ricerca tramite l’oracolo di stato. Il ML non guida la ricerca. '
             'Una futura estensione potrebbe valutare decisioni sotto incertezza.', '',
             f"Durata totale misurata: {metadata['seconds']:.1f} s. Configurazione, hash e versioni: `run.json`.", '',
             'I risultati del profilo smoke servono solo a verificare l’esecuzione e non sostituiscono il profilo full.', '']
    text += ['## Verifica SWI-Prolog', '',
             f"Motore: {metadata['prolog']['engine']}. Tutti i sei predicati derivati coincidono "
             f"con Datalog su {metadata['prolog']['all_predicates_agreement']} fotografie. "
             'Le feature del dataset finale sono materializzate dall’output di SWI-Prolog.', '',
             '## Rete bayesiana con struttura appresa', '',
             'Sei variabili binarie; ordine prefissato, fino a due genitori, selezione locale BIC. '
             'Mediane, struttura e CPD sono stimate nel training. Alpha e limite dei genitori '
             'sono scelti nei fold interni; inferenza esatta anche con evidenza parziale.', '',
             '| F1 macro | Balanced accuracy | Average precision | Brier ↓ |',
             '|---:|---:|---:|---:|',
             '| ' + ' | '.join(pm(metadata['bayesian'], m) for m in
                                ['f1_macro', 'balanced_accuracy', 'average_precision', 'brier']) + ' |', '',
             'La rete usa cinque osservabili selezionati a priori, quindi il confronto con i '
             'classificatori a 17 feature è descrittivo. È una rete bayesiana proposizionale '
             'su feature relazionali aggregate, non un modello probabilistico relazionale.', '',
             '## Analisi aggiuntive', '',
             'learning_curve_summary.csv riporta curve su frazioni 0,4 / 0,7 / 1,0 dei gruppi '
             'di training, sugli stessi test esterni, con configurazioni fissate a priori. '
             'importance_summary.csv riporta permutation importance sui test: tre permutazioni '
             'mediate entro fold, poi media e deviazione standard fra fold. Queste analisi '
             'sono diagnostiche e non selezionano feature o iperparametri. Le feature correlate '
             'possono dividere l’importanza; le permutazioni non provano causalità.', '',
             '## Apprendimento non supervisionato e monitoraggio', '',
             'K-Means identifica regimi nei sensori nominali (cpu, errors, latency), su dati separati '
             'dal task supervisionato. Scelta di k fra 2 e 7 mediante silhouette nel training; '
             'scaler e centroidi non leggono i test. Il 20% dei gruppi di training calibra la '
             'soglia al quantile 0,95 della distanza dal centro più vicino. Il riferimento nominale '
             'è un’assunzione: non si impara da uno storico contaminato da guasti.', '',
             'Le anomalie diventano fatti alarm e la KB ne deduce le conseguenze. Si valutano '
             'guasti locali iniettati e indisponibilità critica su infrastrutture esterne; '
             'le verità del simulatore non partecipano al fit, alla silhouette o alla calibrazione. '
             'Split a gruppi indipendenti dal task predittivo, 5 fold × 2 ripetizioni nel profilo full. '
             'Baseline: soglie manuali e distanza da un singolo centro, con la stessa calibrazione.', '',
             '| Metodo | F1 guasti locali | Falsi allarmi locali | F1 macro servizio critico | Balanced accuracy critica |',
             '|---|---:|---:|---:|---:|']
    for row in metadata['monitoring']['summary']:
        text.append('| ' + row['method'] + ' | ' + ' | '.join(pm(row, metric) for metric in
                    ['local_f1', 'local_false_alarm_rate', 'critical_f1_macro', 'critical_balanced_accuracy']) + ' |')
    text += ['', 'Il benchmark di monitoraggio assume due modi di carico nominale e perturbazioni '
             'additive note al simulatore. Le prestazioni dipendono da queste ipotesi. '
             'La silhouette misura separazione geometrica; il confronto con il centro unico '
             'verifica separatamente se più regimi aiutino il monitoraggio. Non si interpreta '
             'un cluster come classe di guasto e non si trasferiscono le etichette dei cluster '
             'fra fit differenti. Modelli, partizioni e predizioni sono salvati nei file monitoring_*.', '']
    (output / 'REPORT.md').write_text('\n'.join(text), encoding='utf-8')
