"""Compila i soli segnaposto del template, mantenendo titoli e formattazione.

Nessuna dipendenza esterna. Tabelle lette dagli artefatti verificati del run full.
"""
import argparse
from copy import deepcopy
import csv
import io
from pathlib import Path
import re
import statistics
from xml.etree import ElementTree as ET
from zipfile import ZipFile
import json

ROOT = Path(__file__).resolve().parents[1]
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS = {'w': W}


def tag(name):
    return '{' + W + '}' + name


def sub(parent, name, attrs=None, text=None):
    node = ET.SubElement(parent, tag(name), {tag(k): str(v) for k, v in (attrs or {}).items()})
    node.text = text
    return node


def rows(name, folder='full'):
    with (ROOT / 'results' / folder / name).open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def pm(row, metric, digits=3):
    return f"{float(row[metric + '_mean']):.{digits}f} ± {float(row[metric + '_std']):.{digits}f}".replace('.', ',')


def table(header, data, widths=None):
    return {'table': [header, *data], 'widths': widths}


def code(text):
    return {'code': text}


def text_of(element):
    return ''.join(t.text or '' for t in element.findall('.//w:t', NS))


def fill_content():
    run = json.loads((ROOT / 'results/full/run.json').read_text())
    if run['status'] != 'complete' or run['seed'] != 42:
        raise ValueError('Il testo delle conclusioni richiede il run completo seed 42')
    metrics = rows('cv_summary.csv')
    names = {'LogisticRegression': 'Logistica', 'RandomForest': 'Random Forest',
             'GradientBoosting': 'Gradient Boosting', 'LogicOnly': 'Sola logica', 'DummyPrior': 'Prior'}
    protocol = json.loads((ROOT / 'results/scenarios/protocol.json').read_text())
    if protocol['status'] != 'complete' or protocol['samples_total'] != 2880:
        raise ValueError('Completare e auditare i tre dataset prima di produrre la relazione')
    scenarios = rows('datasets.csv', 'scenarios')
    scenario_metrics = rows('cv_summary.csv', 'scenarios')
    scenario_deltas = [r for r in rows('ablation_deltas.csv', 'scenarios')
                       if r['comparison'] == 'BASE+KB minus BASE+LOCAL']
    by_scenario = {(r['scenario'], r['model'], r['feature_set']): r for r in scenario_metrics}
    monitoring_deltas = []
    for scenario, folder in [('standard', 'full'), ('redundant', 'full_redundant'), ('dense', 'full_dense')]:
        folds = rows('monitoring_folds.csv', folder)
        reference = {(r['repeat'], r['fold']): float(r['critical_f1_macro'])
                     for r in folds if r['method'] == 'SingleCenter'}
        diffs = [float(r['critical_f1_macro']) - reference[(r['repeat'], r['fold'])]
                 for r in folds if r['method'] == 'KMeans']
        monitoring_deltas.append([scenario,
                                 f'{statistics.mean(diffs):+.3f} ± {statistics.stdev(diffs):.3f}'.replace('.', ','),
                                 f'{sum(d > 0 for d in diffs)}/{len(diffs)}'])
    metric_tables = [table(['Modello', 'Feature', 'F1 macro', 'Balanced accuracy'],
                           [[names[r['model']], r['feature_set'], pm(r, 'f1_macro'), pm(r, 'balanced_accuracy')] for r in metrics]),
                     table(['Modello', 'Feature', 'Average precision', 'Brier'],
                           [[names[r['model']], r['feature_set'], pm(r, 'average_precision'), pm(r, 'brier')] for r in metrics])]
    deltas = [r for r in rows('ablation_deltas.csv') if r['comparison'] == 'BASE+KB minus BASE+LOCAL']
    repair = {(r['strategy'], int(r['n_failures'])): r for r in rows('planning_summary.csv')}
    reasoning = rows('reasoning_cases.csv')
    reasoning_table = []
    for field, label in [('input_facts', 'Fatti iniziali'), ('closure_facts', 'Fatti nella chiusura'),
                         ('rounds', 'Iterazioni produttive'), ('matches', 'Tentativi di unificazione'),
                         ('seconds', 'Tempo Datalog (s)')]:
        values = [float(r[field]) for r in reasoning]
        reasoning_table.append([label, f'{statistics.mean(values):.6f}'.replace('.', ','),
                                f'{statistics.stdev(values):.6f}'.replace('.', ',')])
    network_summary = rows('bayesian_summary.csv')[0]
    networks = json.loads((ROOT / 'results/full/bayesian_networks.json').read_text())
    prior = [n['prior'][1] for n in networks]
    posterior = [n['query']['posterior'][1] for n in networks]
    importance = rows('importance_summary.csv')
    top_importances = []
    for name in ['LogisticRegression', 'RandomForest', 'GradientBoosting']:
        best = max((r for r in importance if r['model'] == name), key=lambda r: float(r['f1_decrease_mean']))
        top_importances.append([names[name], best['feature'], pm(best, 'f1_decrease')])
    rules = '''edge(C,S,D) :- requires(C,S,D).
edge(C,S,A) :- replicas(C,S,A,_).
edge(C,S,B) :- replicas(C,S,_,B).
reach(C,S,D) :- edge(C,S,D).
reach(C,S,D) :- edge(C,S,M), reach(C,M,D).
down(C,S) :- alarm(C,S).
down(C,S) :- requires(C,S,D), down(C,D).
down(C,S) :- replicas(C,S,A,B), down(C,A), down(C,B).
critical_down(C,S) :- critical(C,S), down(C,S).
exposed(C,S,D) :- reach(C,S,D), alarm(C,D).
degraded(C,S) :- replicas(C,S,A,_), down(C,A).
degraded(C,S) :- replicas(C,S,_,B), down(C,B).'''
    return {
        0: ['ServiceRescue-KB'],
        6: [{'bold': 'https://github.com/DomenicoMastrolonardo/ServiceRescue'}],
        12: [
            'Il progetto affronta l’analisi dei guasti in infrastrutture composte da servizi informatici interdipendenti. '
            'Un servizio critico può risultare indisponibile per una dipendenza indiretta, mentre una replica sana '
            'può impedirne il guasto. Si studiano tre problemi collegati: derivare le conseguenze delle anomalie '
            'osservate, prevedere l’indisponibilità futura del servizio critico e individuare riparazioni a costo minimo '
            'quando i guasti sono confermati.',
            'Il dominio è simulato mediante un generatore originale: 120 infrastrutture di 10–18 nodi, ciascuna '
            'osservata in otto scenari, per 960 esempi. Gli scenari condividono la topologia entro infrastruttura '
            'ma non formano una serie temporale. I dati sintetici consentono oracoli di verifica e riproducibilità; '
            'i risultati non costituiscono una validazione su incidenti reali.'
            ' La valutazione è estesa a due ulteriori dataset, ridondante e denso: '
            'in totale 2.880 esempi di 360 infrastrutture appartenenti a tre famiglie dello stesso dominio.'
        ],
        15: [
            'ServiceRescue-KB è un KBS che rappresenta dipendenze obbligatorie e repliche con clausole di Horn. '
            'SWI-Prolog ricava la chiusura logica; un interprete Datalog indipendente verifica le deduzioni e '
            'fornisce spiegazioni. Le relazioni derivate diventano Background Knowledge per tre classificatori '
            'supervisionati e una rete bayesiana. Il ragionamento verifica inoltre gli stati di una ricerca '
            'a costo uniforme delle riparazioni. Il ML non guida la ricerca: quest’ultima assume guasti confermati '
            'e azioni deterministiche. Un modulo non supervisionato impara regimi nominali con K-Means '
            'e produce anomalie locali da propagare nella KB. Questo ramo usa dati di monitoraggio '
            'separati dal dataset di previsione futura.',
            'La prima sezione tratta rappresentazione, inferenza e ricerca; la seconda apprendimento con BK '
            'supervisionato e non supervisionato con valutazione; la terza ragionamento probabilistico. Il dataset, gli split, le predizioni, '
            'i parametri scelti e gli hash sono conservati in results/full/. La struttura include '
            'src/main.py, serviceProlog.py, supervisedLearning.py, bayesianNetwork.py, extraAnalysis.py e '
            'unsupervisedLearning.py, oltre a kb/, data/raw/, data/processed/, results/tables/ e results/figures/. '
            'Il codice riutilizzabile è nel pacchetto src/servicerescue/; tools/repairSearch.py '
            'espone separatamente il benchmark aggiuntivo delle riparazioni.'
        ],
        18: ['Argomento 1 — Rappresentazione della conoscenza e ragionamento automatico: clausole di Horn, '
             'Datalog positivo, Prolog con tabling, ricorsione e congiunzioni; ricerca a costo uniforme per il ripristino.'],
        19: ['Argomento 2 — Apprendimento: K-Means, silhouette e rilevamento di anomalie; '
             'regressione logistica, Random Forest e Gradient Boosting con Background Knowledge, '
             'confronto ablativo e cross-validation annidata a gruppi.'],
        20: ['Argomento 3 — Apprendimento e ragionamento sotto incertezza: struttura di rete bayesiana '
             'appresa con BIC, stima delle CPD e inferenza esatta con evidenza parziale.'],
        21: ['Integrazione trasversale — La stessa conoscenza delle dipendenze alimenta predizione e '
             'verifica degli stati nella ricerca; simulatori distinti controllano deduzioni e piani.'],
        22: ['Le aree affrontate sono rappresentazione logica, inferenza, ricerca, apprendimento supervisionato e non supervisionato '
             'e modelli grafici probabilistici. La rete bayesiana è proposizionale su feature relazionali aggregate, '
             'non un modello probabilistico relazionale o un’ontologia OWL.'],
        28: [
            'La KB contiene dodici regole, quattro predicati di ingresso e sei predicati derivati. '
            'In Prolog il primo argomento C identifica la fotografia, impedendo deduzioni tra esempi '
            'anche quando i nomi locali dei nodi coincidono. Le regole sono esterne al codice Python: '
            'kb/kb.pl per SWI-Prolog e kb/rules.json per il verificatore Datalog.',
            table(['Predicato', 'Semantica'], [
                ['requires(C,S,D)', 'La disponibilità di S richiede D: un guasto di D si propaga a S.'],
                ['replicas(C,S,A,B)', 'S richiede almeno una fra A e B; la perdita di entrambe causa un guasto.'],
                ['alarm(C,S)', 'Guasto assunto nello scenario logico corrente.'],
                ['critical(C,S)', 'Servizio da ripristinare per raggiungere l’obiettivo.']], [2600, 6426]),
            'Più requisiti sullo stesso servizio devono essere soddisfatti insieme. Le repliche possono '
            'condividere dipendenze: una causa remota può quindi renderle entrambe indisponibili. Nel dataset '
            'gli allarmi derivano dai sensori e rappresentano ipotesi qualitative; nella ricerca indicano guasti confermati.'
        ],
        31: [
            'SWI-Prolog 9.0.4 esegue realmente la KB tramite subprocess Python. I predicati reach/3 e down/2 '
            'usano tabling, quindi risoluzione SLG [2]. Il verificatore Python implementa un frammento Datalog '
            'positivo mediante unificazione, join e punto fisso sincrono [1]. heapq gestisce la frontiera UCS. '
            'Non si presentano questi algoritmi standard come contributi originali.'
        ],
        32: [
            'Il contributo specifico è la formalizzazione delle dipendenze, il generatore, le feature relazionali '
            'e il confronto automatico fra Prolog, Datalog e simulatore. L’ambiente verificato usa Python 3.12.3 '
            '(codice compatibile con Python ≥3.10). Installare SWI-Prolog e le dipendenze in requirements.txt; '
            'su Linux: sudo apt-get install swi-prolog-nox. Dalla radice del progetto:',
            code('python -m venv .venv\n# Attivare .venv secondo il proprio sistema operativo\n'
                 'python -m pip install -r requirements.txt\npython src/main.py\n'
                 'python main.py demo\npython -m unittest discover -s tests -v\n'
                 'python tests/audit_results.py results/full\n'
                 'python tools/evaluate_scenarios.py\npython tools/build_documentation.py')
        ],
        35: [
            'Le dodici regole eseguibili sono riportate integralmente. reach descrive la raggiungibilità '
            'strutturale, mentre down rispetta il vincolo delle repliche: un percorso verso un guasto non '
            'basta a dimostrare indisponibilità. degraded significa almeno una replica indisponibile '
            'e rimane vero se sono guaste entrambe.',
            code(rules),
            'Il motore Datalog non ammette simboli funzione o negazione; richiede fatti ground e variabili '
            'della testa presenti nel corpo. A ogni iterazione produttiva aggiunge fatti a un insieme finito. '
            'I cicli quindi terminano e un ciclo senza allarme non genera spontaneamente un guasto. '
            'La prima giustificazione usa solo premesse di iterazioni precedenti, producendo spiegazioni '
            'acicliche; non enumera tutte le cause minime. In Prolog i fatti restano immutabili durante '
            'ogni invocazione e le tabelle non sopravvivono al processo.',
            'Le feature finali sono materializzate dalle risposte Prolog e confrontate su tutti i sei predicati '
            'con Datalog. Non esiste un fallback a feature nulle. Soglie, costi e inventario sono espliciti; '
            'l’assenza di critical_down è usata come obiettivo sotto assunzione di mondo chiuso e inventario '
            'completo, senza implicare disponibilità reale in presenza di informazioni mancanti.',
            'Complessità del verificatore: con N nodi, E archi, R gruppi di repliche e I iterazioni, '
            'reach può contenere O(N²) coppie. L’indicizzazione è solo per predicato. I costi conservativi '
            'per iterazione sono O(E N²) per la ricorsione reach, O(E N) per le dipendenze, O(R N) per '
            'le repliche e O(N³) per il join fra reach e allarmi. Il totale è O(I·(E N² + N³ + R N)). '
            'Nei grafi generati E,R=O(N), I=O(N) e spazio O(N²), dando un limite conservativo O(N⁴). '
            'Questo descrive il motore naive implementato, non un limite intrinseco di Datalog o di SWI-Prolog.',
            'Ricerca: uno stato è l’insieme canonico dei guasti locali già riparati. Ogni azione rimuove '
            'un guasto confermato e costa un intero positivo fra 1 e 9. UCS minimizza la somma dei costi '
            'e verifica l’obiettivo con le quattro regole Datalog per down e critical_down. Tutti gli ordini '
            'che portano allo stesso insieme hanno lo stesso costo, quindi è corretto deduplicare già '
            'all’inserimento in coda. Con k guasti esistono al massimo 2^k stati e O(k·2^k) transizioni. '
            'La baseline cheapest ripara prima il guasto meno costoso, anche se irrilevante per l’obiettivo.'
        ],
        38: [
            'La KB è verificata su tutte le 960 fotografie: SWI-Prolog e Datalog coincidono su tutti i sei '
            'predicati derivati; i guasti coincidono anche con il simulatore procedurale. Le seguenti misure '
            'sono medie e deviazioni standard campionarie per fotografia del verificatore Datalog.',
            table(['Misura', 'Media', 'Dev. standard'], reasoning_table, [4000, 2513, 2513]),
            f"SWI-Prolog completa avvio, caricamento ed esportazione in {run['prolog']['seconds']:.3f} s "
            'sulla macchina usata: tale tempo non è direttamente confrontabile con quello della sola '
            'inferenza Datalog. I dati del run non dimostrano scalabilità industriale.',
            'La ricerca è valutata su 60 casi con 8/12/16 nodi e 2/4/6 guasti. Tutti i 120 piani delle '
            'due strategie sono validi; i 60 piani UCS hanno costo uguale all’oracolo esaustivo. '
            'Sono inclusi 16 casi già operativi, con ottimo zero. Costi medi ± deviazioni standard:',
            table(['Guasti', 'Casi', 'Costo UCS', 'Costo cheapest', 'Eccesso cheapest'],
                  [[str(k), repair[('ucs', k)]['cases'], pm(repair[('ucs', k)], 'cost'),
                    pm(repair[('cheapest', k)], 'cost'), pm(repair[('cheapest', k)], 'excess_cost')]
                   for k in [2, 4, 6]], [850, 700, 2450, 2450, 2576]),
            'Con sei guasti UCS espande 12,667 ± 12,228 stati contro 4,889 ± 2,246 della baseline. '
            'La ricerca ottimale risparmia costo, pagando una maggiore esplorazione. Nella demo riparare '
            'power costa 4 e ripristina portal attraverso db_a e api; cheapest ripara prima db_b, '
            'spende 6 in totale e non migliora l’obiettivo. I test comprendono cause condivise, repliche, '
            'cicli, contesti separati e confronto esaustivo: la correttezza riguarda il dominio formalizzato.'
            ' Nei tre dataset l’accordo Prolog/Datalog è verificato su tutte le 2.880 fotografie. '
            'Le misure seguenti mostrano come varia il lavoro del verificatore; dimensione e densità '
            'variano insieme nello scenario dense, quindi non si isola un singolo fattore:',
            table(['Scenario', 'Fatti nella chiusura', 'Iterazioni', 'Unificazioni tentate'],
                  [[r['scenario'], pm(r, 'closure_facts'), pm(r, 'rounds'), pm(r, 'matches')]
                   for r in rows('reasoning_summary.csv', 'scenarios')])
        ],
        44: [
            'Il task supervisionato è la classificazione binaria dell’indisponibilità futura del servizio '
            'critico, con prevalenza positiva 33,0%. Il futuro è simulato separatamente dagli allarmi '
            'correnti, quindi il target non è una copia di root_down. Si confrontano tre famiglie di '
            'modelli su BASE, BASE+LOCAL e BASE+KB, più DummyPrior e LogicOnly. BASE+LOCAL controlla '
            'se il guadagno dipende semplicemente dall’accesso ai sensori degli altri nodi.'
        ],
        47: [
            'NumPy 2.2.6 e SciPy 1.15.3 supportano calcoli e generazione; scikit-learn 1.7.2 fornisce '
            'LogisticRegression, RandomForestClassifier, GradientBoostingClassifier, DummyClassifier, '
            'Pipeline, StandardScaler, GridSearchCV, StratifiedGroupKFold, KMeans e silhouette_score [3]. '
            'Matplotlib 3.10.6 produce figure aggregate. Non sono richiesti pandas o servizi remoti.'
        ],
        48: [
            'L’implementazione specifica collega le query logiche alle feature e conserva gli indici globali '
            'di tutte le partizioni. I dati vengono salvati in JSON/CSV; l’audit ricalcola le metriche '
            'dalle predizioni e controlla hash, disgiunzione dei gruppi e copertura dei test. '
            'Il clustering usa sensori nominali senza etichette di guasto: stima regimi e distanze '
            'per generare fatti alarm. Non raggruppa le classi già note del task supervisionato '
            'e non interpreta i cluster come tipi di guasto. Il confronto con un unico centro '
            'serve a valutare se la distinzione fra regimi sia utile al monitoraggio.'
        ],
        51: [
            'Monitoraggio non supervisionato: per ciascuna topologia si generano otto fotografie '
            'nominali, ciascuna con misure per tutti i nodi. Le feature sono cpu, errors e latency. '
            'Il carico elevato ha probabilità 0,45; le medie sono rispettivamente (0,72;0,08;110) '
            'e (0,25;0,03;45), con rumore normale indipendente di deviazione (0,045;0,012;8). '
            'CPU ed errors sono troncati in [0;1] e latency ad almeno 1. La modalità di carico '
            'non è annotata nei file di fit. La disponibilità di uno storico nominale attendibile '
            'è un’assunzione esplicita, quindi non si rivendica apprendimento da storico contaminato.',
            'Per il solo test, ciascun nodo subisce un guasto locale con probabilità 0,08: '
            'i sensori aumentano di (0,16;0,20;90), con troncamento delle prime due componenti. '
            'Il simulatore propaga i guasti veri sulla topologia e conserva la verità in '
            'monitoring_truth.json; fit, silhouette e calibrazione non leggono questo file. '
            'Gli stream nominale e guasti usano seed+700 e seed+701. Le equazioni sono ipotesi '
            'sintetiche fissate prima del confronto e rendono il compito deliberatamente controllato.',
            'Valutazione del monitoraggio: cinque partizioni esterne delle infrastrutture, ripetute '
            'due volte con seed+710+r, indipendenti dagli split della previsione futura. In ogni '
            'training esterno il 20% dei gruppi (arrotondato per eccesso) calibra le distanze; '
            'gli altri gruppi stimano StandardScaler e K-Means. Si confrontano k=2,…,7, con '
            'n_init=10: fit su al massimo 2.000 nodi campionati dal training e silhouette sugli '
            'stessi al massimo 400 nodi di tale sottoinsieme per ogni k. Si massimizza la '
            'silhouette; a parità vince k minore. Questi limiti contengono il costo, senza '
            'selezionare nodi per etichetta. Il costo di Lloyd è O(n·k·d·T) per inizializzazione '
            'e la silhouette richiede O(m²·d), con d=3 e m≤400.',
            'Un nodo è anomalo se la distanza euclidea standardizzata dal centro più vicino '
            'supera il quantile 0,95 delle distanze nominali di calibrazione. Tale quantile '
            'è prefissato e non garantisce esattamente il 5% di falsi allarmi su un nuovo test. '
            'Le anomalie entrano nelle regole Datalog down e critical_down; la propagazione '
            'è verificata dal simulatore indipendente. Si confrontano le soglie manuali '
            '(errors≥0,60 o cpu≥0,85) e SingleCenter, con un centro medio e la stessa calibrazione. '
            'Il confronto misura il contributo della modellazione di più regimi. I modelli '
            'e gli split sono in monitoring_models.json; gli identificativi dei cluster sono locali '
            'al fit e i loro profili non vengono mediati come se fossero classi stabili.',
            'Generatore fissato prima della valutazione: i primi tre nodi non hanno dipendenze; ogni '
            'nodo successivo sceglie due predecessori distinti. Con probabilità 0,45 li usa come repliche; '
            'altrimenti richiede il primo e, con probabilità 0,35, anche il secondo. Gli archi puntano a '
            'indici inferiori, quindi le topologie generate sono DAG; il motore è testato separatamente '
            'anche sui cicli. Il nodo finale è critico. Nodi non raggiungibili costituiscono informazione '
            'irrilevante per il suo guasto e non vengono eliminati.',
            'Per fotografia, stress comune uniforme in [0;0,32] e severità individuale Beta(1,3;4,5) '
            'più stress, troncata in [0;1]. I sensori sono: errors=severità+rumore normale σ=0,09; '
            'cpu=0,2+0,72×severità+rumore σ=0,09; latency=25+180×severità+rumore σ=12. '
            'Cpu ed errors sono troncati in [0;1], latency ha minimo 1. Sono grandezze del benchmark, '
            'non soglie operative validate.',
            'Gli allarmi scattano per errors≥0,60 oppure cpu≥0,85. Il guasto futuro di un nodo ha '
            'probabilità 0,015+0,60×severità²; ciascuna delle tre zone può inoltre subire uno shock '
            'con probabilità 0,025 che guasta tutti i suoi nodi. Il simulatore propaga gli esiti secondo '
            'dipendenze e repliche. Severità, shock, esiti futuri e zone non entrano nelle feature. '
            'I coefficienti sono ipotesi del benchmark, non parametri ottimizzati sui test. '
            'Il seed è 42 e gli stream di topologia, osservazioni ed esiti sono separati.',
            'Sensibilità a più dataset: si conserva standard/42 e si aggiungono redundant/73 e '
            'dense/101, con configurazioni e seed fissati prima dei nuovi esperimenti. Ogni dataset '
            'ha 120 infrastrutture e otto fotografie per infrastruttura. Si variano ridondanza, '
            'dimensione e densità del grafo; sensori, futuro, KB, feature e griglie rimangono gli stessi. '
            'La probabilità della seconda dipendenza è condizionata alla scelta di non usare repliche. '
            'I valori estremi servono a distinguere scenari strutturali, non sono stime da dati reali:',
            table(['Scenario / seed', 'Nodi', 'P(repliche)', 'P(seconda dip.)', 'Prevalenza'],
                  [[f"{r['scenario']} / {r['seed']}", f"{r['min_nodes']}–{r['max_nodes']}",
                    r['replica_probability'], r['extra_dependency_probability'],
                    f"{float(r['prevalence']):.1%}"] for r in scenarios], [2050, 1050, 1700, 1900, 2326]),
            'Ogni dataset è valutato separatamente con CV annidata 5×2×3 e gruppi locali; '
            'non si addestra su una famiglia per testare su un’altra. Il confronto misura sensibilità '
            'alle distribuzioni simulate, non trasferimento fra domini o robustezza causale. '
            'Un seed per famiglia non separa l’effetto della configurazione da quello del campionamento. '
            'Tutti gli esiti sono conservati in results/full, results/full_redundant, results/full_dense; '
            'protocollo e sintesi complete sono in results/scenarios/.',
            table(['Insieme', 'Feature', 'Informazione'], [
                ['BASE (6)', 'root_cpu, root_errors, root_latency, n_nodes, n_requires, n_replicas', 'Sensori del nodo critico e dimensioni della topologia.'],
                ['BASE+LOCAL (11)', 'BASE + mean_cpu, max_cpu, mean_errors, max_errors, alarm_fraction', 'Aggregazioni di tutti i sensori, senza percorsi.'],
                ['BASE+KB (17)', 'BASE+LOCAL + root_down, down_fraction, reachable_fraction, exposed_fraction, reachable_down_fraction, degraded_fraction', 'Conseguenze e relazioni derivate dalla KB.']], [1600, 4200, 3226]),
            'Le frazioni exposed e reachable_down usano il numero di nodi raggiungibili, con '
            'denominatore minimo 1; le altre frazioni usano il numero totale di nodi. Gli identificativi, '
            'il gruppo, il target e i costi sono esclusi dagli input dei classificatori.',
            table(['Modello/componente', 'Griglia o impostazione', 'Motivazione'], [
                ['Logistica', 'C∈{0,1;1;10}; class_weight∈{None;balanced}; max_iter=2000', 'Regolarizzazione e bilanciamento scelti nel training interno.'],
                ['Random Forest', '60 alberi; max_depth∈{4;None}; min_samples_leaf∈{3;10}', 'Controllo della complessità entro un budget limitato.'],
                ['Gradient Boosting', '60 alberi; max_depth∈{1;2}; learning_rate∈{0,05;0,1}', 'Interazioni semplici e due intensità di aggiornamento.'],
                ['StandardScaler', 'Fit nella pipeline della logistica', 'Latency e frazioni hanno scale diverse.'],
                ['CV', '5 fold esterni × 2 ripetizioni; 3 interni; gruppi per infrastruttura', 'Separazione di tuning e test, con più partizioni.'],
                ['Classificazione', 'Soglia predefinita 0,5; scoring interno F1 macro', 'Nessuna scelta di soglia in base ai test esterni.']], [1950, 3500, 3576]),
            'Le griglie hanno 6/4/4 configurazioni per logistica/foresta/boosting. In entrambi i livelli '
            'StratifiedGroupKFold mantiene insieme tutte le fotografie della stessa infrastruttura; '
            'la stratificazione è approssimata sotto il vincolo dei gruppi. Tutti i confronti usano gli '
            'stessi split. Il codice rifiuta fold con una sola classe. Standardizzazione e pesi '
            'bilanciati sono stimati esclusivamente nel training; non si applicano SMOTE o selezioni '
            'globali di feature. Le feature logiche si materializzano prima degli split perché sono '
            'funzioni fisse della sola fotografia e non leggono etichette o statistiche di altri esempi.',
            'Curve diagnostiche: frazioni 0,4/0,7/1,0 dei gruppi di training sugli stessi test esterni. '
            'Configurazioni prefissate: logistica C=1 con class_weight=balanced; foresta 60 alberi, '
            'profondità 4 e foglia minima 3; boosting 60 alberi, profondità 2 e learning_rate=0,05. '
            'Le importanze usano tre permutazioni di ciascuna feature sul test, mediate entro fold '
            'e poi aggregate fra fold. Queste analisi non scelgono nuovi parametri o feature.'
        ],
        54: [
            'Monitoraggio: media e deviazione standard campionaria sui dieci test esterni '
            'di ciascuna famiglia. F1 locale riguarda la classe guasto; F1 macro critica riguarda '
            'l’indisponibilità del servizio dopo la propagazione nella KB. Le etichette sono '
            'impiegate soltanto per queste misure. La silhouette è un criterio geometrico di '
            'training, non sostituisce la verifica del compito finale:',
            table(['Scenario / metodo', 'F1 locale', 'Falsi allarmi', 'F1 macro critica'],
                  [[f"{r['scenario']} / {r['method']}", pm(r, 'local_f1'),
                    pm(r, 'local_false_alarm_rate'), pm(r, 'critical_f1_macro')]
                   for r in rows('monitoring_summary.csv', 'scenarios')], [2800, 2076, 2075, 2075]),
            table(['Scenario', 'Δ F1 macro critica: K-Means − centro unico', 'Fold Δ positivo'], monitoring_deltas),
            'I delta confrontano gli stessi test esterni. Un miglioramento medio piccolo, nullo '
            'o negativo limita la convenienza di usare più regimi; non si conclude che il '
            'clustering sia sempre necessario. Il suo ruolo nel prototipo è verificare questa '
            'ipotesi sul monitoraggio, oltre a produrre gli allarmi del ramo K-Means.',
            'La silhouette seleziona k=2 in tutti i 30 fit, coerentemente con i due modi del '
            'generatore; non è una scoperta sul funzionamento di sistemi reali. Rispetto al '
            'centro unico, il delta F1 macro critica è +0,016 ± 0,028 in standard, '
            '+0,015 ± 0,030 in redundant e −0,019 ± 0,044 in dense. I fold con delta positivo '
            'sono 7/10, 6/10 e 3/10. La segmentazione dei regimi offre quindi un vantaggio '
            'limitato e non uniforme. Nel grafo denso i falsi allarmi possono propagarsi '
            'a più servizi: è un’interpretazione plausibile, non un effetto isolato sperimentalmente.',
            'I profili dei centri per fold sono in results/tables/01_cluster_profiles.csv; '
            'la curva media con deviazione standard della silhouette in '
            'results/figures/01_silhouette_scores.png. Le predizioni e gli allarmi sono conservati '
            'e l’audit li ricostruisce da scaler, centroidi e soglie: controlla separazione di '
            'fit/calibrazione/test, effetti nella KB e metriche aggregate. La valutazione '
            'su guasti additivi artificiali non dimostra robustezza a drift, guasti silenziosi '
            'o a errori nello storico nominale.',
            'Per il dataset standard si riportano media e deviazione standard campionaria (ddof=1) sui dieci fold esterni, '
            'non risultati di un singolo run. Le ripetizioni riusano il dataset: i fold sono correlati '
            'e la deviazione standard non è un intervallo di confidenza. F1 macro guida il tuning; '
            'balanced accuracy, average precision e Brier descrivono aspetti complementari.',
            *metric_tables,
            'Per LogicOnly AP e Brier sono calcolati sugli score 0/1, non su probabilità calibrate. '
            'Il confronto più informativo per la conoscenza è BASE+KB meno BASE+LOCAL, calcolato '
            'sugli stessi split:',
            table(['Modello', 'Δ F1 macro, media ± dev. std.', 'Fold con Δ positivo'],
                  [[names[r['model']], pm(r, 'f1_delta'), f"{r['positive_folds']}/{r['n_folds']}"] for r in deltas]),
            'La KB migliora in media i tre classificatori rispetto alle aggregazioni globali: '
            'circa 1,3/3,8/4,1 punti percentuali per logistica/foresta/boosting. La variabilità '
            'dei delta impedisce di dichiarare un miglioramento garantito o statisticamente significativo. '
            'LogicOnly ottiene comunque il migliore F1 medio, 0,627: il progetto non dimostra che '
            'l’ibrido ML sia sempre preferibile alla sola logica. La foresta BASE+KB ha il Brier '
            'medio più basso fra i classificatori (0,208), mentre la logistica BASE+KB ha AP 0,509; '
            'ciò suggerisce utilità degli score graduati senza dimostrare utilità operativa.',
            'Curve: media ± deviazione standard sui test esterni, con configurazioni prefissate '
            'e training completo del fold (non i modelli selezionati dalla CV annidata):',
            table(['Modello', 'F1 training', 'F1 test esterno'],
                  [[names[r['model']], pm(r, 'train_f1'), pm(r, 'test_f1')] for r in rows('learning_curve_summary.csv') if float(r['fraction']) == 1.]),
            'I gap medi training/test sono circa 0,026, 0,110 e 0,095: nei modelli ad albero '
            'rimane un divario più ampio. La sintesi seguente mostra la feature con maggiore '
            'importanza media per ciascun modello; tutte le 17 sono conservate nei CSV:',
            table(['Modello', 'Feature', 'Riduzione F1 per permutazione'], top_importances),
            'Le importanze sono descrittive e non causali: feature correlate possono condividere '
            'il contributo, e permutazioni isolate possono violare dipendenze della KB. L’esperimento '
            'supervisionato produce 110 valutazioni e 21.120 predizioni; l’audit ne verifica '
            'copertura, gruppi e ricostruzione delle metriche. I grafici aggregati sono in results/figures/.'
            ' Questi valori si riferiscono al dataset standard. La tabella seguente confronta '
            'F1 macro, media ± deviazione standard dei dieci test esterni per ciascun dataset; '
            'non si mescolano i fold di famiglie differenti:',
            table(['Modello / feature', 'standard', 'redundant', 'dense'],
                  [[f"{names[model]} / {feature}",
                    *[pm(by_scenario[(scenario, model, feature)], 'f1_macro')
                      for scenario in ['standard', 'redundant', 'dense']]]
                   for model, feature in [(r['model'], r['feature_set']) for r in metrics]],
                  [2500, 2176, 2175, 2175]),
            table(['Modello', 'Scenario', 'Δ KB–LOCAL, F1', 'Fold Δ positivo'],
                  [[names[r['model']], r['scenario'], pm(r, 'f1_delta'),
                    f"{r['positive_folds']}/{r['n_folds']}" ] for r in scenario_deltas]),
            'Per le quattro metriche complete si conservano anche le sintesi CSV separate. '
            'Il confronto va letto insieme alla prevalenza e al prior: un F1 più alto in un dataset '
            'non dimostra che quel modello generalizzi meglio a tutti i contesti. Gli audit dei tre '
            'dataset controllano 330 valutazioni supervisionate e 63.360 predizioni esterne.'
        ],
        62: [
            'La rete bayesiana stima P(future_down | evidenza). Contiene sei variabili binarie: '
            'future_down, root_errors, mean_errors, root_down, exposed_fraction e degraded_fraction. '
            'Le ultime cinque indicano il superamento della mediana del training. Alcuni osservabili '
            'derivano dal ragionamento della KB; il target futuro non viene usato come evidenza. '
            'Struttura e CPD sono apprese, mentre le query ammettono anche evidenza parziale.'
        ],
        65: [
            'NumPy gestisce conteggi e tabelle, SciPy calcoli stabili in logaritmi, scikit-learn '
            'la selezione annidata [3]. Il modulo src/servicerescue/bayesian.py implementa ricerca '
            'BIC entro un ordine prefissato e inferenza per enumerazione.'
        ],
        66: [
            'L’implementazione compatta espone struttura, soglie, CPD e posteriori di ogni fold in '
            'bayesian_networks.json. I test controllano un arco predittivo noto, normalizzazione '
            'delle CPD e della congiunta, marginalizzazione, accordo fra query e predizione e '
            'assenza di modifiche del discretizzatore durante la previsione.'
        ],
        69: [
            'L’ordine topologico è fissato a priori: il target precede gli osservabili nell’ordine '
            'dichiarato. Per ogni nodo si enumerano sottoinsiemi dei predecessori fino al limite '
            'dei genitori. Il punteggio locale è log-verosimiglianza multinomiale meno '
            '0,5×numero_parametri×log(N); per un nodo binario con p genitori binari il numero '
            'di parametri liberi è 2^p. Il criterio decomponibile consente l’ottimo entro '
            'lo spazio vincolato dall’ordine, non fra tutti i DAG possibili.',
            'Le CPD usano smoothing: (conteggio+alpha)/(totale+2×alpha). La griglia interna '
            'combina alpha∈{0,5;1;2} e max_parents∈{1;2}, sei configurazioni. Mediane, '
            'struttura e parametri sono ristimati a ogni fit interno ed esterno. Gli split '
            'sono gli stessi della valutazione supervisionata, con infrastrutture separate '
            'e selezione basata su F1 macro. La soglia di decisione rimane 0,5.',
            'Con evidenza completa si valuta la fattorizzazione per entrambe le classi '
            'e si normalizza. Con evidenza parziale si enumerano i 64 assegnamenti e '
            'si marginalizzano le variabili non osservate. Le CPD positive evitano '
            'probabilità nulle senza fallback sulla classe più frequente. Gli archi '
            'sono statistici: la posizione del target nell’ordine non identifica cause fisiche.',
            'Con m variabili e al massimo due genitori vengono esaminati O(m³) insiemi '
            'candidati; il conteggio richiede O(N) per candidato, oltre alle piccole tabelle. '
            'L’inferenza per enumerazione costa O(m·2^m). Il limite a sei variabili '
            'rende praticabile l’inferenza esatta, ma restringe lo spazio del modello. '
            'Usare feature relazionali aggregate non rende questa rete un modello probabilistico relazionale.'
        ],
        72: [
            'Risultati della rete sul dataset standard, sui dieci fold esterni con tuning nei rispettivi training. '
            'Il numero di archi appresi è 8,5 ± 1,269:',
            table(['F1 macro', 'Balanced accuracy', 'Average precision', 'Brier'],
                  [[pm(network_summary, f) for f in ['f1_macro', 'balanced_accuracy', 'average_precision', 'brier']]]),
            'Alla soglia 0,5 la rete predice soltanto la classe maggioritaria: F1 e balanced '
            'accuracy coincidono con il prior. Gli score contengono qualche informazione '
            '(AP 0,416 e Brier 0,216), ma il modello non discrimina utilmente la classe positiva '
            'con la decisione adottata. Struttura vincolata, discretizzazione e aggregazione '
            'sono limiti plausibili, non cause isolate sperimentalmente. Non si modifica '
            'la soglia dopo aver visto i test per nascondere il risultato. Il confronto con '
            'classificatori a 17 feature è descrittivo, poiché la rete usa cinque osservabili.',
            'Query esatta con evidenza parziale, aggregata fra le dieci reti di training; '
            'si riporta P(future_down=1):',
            table(['Evidenza', 'Media', 'Dev. standard'], [
                ['Nessuna', f'{statistics.mean(prior):.3f}', f'{statistics.stdev(prior):.3f}'],
                ['root_down=1, exposed_fraction=1', f'{statistics.mean(posterior):.3f}', f'{statistics.stdev(posterior):.3f}']]),
            'I valori 1 indicano superamento della mediana del relativo training; le altre '
            'tre variabili sono marginalizzate. La variabilità dei posteriori non è una '
            'misura di accuratezza dello scenario. Le ulteriori 1.920 predizioni della rete '
            'sono conservate e auditate, incluse le soglie stimate sul solo training.'
            ' Le valutazioni aggiuntive usano lo stesso tuning annidato e producono la seguente '
            'sintesi per dataset; complessivamente vengono auditate 5.760 predizioni bayesiane:',
            table(['Scenario', 'F1 macro', 'Balanced accuracy', 'Average precision', 'Brier'],
                  [[r['scenario'], pm(r, 'f1_macro'), pm(r, 'balanced_accuracy'),
                    pm(r, 'average_precision'), pm(r, 'brier')]
                   for r in rows('bayesian_summary.csv', 'scenarios')], [1450, 1850, 1950, 1926, 1850])
        ],
        79: [
            'Il contributo più solido è la KB condivisa per deduzioni spiegabili e verifica degli stati '
            'nella ricerca: accordo completo dei motori sui casi valutati e piani UCS ottimi rispetto '
            'all’oracolo esaustivo. Nel dataset standard la BK migliora in media i tre classificatori '
            'rispetto a input comparabili, ma la sola logica rimane superiore in F1. La rete bayesiana '
            'dimostra apprendimento e inferenza con evidenza parziale, senza superiorità predittiva. '
            'La suite conta 26 test superati; gli audit confermano integrità dei file e metriche. '
            f"La pipeline dello scenario standard ha richiesto circa {run['seconds']:.1f} s sulla macchina usata.",
            'Nel monitoraggio, K-Means alimenta la KB con allarmi ricavati da uno storico '
            'nominale senza etichette di guasto. Il confronto con un unico centro mostra '
            'benefici modesti nei primi due scenari e un peggioramento nel terzo. Il clustering '
            'è dunque una soluzione candidata valutata sul compito, non una componente di cui '
            'si presume indispensabilità. Sono auditate 17.280 predizioni del monitoraggio '
            'sui tre metodi e sulle tre famiglie, oltre alle predizioni supervisionate e bayesiane.',
            'La conclusione non si estende uniformemente agli altri dataset: nello scenario redundant '
            'il delta F1 di KB rispetto a LOCAL è −0,014 per logistica, +0,007 per foresta e −0,005 '
            'per boosting. La sola logica resta un riferimento competitivo. La conoscenza formalizzata '
            'correttamente può essere utile al ragionamento e alla ricerca anche quando le sue '
            'aggregazioni non migliorano il classificatore; i risultati sconsigliano di assumere '
            'un vantaggio predittivo universale dell’integrazione. Nel dataset dense i delta '
            'sono invece +0,052/+0,058/+0,055: logistica e foresta con KB raggiungono F1 0,665 '
            'e 0,658, contro 0,655 della sola logica. I piccoli divari non dimostrano superiorità '
            'statisticamente significativa. Densità, dimensione, prevalenza e seed variano '
            'congiuntamente, quindi il confronto non identifica quale fattore causi le differenze.',
            'Generatore e KB condividono deliberatamente la semantica delle dipendenze: i risultati '
            'sono interni al benchmark sintetico. Restano da valutare dati reali, dipendenze mancanti, '
            'topologie cicliche nella valutazione predittiva, drift, effetti incerti e tempi delle riparazioni. '
            'Le tre famiglie sintetiche ampliano la valutazione nel dominio dei servizi; '
            'non sostituiscono esperimenti su domini indipendenti. '
            'La ricerca ha spazio esponenziale e la rete è limitata a sei variabili; non si rivendica '
            'scalabilità industriale. Le deviazioni standard dei fold non provano significatività.',
            'Il perimetro stimato è 25 ore: 2 per analisi, 4 per KB e verifica, 2 per generatore, '
            '4 per ML supervisionato, 2 per clustering e monitoraggio, 3 per rete bayesiana, '
            '1 per il benchmark aggiuntivo di ricerca, 4 per valutazione e relazione, 3 per '
            'riproduzione e discussione. È una stima organizzativa, non un rendiconto di ore svolte. '
            'K-Means ha un ruolo operativo nella produzione degli allarmi '
            'e viene valutato contro due baseline; la ricerca delle riparazioni resta un contributo aggiuntivo.'
            ' La KB sviluppata è specifica del dominio, mentre interprete e ricerca operano su regole '
            'e topologie esterne. Non si rivendicano algoritmi nuovi né superiorità sullo stato dell’arte.',
            table(['Criterio tecnico', 'Evidenza e autovalutazione'], [
                ['Originalità', 'Integrazione di KB, generatore, feature e ricerca per il dominio dei servizi mediante algoritmi standard documentati.'],
                ['Completezza', 'Rappresentazione, ragionamento ricorsivo, clustering, ricerca, apprendimento supervisionato e probabilistico.'],
                ['Significatività', 'Confronti con sola logica, prior, feature senza relazioni e strategia di riparazione economica; utilità condizionata al simulatore.'],
                ['Complessità', 'Congiunzione delle repliche, dipendenze transitive e condivise; analisi dei join, del punto fisso e dello spazio di ricerca.'],
                ['Generalità', 'Tre famiglie sintetiche nello stesso dominio; assente validazione esterna su dati reali o domini diversi.'],
                ['Valutazione', 'Tre dataset e CV annidata a gruppi, medie e deviazioni standard; monitoraggio con partizioni indipendenti, oracoli e 26 test.'],
                ['Documentazione', 'Template originale, componenti indicati con matricola e utenza istituzionale, scelte tecniche, regole, risultati e limiti in questo file.']], [2200, 6826]),
            table(['Modulo o cartella', 'Funzione in ServiceRescue-KB'], [
                ['src/main.py', 'Orchestrazione della pipeline nel dominio dei servizi.'],
                ['src/serviceProlog.py', 'Preparazione dei dati e inferenza SWI-Prolog.'],
                ['src/unsupervisedLearning.py', 'K-Means e silhouette per anomalie che alimentano la KB.'],
                ['src/supervisedLearning.py', 'Tre classificatori, ablation e CV annidata a gruppi.'],
                ['src/bayesianNetwork.py', 'Apprendimento BIC vincolato e inferenza esatta implementati in NumPy.'],
                ['src/extraAnalysis.py', 'Curve di apprendimento e importanze aggregate.'],
                ['kb/, data/raw/, data/processed/', 'Regole e dati del dominio dei servizi.'],
                ['results/tables/, results/figures/, docs/', 'Risultati verificabili e documento unico sul template.']], [3150, 5876]),
            'L’organizzazione modulare distingue le responsabilità della pipeline. Le cartelle '
            'tests/ e tools/ conservano verifiche e comandi riproducibili; src/servicerescue/ '
            'separa il codice riutilizzabile dagli entrypoint.',
            'L’autovalutazione sintetizza la coerenza con i requisiti tecnici del progetto e i limiti '
            'emersi dalla valutazione. OWL, RDF2Vec, SVM logiche e modelli probabilistici relazionali '
            'sono possibili approcci alternativi, esterni al perimetro implementato.',
            'Il repository raccoglie documentazione, codice, KB, dati, test, strumenti e risultati '
            'necessari alla riproduzione degli esperimenti. L’ambiente virtuale e le cache restano '
            'locali e sono esclusi dal versionamento.'
        ],
        85: ['[1] D. L. Poole, A. K. Mackworth, Artificial Intelligence: Foundations of Computational Agents, '
             '3ª ed., Cambridge University Press, 2023. Riferimenti per Datalog e ricerca: '
             'https://artint.info/3e/html/ArtInt3e.Ch15.S4.html e https://artint.info/3e/html/ArtInt3e.Ch3.S5.html.'],
        86: ['[2] SWI-Prolog, Reference Manual, Tabled execution (SLG resolution): '
             'https://www.swi-prolog.org/pldoc/man?section=tabling. Motore usato: SWI-Prolog 9.0.4.'],
        87: ['[3] Scikit-learn, documentazione ufficiale: Cross-validation, '
             'https://scikit-learn.org/stable/modules/cross_validation.html; StratifiedGroupKFold, '
             'https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.StratifiedGroupKFold.html; '
             'Common pitfalls, https://scikit-learn.org/stable/common_pitfalls.html; Permutation importance, '
             'https://scikit-learn.org/stable/modules/permutation_importance.html. Versione usata: 1.7.2; '
             'i collegamenti stable possono descrivere versioni successive.'],
    }


def paragraph(template, item, keep_identity=False):
    p = deepcopy(template)
    if not keep_identity:
        p.attrib.clear()
    first_properties = template.find('w:r/w:rPr', NS)
    for child in list(p):
        if child.tag != tag('pPr'):
            p.remove(child)
    run = sub(p, 'r')
    properties = deepcopy(first_properties) if first_properties is not None else ET.Element(tag('rPr'))
    run.append(properties)
    text = item if isinstance(item, str) else item.get('bold', item.get('code', ''))
    if isinstance(item, dict) and 'bold' in item:
        sub(properties, 'b', {'val': 1})
    if isinstance(item, dict) and 'code' in item:
        sub(properties, 'rFonts', {'ascii': 'Consolas', 'hAnsi': 'Consolas'})
        sub(properties, 'sz', {'val': 18})
    for i, line in enumerate(text.splitlines()):
        if i:
            sub(run, 'br')
        t = sub(run, 't', text=line)
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    return p


def word_table(item):
    data = item['table']
    count = len(data[0])
    widths = item['widths'] or {3: [2800, 3300, 2926], 4: [2100, 2100, 2413, 2413]}.get(count)
    widths = widths or [9026 // count] * count
    t = ET.Element(tag('tbl'))
    props = sub(t, 'tblPr')
    sub(props, 'tblW', {'w': sum(widths), 'type': 'dxa'})
    sub(props, 'tblLayout', {'type': 'fixed'})
    borders = sub(props, 'tblBorders')
    for side in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
        sub(borders, side, {'val': 'single', 'sz': 4, 'color': 'B7B7B7'})
    margins = sub(props, 'tblCellMar')
    for side in ['top', 'bottom', 'left', 'right']:
        sub(margins, side, {'w': 70, 'type': 'dxa'})
    grid = sub(t, 'tblGrid')
    for width in widths:
        sub(grid, 'gridCol', {'w': width})
    for i, row in enumerate(data):
        if len(row) != count:
            raise ValueError('Tabella non rettangolare')
        tr = sub(t, 'tr')
        trpr = sub(tr, 'trPr')
        sub(trpr, 'cantSplit')
        if i == 0:
            sub(trpr, 'tblHeader')
        for value, width in zip(row, widths):
            cell = sub(tr, 'tc')
            cp = sub(cell, 'tcPr')
            sub(cp, 'tcW', {'w': width, 'type': 'dxa'})
            if i == 0:
                sub(cp, 'shd', {'fill': 'EDEDED'})
            p = sub(cell, 'p')
            sub(sub(p, 'pPr'), 'spacing', {'before': 0, 'after': 40, 'line': 240, 'lineRule': 'auto'})
            r = sub(p, 'r')
            rp = sub(r, 'rPr')
            sub(rp, 'sz', {'val': 18})
            if i == 0:
                sub(rp, 'b')
            sub(r, 't', text=str(value))
    return t


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', type=Path, default=ROOT / 'tools/Template_Doc_Progetto.docx')
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/Documentazione_ServiceRescue-KB.docx')
    args = parser.parse_args()
    with ZipFile(args.template) as source:
        entries = [(info, source.read(info.filename)) for info in source.infolist()]
    source_xml = next(data for info, data in entries if info.filename == 'word/document.xml')
    # iterparse produce (evento, (prefisso, URI)).
    namespaces = dict(pair for _, pair in ET.iterparse(io.BytesIO(source_xml), events=['start-ns']))
    for prefix, uri in namespaces.items():
        ET.register_namespace(prefix, uri)
    document = ET.fromstring(source_xml)
    body = document.find('w:body', NS)
    original = list(body)
    if len(original) != 89 or text_of(original[25]) != 'Sezione Argomento 1' or text_of(original[78]) != 'Conclusioni':
        raise ValueError('Struttura del template diversa: richiede una nuova mappatura')
    replacements = fill_content()
    for node in list(body):
        body.remove(node)
    for index, node in enumerate(original):
        if index not in replacements:
            body.append(node)
            continue
        for n, item in enumerate(replacements[index]):
            body.append(word_table(item) if isinstance(item, dict) and 'table' in item
                        else paragraph(node, item, keep_identity=n == 0))
    rendered = ET.tostring(document, encoding='utf-8', xml_declaration=True).decode('utf-8')
    opening = re.search(r'<w:document\b[^>]*>', rendered).group(0)
    extra = ''.join(f' xmlns:{prefix}="{uri}"' for prefix, uri in namespaces.items()
                    if prefix and f'xmlns:{prefix}=' not in opening)
    # Conserva anche i namespace citati solo da mc:Ignorable.
    rendered = rendered.replace(opening, opening[:-1] + extra + '>', 1)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(args.output, 'w') as target:
        for info, data in entries:
            target.writestr(info, rendered.encode('utf-8') if info.filename == 'word/document.xml' else data)
    print(f'Template compilato: {args.output}')
    print(f'Segnaposto compilati: {len(replacements)}; titoli e stili originali conservati.')


if __name__ == '__main__':
    main()
