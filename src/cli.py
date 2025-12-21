import argparse
import json
import os
import sqlite3
from getpass import getpass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from libraries.database import FIELDS, connect_db, insert_people, search_people
from libraries.leva_padova import RicercaLeva
from libraries.secrets import PASSWORD_ENV, USERNAME_ENV
from libraries.triplette import Triplette

DEFAULT_NOMI_FILE = Path("data/nomi.txt")
CACHE_FILE = Path("risultati/cache.json")
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


def parse_args():
    parser = argparse.ArgumentParser(
        description="Scraper dell'archivio di leva di Padova e Rovigo"
    )
    parser.add_argument(
        "surnames",
        nargs="*",
        help="Cognomi (o parti di essi) da cercare",
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
        help="Forza la ricerca sul cognome esatto",
    )
    parser.add_argument(
        "--aggiorna",
        metavar="FILE",
        help="Aggiorna il file con tutti i nomi noti aggiungendo quelli nuovi",
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
    args = parser.parse_args()
    if not args.surnames and not args.config_env and not args.search:
        parser.error("Specificare almeno un cognome oppure usare --config-env")
    return args


def load_cache(path: Path) -> Dict[str, List[List[str]]]:
    if not path.exists():
        return {}
    try:
        with path.open() as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def save_cache(path: Path, cache: Dict[str, List[List[str]]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        json.dump(cache, fh)


def cache_key(cognome: str, cognome_esatto: bool) -> str:
    return f"{cognome.strip().lower()}|{int(bool(cognome_esatto))}"


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
        values = [row[field] or "" for field in FIELDS]
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


def read_names_file(path: Path) -> Set[str]:
    names: Set[str] = set()
    if not path.exists():
        return names
    with path.open() as fh:
        for line in fh:
            nome = line.strip()
            if nome:
                names.add(nome.lower())
    return names


def update_names_file(path: Path, existing: Set[str], names: Set[str]):
    nuovi = sorted(nome for nome in names if nome and nome not in existing)
    if not nuovi:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        for nome in nuovi:
            fh.write(f"{nome}\n")
    existing.update(nuovi)
    print(f"Aggiunti {len(nuovi)} nuovi nomi al file {path}")


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


def main():
    args = parse_args()
    if args.config_env:
        configure_envrc(ENVRC_PATH)
        if not args.surnames:
            return
    db_path = Path(args.db) if args.db else DEFAULT_DB_FILE
    db_conn = connect_db(db_path) if (args.surnames or args.search) else None
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
    names_file = Path(args.aggiorna) if args.aggiorna else DEFAULT_NOMI_FILE
    triplette = Triplette(str(names_file))
    cache = {} if args.no_cache else load_cache(CACHE_FILE)
    cache_dirty = False
    combined: Set[Tuple[str, ...]] = set()
    nuovi_nomi: Set[str] = set()
    existing_names = read_names_file(names_file) if args.aggiorna else set()

    for raw_cognome in args.surnames:
        cognome = raw_cognome.strip()
        if not cognome:
            continue
        key = cache_key(cognome, args.force_exact)
        if not args.no_cache and key in cache:
            results = cache[key]
            print(f"Uso la cache per {cognome}")
        else:
            ricerca = RicercaLeva(
                cognome=cognome,
                triplette=triplette,
                cognome_esatto=args.force_exact,
            )
            ricerca.search(dump=False)
            results = sort_rows(ricerca.ricerche)
            if not args.no_cache:
                cache[key] = results
                cache_dirty = True
        print_results(cognome, results)
        if db_conn:
            insert_people(db_conn, results)
        combined.update(tuple(row) for row in results)
        nuovi_nomi.update(row[1].lower() for row in results if len(row) > 1 and row[1])

    if not args.no_cache and cache_dirty:
        save_cache(CACHE_FILE, cache)

    if args.output:
        write_results(args.output, combined)

    if args.aggiorna and nuovi_nomi:
        update_names_file(names_file, existing_names, nuovi_nomi)
    if db_conn:
        db_conn.close()


if __name__ == "__main__":
    main()
