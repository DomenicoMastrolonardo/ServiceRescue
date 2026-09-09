# Knowledge Base

Questa scheda descrive le dodici regole del benchmark sintetico. L’estensione RCAEval usa separatamente `observed_calls.json`: tre regole per percorsi di chiamata e possibili effetti di un allarme. Queste ultime non derivano indisponibilità; significato e limiti sono descritti in `data/external/README.md` e nel documento Word.

La KB principale è `kb.pl`, eseguita da SWI-Prolog. `rules.json` contiene la rappresentazione equivalente utilizzata dal verificatore Datalog. Le variabili iniziano con `?`; gli altri termini sono costanti stringa. Ogni regola contiene nome, testa e lista di atomi del corpo. Tutte le variabili della testa devono comparire nel corpo.

## Fatti di ingresso

| Predicato | Significato |
|---|---|
| `requires(S,D)` | S richiede D: il guasto di D rende indisponibile S |
| `replicas(S,A,B)` | S richiede almeno una delle due repliche A e B |
| `alarm(S)` | S è assunto guasto nello scenario logico corrente |
| `critical(S)` | Il ripristino di S è necessario per raggiungere l’obiettivo |

Più fatti `requires` sullo stesso servizio rappresentano requisiti congiunti di disponibilità: basta perdere un requisito per avere un guasto. Più gruppi di repliche sullo stesso servizio sono anch’essi requisiti congiunti. Il generatore usa al massimo un gruppo per nodo. Costi, sensori e zone sono metadati dell’applicazione e non predicati inferenziali.

## Le dodici regole

Questa notazione testuale è la trascrizione leggibile delle regole JSON:

```prolog
edge(S,D) :- requires(S,D).
edge(S,A) :- replicas(S,A,B).
edge(S,B) :- replicas(S,A,B).
reach(S,D) :- edge(S,D).
reach(S,D) :- edge(S,M), reach(M,D).

down(S) :- alarm(S).
down(S) :- requires(S,D), down(D).
down(S) :- replicas(S,A,B), down(A), down(B).
critical_down(S) :- critical(S), down(S).
exposed(S,D) :- reach(S,D), alarm(D).
degraded(S) :- replicas(S,A,B), down(A).
degraded(S) :- replicas(S,A,B), down(B).
```

`reach` descrive la raggiungibilità strutturale, non implica automaticamente un guasto: una replica sana può proteggere il servizio. `degraded` significa che **almeno una** replica è indisponibile; resta vero anche se sono guaste entrambe. Non significa “degradato ma operativo”.

## Semantica e spiegazione

Il motore calcola il minimo punto fisso con iterazioni sincrone: i nuovi fatti diventano utilizzabili nell’iterazione successiva. Conserva una prima giustificazione per ogni deduzione; tutte le premesse sono più vecchie della conclusione, quindi la spiegazione rimane aciclica anche se la topologia contiene cicli. Non elenca tutte le prove, né garantisce la prova minima. L’ordine delle regole può cambiare la prima prova ma non la chiusura.

Il linguaggio non include negazione, funzioni, uguaglianza speciale o vincoli aritmetici. Il pianificatore usa l’assenza di `critical_down` come obiettivo **sotto assunzione di mondo chiuso e inventario completo**. Con una topologia incompleta questa assenza non dimostra disponibilità reale.

Nel dataset gli allarmi sono soglie sui sensori e `down` è un’ipotesi qualitativa di rischio. Nei casi di pianificazione gli stessi fatti rappresentano guasti confermati: le due interpretazioni sono esplicite e i piani non sono applicati a un’infrastruttura reale.

## Esecuzione SWI-Prolog

Il modulo `src/serviceProlog.py` genera fatti con un primo argomento C, identificatore della fotografia. In Prolog `requires(C,S,D)` e `down(C,S)` mantengono separate le osservazioni. I predicati ricorsivi `reach/3` e `down/2` usano tabling (risoluzione SLG) per terminare anche sui cicli. Ogni processo carica fatti immutabili e termina dopo le query: nessuna tabella obsoleta sopravvive al cambio di fatti. Le feature finali sono estratte dalle deduzioni di Prolog, confrontate su tutti i sei predicati con la chiusura Datalog; un disaccordo interrompe la pipeline. Il pianificatore mantiene il motore Datalog come oracolo interno, verificato separatamente dal simulatore.
