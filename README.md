# ServiceRescue-KB

Progetto per l’esame di **Ingegneria della Conoscenza**: analisi dei guasti di servizi informatici tramite **SWI-Prolog/Datalog, K-Means e silhouette, apprendimento supervisionato con Background Knowledge e rete bayesiana**. Include inoltre la ricerca delle riparazioni a costo minimo.

Il sistema studia come riconoscere anomalie nei sensori, dedurne gli effetti sui servizi e prevedere un’interruzione futura con l’aiuto della KB. Se i guasti sono confermati, cerca inoltre le riparazioni che ripristinano il servizio critico al costo minimo.

Il progetto ha una struttura modulare e confronta modelli con e senza feature derivate dalla KB. Il dataset è **sintetico originale**, generato localmente: non sono utilizzati dati reali di produzione. L’esecuzione è locale: richiede SWI-Prolog installato e disponibile nel PATH.

## Avvio rapido

Richiesti **SWI-Prolog** e Python **3.10 o successivo**; verificato con Python 3.12.3. Dalla cartella `ServiceRescue-KB`:

Installare SWI-Prolog: `sudo apt-get install swi-prolog-nox` su Linux, `brew install swi-prolog` su macOS; su Windows usare l’installer ufficiale e aggiungere `swipl` al PATH.

```bash
python -m venv .venv
# Linux / macOS / WSL
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py demo
python -m unittest discover -s tests -v
python src/main.py
python tests/audit_results.py results/full
```

Su sistemi dove il comando è `python3`, usarlo per creare l’ambiente. Dopo aver installato le dipendenze, su Linux/WSL è possibile eseguire `.venv/bin/python main.py demo`. L’ambiente `.venv` è locale e non va incluso nel repository né copiato tra sistemi operativi.

La demo mostra una catena `power → db_a → api → portal`: riparare `power` costa 4; la strategia che sceglie prima il guasto meno costoso ripara anche `db_b` e spende 6. Il JSON contiene l’albero delle deduzioni e i due piani.

```bash
# Controllo rapido della pipeline; non valido come valutazione finale
python main.py experiment --profile smoke
# Nuovo esperimento riproducibile, in una directory distinta
python main.py experiment --profile full --seed 73 --output results/seed73
```

Il profilo completo genera **960 osservazioni di 120 infrastrutture**, confronta tre classificatori su tre insiemi di feature e due baseline; valuta inoltre una rete bayesiana con struttura appresa e svolge analisi aggiuntive. Usa **5 fold esterni × 2 ripetizioni e 3 fold interni**, tutti separati per infrastruttura. La durata dipende dalla macchina. Rieseguire un profilo nella stessa cartella aggiorna i relativi risultati.

La valutazione di consegna comprende **tre dataset sintetici**: `standard` (seed 42, 10–18 nodi), `redundant` (seed 73, più repliche) e `dense` (seed 101, 20–30 nodi e più dipendenze obbligatorie). Sono 2.880 osservazioni di 360 infrastrutture, con CV annidata separata per ciascun dataset e configurazioni prefissate. Non sono tre domini reali e non si misura il trasferimento tra famiglie. Protocollo e tabelle comparative: `results/scenarios/`.

```bash
# Riproduce i tre esperimenti completi e controlla tutti gli artefatti
python tools/evaluate_scenarios.py
# Ripete solo gli audit e rigenera le tabelle comparative
python tools/evaluate_scenarios.py --summarize-only
```

Il ramo non supervisionato usa **misure nominali separate dalle etichette di previsione**: K-Means seleziona k fra 2 e 7 tramite silhouette nel training, poi una calibrazione separata fissa la soglia delle anomalie. Queste diventano fatti `alarm` della KB. Il confronto con soglie fisse e distanza da un unico centro misura l’utilità del clustering sul compito finale. Le verità dei guasti iniettati servono soltanto alla valutazione. Riferimento nominale pulito, due modi di carico e perturbazioni additive sono ipotesi del benchmark, non caratteristiche validate su servizi reali.

## Documentazione unica

La documentazione completa è raccolta in **[Documentazione_ServiceRescue-KB.docx](docs/Documentazione_ServiceRescue-KB.docx)**, compilata nel template del progetto conservando titoli, ordine, stili e le tre sezioni tecniche. Rappresentazione e ricerca occupano la prima sezione, apprendimento supervisionato e non supervisionato la seconda, rete bayesiana la terza.

Il file include tutte le regole, i tre dataset, i parametri, le tabelle con medie e deviazioni standard, l’interpretazione, le verifiche, i limiti e l’autovalutazione tecnica. Il frontespizio contiene i dati del progetto e il collegamento a [ServiceRescue](https://github.com/DomenicoMastrolonardo/ServiceRescue).

Il template sorgente è in `tools/Template_Doc_Progetto.docx`; il testo è in `tools/fill_template.py`. I rapporti automatici e i CSV nelle cartelle dei risultati sono artefatti sperimentali, mentre il Word è il documento unico da consegnare. Per rigenerarlo dopo aver completato i tre esperimenti:

```bash
python tools/build_documentation.py
```

La generazione del documento usa esclusivamente la libreria standard Python e non richiede Word installato.

## Struttura

```text
src/main.py                 pipeline principale
src/serviceProlog.py        preparazione dati e inferenza SWI-Prolog
src/unsupervisedLearning.py K-Means, silhouette, anomalie e KB
src/supervisedLearning.py   CV annidata supervisionata
src/bayesianNetwork.py      struttura BIC, CPD e inferenza probabilistica
src/extraAnalysis.py        curve, importanze e figure
src/servicerescue/          implementazione modulare riutilizzabile
kb/kb.pl                    KB Prolog eseguibile
kb/rules.json               regole equivalenti per la verifica Datalog
data/raw/                   osservazioni e topologie sintetiche
data/processed/             dataset con feature KB e fatti Prolog
results/tables/             tabelle aggregate degli esperimenti
results/figures/            grafici delle analisi
results/full/               artefatti canonici e audit del run completo
results/full_redundant/     secondo dataset e valutazione completa
results/full_dense/         terzo dataset e valutazione completa
results/scenarios/          protocollo e tabelle comparative dei tre dataset
docs/                       documentazione Word del progetto
tests/                      test semantici, probabilistici e audit
tools/                      generatore Word, template, suite su tre dataset e repairSearch.py
main.py                     entrypoint precedente, mantenuto
```

L’assenza di una dipendenza o una divergenza fra motore logico e oracolo interrompe l’esecuzione: non esistono feature di ripiego impostate silenziosamente a zero. Le feature finali provengono da SWI-Prolog e vengono confrontate con la chiusura Datalog su tutti i sei predicati derivati. Il simulatore verifica separatamente la semantica dei guasti. La rete probabilistica è proposizionale su feature aggregate: non è un modello probabilistico relazionale.

## Architettura e moduli

Il sistema comprende sei moduli principali, KB esterna, K-Means con silhouette, tre classificatori, CV annidata, rete bayesiana con struttura appresa e analisi aggiuntive. Le conclusioni del documento Word descrivono il ruolo dei file e l’autovalutazione secondo i criteri tecnici del progetto.

`serviceProlog.py` gestisce la preparazione dei dati e l’inferenza nel dominio dei servizi. Le cartelle principali sono `src/`, `kb/`, `data/raw/`, `data/processed/`, `results/figures/`, `results/tables/` e `docs/`. `tests/`, `tools/` e il pacchetto interno `src/servicerescue/` contengono verifiche, comandi riproducibili e codice riutilizzabile. La ricerca aggiuntiva è eseguibile con `python tools/repairSearch.py`.

L’implementazione usa subprocess per SWI-Prolog, una rete bayesiana BIC con ordine prefissato e inferenza per enumerazione in NumPy, e clustering applicato al monitoraggio. Le dipendenze sono elencate in `requirements.txt`. I dati sono sintetici originali e la valutazione usa split a gruppi e tre famiglie di infrastrutture.

I singoli moduli sono eseguibili con `python src/<modulo>.py`; i moduli di valutazione richiedono prima il run completo. `supervisedLearning.py`, `unsupervisedLearning.py` e `tools/repairSearch.py` scrivono i propri rerun in cartelle separate. I file in `results/tables/` sono copie di consegna degli artefatti canonici `results/full/`; rieseguire la pipeline completa li aggiorna insieme alle figure. Per il monitoraggio sono disponibili `01_cluster_profiles.csv`, `07_anomaly_detection.csv` e `08_silhouette_scores.csv`, oltre al grafico `01_silhouette_scores.png`.

Le 25 ore riportate nel documento sono una stima del perimetro di lavoro, non ore effettivamente registrate.
