import re
import time
from pathlib import Path
from typing import Iterable, Sequence

import requests
from bs4 import BeautifulSoup

from libraries.secrets import Secrets
from libraries.storage import (
    connect_db,
    fetch_cached_triplette,
    fetch_people,
    query_exists,
    record_query,
    upsert_people,
)
from datetime import datetime


def parse_mother_surname(madre: str) -> str | None:
    if not madre:
        return None
    cleaned = madre.strip()
    if not cleaned:
        return None
    match = re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ'`-]+", cleaned)
    if not match:
        return None
    surname = match.group(0).strip("`'-")
    if not surname:
        return None
    return surname.title()


class RigaLeva:
    parsed = ['']*11

    def __init__(self, tr_tree) -> None:
        self.parsed = []
        colonne = tr_tree.findAll("td")
        for idx, colonna in enumerate(colonne):
            self.parsed.append(self.formatta(
                colonna.get_text(strip=True), idx))

    def matches(self, cognome):
        return self.parsed[0].upper() == cognome.upper()

    def formatta(self, text, idx):
        def format_place(place):
            place = place.replace(' Di ', ' di ')
            place = place.replace(' In ', ' in ')
            place = place.replace(' Con ', ' con ')
            place = place.replace(' E ', ' e ')
            return place

        if idx in (0, 1, 9, 10):
            return text.title().replace('!', '').replace('?', '')
        if idx == 2:
            return int(text.replace(',00', ''))
        if idx == 3:
            return datetime.strptime(text, '%d/%m/%Y')
        if idx in (4, 7, 8):
            return format_place(text.title())
        if idx == 5:
            return text.upper()
        if idx == 6:
            return int(text)


class TabellaLeva:
    def __init__(self, tree, cognome_richiesto, cognome_esatto=True) -> None:
        tabella = tree.find("table", {"class": "table-risultati"})
        self.parsed = []
        for riga in tabella.find("tbody").findAll("tr"):
            dati_riga = RigaLeva(riga)
            if not cognome_esatto:
                self.parsed.append(dati_riga.parsed)
            else:
                if dati_riga.matches(cognome_richiesto):
                    self.parsed.append(dati_riga.parsed)


class LevaPadova:
    request = None
    ok = False
    timeout = (5, 20)
    max_retries = 3
    backoff_seconds = 1.0

    def __init__(self):
        login_url = "https://archiviodistato.provincia.padova.it/leva/login.php"

        payload = {
            "username": Secrets.username,
            "password": Secrets.password,
            "code": "log",
            "sent": "sent",
        }

        session_requests = requests.session()
        self.request = session_requests
        result = self._post_with_retry(
            login_url,
            data=payload,
            headers=dict(referer=login_url),
        )
        self.ok = result.ok
        if self.ok:
            self.request = session_requests
        else:
            raise BaseException(result.status_code)

    def _post_with_retry(self, url, data, headers):
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                response = self.request.post(
                    url,
                    data=data,
                    headers=headers,
                    timeout=self.timeout,
                )
                if response.status_code in {408, 429} or response.status_code >= 500:
                    if attempt < self.max_retries - 1:
                        time.sleep(self.backoff_seconds * (2 ** attempt))
                        continue
                return response
            except requests.exceptions.RequestException as exc:
                last_exception = exc
                if attempt < self.max_retries - 1:
                    time.sleep(self.backoff_seconds * (2 ** attempt))
                    continue
                raise
        if last_exception:
            raise last_exception
        raise RuntimeError("Tentativo di richiesta fallito.")

    def query(self, cognome, nome, cognome_esatto=True):
        # a questo punto ho effettuato il login
        search_url = "https://archiviodistato.provincia.padova.it/leva/consulta.php"
        payload = {
            "cognome": cognome,
            "nome": nome,
            "ricerca": "si",
            "madre": "",
            "localita": "",
            "nascita": "",
            "giorno": "",
            "mese": "",
            "anno": "",
            "ord": "cognome",
            "leva": "Esegui ricerca"
        }

        result = self._post_with_retry(
            search_url,
            data=payload,
            headers=dict(referer=search_url),
        )

        return TabellaLeva(
            tree=BeautifulSoup(result.text,
                               'html.parser'),
            cognome_richiesto=cognome,
            cognome_esatto=cognome_esatto
        ).parsed


class RicercaLeva:
    def __init__(
        self,
        cognome,
        triplette,
        cognome_esatto,
        db_path: Path | None = None,
        rate_limit_seconds: float = 0.0,
    ) -> None:
        self.ricerche = set()
        self.triplette = triplette
        self.cognome_esatto = cognome_esatto
        self.cognome = cognome
        self.db_path = db_path or Path("risultati/leva.sqlite")
        self.rate_limit_seconds = rate_limit_seconds

    @staticmethod
    def _format_row(raw_row: Sequence[object]) -> tuple[str, ...]:
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

    @staticmethod
    def _format_cached_rows(rows: Iterable[Sequence[object]]) -> list[tuple[str, ...]]:
        formatted: list[tuple[str, ...]] = []
        for row in rows:
            formatted.append(tuple("" if value is None else str(value) for value in row))
        return formatted

    def search(self, filename=None, dump=True):
        connessione = LevaPadova()
        db_conn = connect_db(self.db_path) if self.db_path else None

        idx = 0
        totale = len(self.triplette.lista)
        lunghezza_str = len(str(totale))
        cached_triplette = set()
        try:
            if db_conn:
                cached_triplette = fetch_cached_triplette(
                    db_conn,
                    self.cognome.strip(),
                    self.cognome_esatto,
                )
            for tripletta, conteggio in self.triplette.lista.items():
                idx += 1
                cognome = self.cognome.strip()
                if db_conn and query_exists(db_conn, cognome, tripletta, self.cognome_esatto):
                    print(
                        f"[{idx:{lunghezza_str}}/{totale}]{cognome} {tripletta} (cache)"
                    )
                    cached_triplette.add(tripletta)
                    continue
                covering = self.triplette.covering_triplette(tripletta, cached_triplette)
                if db_conn and covering:
                    print(
                        f"[{idx:{lunghezza_str}}/{totale}]{cognome} {tripletta} "
                        f"(inferenza da {covering})"
                    )
                    continue
                risultati = connessione.query(
                    cognome,
                    tripletta,
                    cognome_esatto=self.cognome_esatto
                )
                print(
                    f"[{idx:{lunghezza_str}}/{totale}]{cognome} {tripletta} {len(risultati)}")
                formatted = [self._format_row(row) for row in risultati]
                for row in formatted:
                    self.ricerche.add(row)
                if db_conn:
                    upsert_people(db_conn, formatted, fonte="leva_padova")
                    record_query(
                        db_conn,
                        cognome,
                        tripletta,
                        self.cognome_esatto,
                        len(risultati),
                    )
                    cached_triplette.add(tripletta)
                if self.rate_limit_seconds > 0:
                    time.sleep(self.rate_limit_seconds)
                if dump and filename is not None:
                    self.dump(filename)
            if db_conn:
                cached_rows = fetch_people(db_conn, self.cognome, self.cognome_esatto)
                for row in self._format_cached_rows(cached_rows):
                    self.ricerche.add(row)
        finally:
            if db_conn:
                db_conn.close()

    def dump(self, filename):
        dedup_list = list(map(list, self.ricerche))
        dedup_list.sort(key=lambda x: x[3])
        dedup_list.sort(key=lambda x: x[1])
        dedup_list.sort(key=lambda x: x[0])
        with open(filename, 'w') as f:
            for el in (('Cognome', 'Nome', 'Data di nascita', 'Luogo di nascita', 'Provincia', 'Comune iscrizione', 'Mandamento', 'Padre', 'Madre'),):
                f.write('\t'.join(el))
                f.write('\n')
            for el in dedup_list:
                f.write('\t'.join(el))
                f.write('\n')
