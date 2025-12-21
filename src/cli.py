import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set, Tuple

from libraries.leva_padova import RicercaLeva
from libraries.triplette import Triplette

DEFAULT_NOMI_FILE = Path("data/nomi.txt")
CACHE_FILE = Path("risultati/cache.json")
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


def parse_args():
    parser = argparse.ArgumentParser(
        description="Scraper dell'archivio di leva di Padova e Rovigo"
    )
    parser.add_argument(
        "surnames",
        nargs="+",
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
    return parser.parse_args()


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


def main():
    args = parse_args()
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
        combined.update(tuple(row) for row in results)
        nuovi_nomi.update(row[1].lower() for row in results if len(row) > 1 and row[1])

    if not args.no_cache and cache_dirty:
        save_cache(CACHE_FILE, cache)

    if args.output:
        write_results(args.output, combined)

    if args.aggiorna and nuovi_nomi:
        update_names_file(names_file, existing_names, nuovi_nomi)


if __name__ == "__main__":
    main()
