import argparse

from controller import DEFAULT_DB_FILE, ENVRC_PATH, run


def parse_args():
    parser = argparse.ArgumentParser(
        description="Scraper dell'archivio di leva di Padova e Rovigo"
    )
    parser.add_argument(
        "surnames",
        nargs="*",
        help="Cognomi (o parti di essi) da cercare; in coda usa la tripletta iniziale",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disabilita la cache dei risultati",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Percorso del file TSV su cui salvare i risultati della sessione",
    )
    parser.add_argument(
        "--force-exact",
        action="store_true",
        help="Forza la ricerca sul cognome esatto (non usa la tripletta iniziale)",
    )
    parser.add_argument(
        "--surname-match",
        choices=("partial", "exact", "soundex"),
        help="Modalità di ricerca cognome: partial, exact o soundex (default: partial)",
    )
    parser.add_argument(
        "--import-names",
        metavar="FILE",
        help="Importa un elenco iniziale di nomi nel database (solo su richiesta)",
    )
    parser.add_argument(
        "--db",
        help="Percorso del database SQLite per salvare e interrogare i risultati",
    )
    parser.add_argument(
        "--search",
        help="Esegue una ricerca nel database con regexp sui campi indicati",
    )
    parser.add_argument(
        "--search-fields",
        help="Campi su cui applicare la regexp (separati da virgola)",
    )
    parser.add_argument(
        "--search-limit",
        type=int,
        help="Limita il numero di risultati della ricerca nel database",
    )
    parser.add_argument(
        "--config-env",
        action="store_true",
        help="Configura interattivamente le variabili in .envrc",
    )
    parser.add_argument(
        "--queue-status",
        action="store_true",
        help="Mostra l'elenco dei cognomi noti con stato interrogazioni",
    )
    parser.add_argument(
        "--list-surnames",
        action="store_true",
        help="Stampa l'elenco dei cognomi noti nel database",
    )
    parser.add_argument(
        "--metrics-log",
        action="store_true",
        help="Mostra il log delle interrogazioni delle triplette",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Numero massimo di cognomi da processare per iterazione della coda",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=100,
        help="Numero massimo di iterazioni della coda per evitare loop infiniti",
    )
    args = parser.parse_args()
    if args.force_exact and args.surname_match:
        parser.error("Usare --force-exact oppure --surname-match, non entrambi")
    if (
        not args.surnames
        and not args.config_env
        and not args.search
        and not args.queue_status
        and not args.import_names
        and not args.list_surnames
        and not args.metrics_log
    ):
        parser.error("Specificare almeno un cognome oppure usare --config-env")
    return args


def main():
    args = parse_args()
    run(args, envrc_path=ENVRC_PATH, default_db_path=DEFAULT_DB_FILE)


if __name__ == "__main__":
    main()
