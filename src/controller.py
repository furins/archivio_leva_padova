import os
import sqlite3
from getpass import getpass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from libraries.leva_padova import LevaPadova, parse_mother_surname
from libraries.secrets import PASSWORD_ENV, USERNAME_ENV
from libraries.storage import (
    DATA_FIELDS,
    connect_db,
    count_query_triplette,
    enqueue_surname,
    fetch_cached_triplette,
    fetch_known_names,
    fetch_known_surnames,
    fetch_pending_surnames,
    fetch_people,
    mark_surname_done,
    normalize_surname,
    normalize_surname_prefix,
    normalize_queue_surnames,
    query_exists,
    record_query,
    search_people,
    upsert_names,
    upsert_people,
)
from libraries.triplette import Triplette

DEFAULT_NOMI_FILE = Path("data/nomi.txt")
DEFAULT_DB_FILE = Path("risultati/leva.sqlite")
ENVRC_PATH = Path(".envrc")
HEADER = (
    "Cognome",
    "Nome",
    "Data di nascita",
    "Luogo di nascita",
    "Provincia",
    "Comune iscrizione",
    "Mandamento",
    "Padre",
    "Madre",
)
ENV_VARIABLES = (
    (USERNAME_ENV, False),
    (PASSWORD_ENV, True),
)


def sort_rows(rows: Iterable[Sequence[str]]) -> List[List[str]]:
    ordered = [list(row) for row in rows]
    ordered.sort(key=lambda x: (x[3], x[1], x[0]))
    return ordered


def print_results(cognome: str, rows: Iterable[Sequence[str]]):
    ordered = sort_rows(rows)
    print(f"=== Risultati per {cognome} ===")
    if not ordered:
        print("Nessun risultato trovato.")
        return
    print("\t".join(HEADER))
    for row in ordered:
        print("\t".join(row))


def print_search_results(rows: Iterable[sqlite3.Row]):
    print("\t".join(HEADER))
    for row in rows:
        values = [row[field] or "" for field in DATA_FIELDS]
        print("\t".join(values))


def write_results(path: str, results: Iterable[Sequence[str]]):
    ordered = sort_rows(results)
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as fh:
        fh.write("\t".join(HEADER))
        fh.write("\n")
        for row in ordered:
            fh.write("\t".join(row))
            fh.write("\n")


def load_names_from_file(path: Path) -> Set[str]:
    names: Set[str] = set()
    if not path.exists():
        return names
    with path.open() as fh:
        for line in fh:
            nome = line.strip()
            if nome:
                names.add(nome)
    return names


def read_envrc_values(path: Path) -> Dict[str, str]:
    valori: Dict[str, str] = {}
    if not path.exists():
        return valori
    with path.open() as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line.startswith("export "):
                continue
            contenuto = line[len("export "):]
            if "=" not in contenuto:
                continue
            var_name, raw_value = contenuto.split("=", 1)
            var_name = var_name.strip()
            raw_value = raw_value.strip()
            if raw_value and raw_value[0] in {'"', "'"} and raw_value[-1] == raw_value[0]:
                raw_value = raw_value[1:-1]
            raw_value = raw_value.replace('\\"', '"')
            valori[var_name] = raw_value
    return valori


def format_env_line(var_name: str, value: str) -> str:
    escaped = value.replace('"', '\\"')
    return f'export {var_name}="{escaped}"'


def write_envrc_values(path: Path, values: Dict[str, str]):
    lines: List[str] = []
    if path.exists():
        lines = path.read_text().splitlines()
    aggiornati: Set[str] = set()
    for idx, raw_line in enumerate(lines):
        stripped = raw_line.strip()
        if not stripped.startswith("export "):
            continue
        contenuto = stripped[len("export "):]
        if "=" not in contenuto:
            continue
        var_name = contenuto.split("=", 1)[0].strip()
        if var_name in values:
            lines[idx] = format_env_line(var_name, values[var_name])
            aggiornati.add(var_name)
    for var_name, value in values.items():
        if var_name not in aggiornati:
            lines.append(format_env_line(var_name, value))
    text = "\n".join(lines)
    if text and not text.endswith("\n"):
        text += "\n"
    with path.open("w") as fh:
        fh.write(text)


def prompt_env_value(var_name: str, current: str, secret: bool) -> str:
    while True:
        default_hint = f" [{current}]" if current else ""
        prompt = f"{var_name}{default_hint}: "
        raw = getpass(prompt) if secret else input(prompt)
        raw = raw.strip()
        if not raw:
            if current:
                return current
            print("Il valore non può essere vuoto.")
            continue
        return raw


def configure_envrc(path: Path):
    print(f"Configurazione delle variabili in {path}")
    existing = read_envrc_values(path)
    nuovi_valori: Dict[str, str] = {}
    for var_name, is_secret in ENV_VARIABLES:
        current = existing.get(var_name, "")
        nuovi_valori[var_name] = prompt_env_value(var_name, current, secret=is_secret)
    write_envrc_values(path, nuovi_valori)
    for var_name, value in nuovi_valori.items():
        os.environ[var_name] = value
    print(f"Variabili salvate in {path}. Esegui 'direnv allow' per ricaricarle.")


def parse_search_fields(raw_fields: Optional[str]) -> Optional[List[str]]:
    if not raw_fields:
        return None
    return [field.strip() for field in raw_fields.split(",") if field.strip()]


def format_result_row(raw_row: Sequence[object]) -> Tuple[str, ...]:
    def normalize(value: object) -> str:
        return "" if value is None else str(value)

    return (
        normalize(raw_row[0]),
        normalize(raw_row[1]),
        normalize(raw_row[3])[:10],
        normalize(raw_row[4]),
        normalize(raw_row[5]),
        normalize(raw_row[7]),
        normalize(raw_row[8]),
        normalize(raw_row[9]),
        normalize(raw_row[10]),
    )


def enqueue_mother_surnames(
    conn: sqlite3.Connection,
    cognome_fonte: str,
    rows: Iterable[sqlite3.Row],
    use_prefix: bool = True,
) -> None:
    for row in rows:
        madre = row["madre"] if isinstance(row, sqlite3.Row) else row[-1]
        mother_surname = parse_mother_surname(madre)
        if mother_surname:
            enqueue_surname(
                conn,
                mother_surname,
                fonte=f"madre:{cognome_fonte}",
                use_prefix=use_prefix,
            )


def run(args, envrc_path: Path = ENVRC_PATH, default_db_path: Path = DEFAULT_DB_FILE):
    if args.config_env:
        configure_envrc(envrc_path)
        if not args.surnames:
            return
    db_path = Path(args.db) if args.db else default_db_path
    db_conn = connect_db(db_path) if (args.surnames or args.search) else None
    if args.import_names:
        if db_conn is None:
            db_conn = connect_db(db_path)
        names_file = Path(args.import_names)
        imported = load_names_from_file(names_file)
        count = upsert_names(db_conn, imported, fonte="import")
        print(f"Importati {count} nomi da {names_file}")
        if not args.surnames and not args.search and not args.queue_status:
            db_conn.close()
            return
    if args.queue_status:
        db_conn = connect_db(db_path)
        if not args.force_exact:
            normalize_queue_surnames(db_conn)
        names = [nome.lower() for nome in fetch_known_names(db_conn)]
        if not names:
            imported = load_names_from_file(DEFAULT_NOMI_FILE)
            if imported:
                upsert_names(db_conn, imported, fonte="import")
                names = [nome.lower() for nome in fetch_known_names(db_conn)]
        if not names:
            print("Nessun nome disponibile nel database. Usa --import-names per inizializzare.")
            db_conn.close()
            return
        total_triplette = len(Triplette(names).lista)
        known = fetch_known_surnames(db_conn)
        full = 0
        partial = 0
        none = 0
        for cognome in known:
            count = count_query_triplette(db_conn, cognome, args.force_exact)
            if count >= total_triplette:
                status = "completo"
                full += 1
            elif count > 0:
                status = "parziale"
                partial += 1
            else:
                status = "nessuna"
                none += 1
            print(f"{cognome}\t{status}\t{count}/{total_triplette}")
        print(
            "Totali:\n"
            f"- completi: {full}\n"
            f"- parziali: {partial}\n"
            f"- nessuna: {none}"
        )
        db_conn.close()
        if not args.surnames and not args.search:
            return
    names = [nome.lower() for nome in fetch_known_names(db_conn)] if db_conn else []
    if not names and db_conn:
        imported = load_names_from_file(DEFAULT_NOMI_FILE)
        if imported:
            upsert_names(db_conn, imported, fonte="import")
            names = [nome.lower() for nome in fetch_known_names(db_conn)]
    if not names:
        print("Nessun nome disponibile nel database. Usa --import-names per inizializzare.")
        if db_conn:
            db_conn.close()
        return
    triplette = Triplette(names)
    if args.search and db_conn:
        fields = parse_search_fields(args.search_fields)
        results = search_people(
            db_conn,
            args.search,
            fields=fields,
            limit=args.search_limit,
        )
        print_search_results(results)
        if not args.surnames:
            return
    combined: Set[Tuple[str, ...]] = set()
    nuovi_nomi: Set[str] = set()

    if db_conn and args.surnames:
        if not args.force_exact:
            normalize_queue_surnames(db_conn)
        for raw_cognome in args.surnames:
            normalized = normalize_surname(raw_cognome)
            if normalized:
                enqueue_surname(
                    db_conn,
                    normalized,
                    fonte="cli",
                    use_prefix=not args.force_exact,
                )

    iterations = 0
    pending: List[str] = []
    if db_conn:
        if not args.force_exact:
            normalize_queue_surnames(db_conn)
        pending = fetch_pending_surnames(db_conn, args.batch_size)

    while pending:
        iterations += 1
        if iterations > args.max_iterations:
            print("Raggiunto il limite massimo di iterazioni della coda.")
            break

        for cognome in pending:
            normalized = normalize_surname(cognome)
            cognome_query = (
                normalize_surname_prefix(normalized)
                if not args.force_exact
                else normalized
            )
            cached_triplette = set()
            if db_conn and not args.no_cache:
                cached_triplette = fetch_cached_triplette(
                    db_conn,
                    cognome_query,
                    args.force_exact,
                )
            connessione = None
            total_triplette = len(triplette.lista)
            width = len(str(total_triplette))
            for idx, tripletta in enumerate(triplette.lista.keys(), start=1):
                if db_conn and not args.no_cache:
                    if query_exists(db_conn, cognome_query, tripletta, args.force_exact):
                        cached_triplette.add(tripletta)
                        print(
                            f"[{idx:{width}}/{total_triplette}] "
                            f"{cognome} {tripletta} (cache)"
                        )
                        continue
                    covering = triplette.covering_triplette(tripletta, cached_triplette)
                    if covering:
                        print(
                            f"[{idx:{width}}/{total_triplette}] {cognome} {tripletta} "
                            f"(inferenza da {covering})"
                        )
                        continue
                if connessione is None:
                    connessione = LevaPadova()
                risultati = connessione.query(
                    cognome_query,
                    tripletta,
                    cognome_esatto=args.force_exact,
                )
                formatted = [format_result_row(row) for row in risultati]
                if db_conn:
                    upsert_people(db_conn, formatted, fonte="leva_padova")
                    record_query(
                        db_conn,
                        cognome_query,
                        tripletta,
                        args.force_exact,
                        len(risultati),
                    )
                    cached_triplette.add(tripletta)
                print(
                    f"[{idx:{width}}/{total_triplette}] "
                    f"{cognome} {tripletta} {len(risultati)}"
                )

            cognome_lookup = cognome if args.force_exact else cognome_query
            results = (
                fetch_people(db_conn, cognome_query, args.force_exact) if db_conn else []
            )
            print_results(cognome_query, results)
            combined.update(tuple(row) for row in results)
            nuovi_nomi.update(row[1].lower() for row in results if len(row) > 1 and row[1])
            if db_conn:
                surnames_seen: Set[str] = set()
                for row in results:
                    if not row:
                        continue
                    normalized = normalize_surname(row[0])
                    if normalized and normalized not in surnames_seen:
                        surnames_seen.add(normalized)
                        enqueue_surname(
                            db_conn,
                            normalized,
                            fonte=f"cognome:{cognome}",
                            use_prefix=not args.force_exact,
                        )
                enqueue_mother_surnames(
                    db_conn,
                    cognome_query,
                    results,
                    use_prefix=not args.force_exact,
                )
                mark_surname_done(db_conn, cognome_query, args.force_exact)

        pending = fetch_pending_surnames(db_conn, args.batch_size) if db_conn else []

    if args.output:
        write_results(args.output, combined)

    if db_conn and nuovi_nomi:
        upsert_names(db_conn, nuovi_nomi, fonte="leva_padova")
    if db_conn:
        db_conn.close()
