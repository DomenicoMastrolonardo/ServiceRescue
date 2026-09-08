"""Orchestratore della pipeline di ServiceRescue-KB."""
import sys
from servicerescue.cli import main

if __name__ == '__main__':
    # Senza argomenti si esegue la pipeline completa.
    if len(sys.argv) == 1 or sys.argv[1].startswith('--'):
        sys.argv.insert(1, 'experiment')
    main()
