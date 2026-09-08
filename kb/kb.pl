% ServiceRescue-KB: stesse dodici regole positive di rules.json.
% C identifica la fotografia: nessuna deduzione attraversa due osservazioni.
:- use_module(library(http/json)).
:- dynamic snapshot/1, requires/3, replicas/4, alarm/2, critical/2.
:- table reach/3, down/2.

edge(C,S,D) :- requires(C,S,D).
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
degraded(C,S) :- replicas(C,S,_,B), down(C,B).

export_snapshot(C) :-
    findall([edge,S,D], edge(C,S,D), Edges),
    findall([reach,S,D], reach(C,S,D), Reaches),
    findall([down,S], down(C,S), Downs),
    findall([critical_down,S], critical_down(C,S), Criticals),
    findall([exposed,S,D], exposed(C,S,D), Exposed),
    findall([degraded,S], degraded(C,S), Degraded),
    append([Edges,Reaches,Downs,Criticals,Exposed,Degraded], All),
    sort(All, Facts),
    json_write_dict(current_output, _{sample_id:C,facts:Facts}, [width(0)]), nl.

main :-
    current_prolog_flag(argv, [FactsFile]),
    load_files(FactsFile, [silent(true)]),
    forall(snapshot(C), export_snapshot(C)), halt.
