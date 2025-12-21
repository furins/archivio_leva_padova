import requests
from bs4 import BeautifulSoup

from libraries.secrets import Secrets
from datetime import datetime


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

    def __init__(self):
        login_url = "https://archiviodistato.provincia.padova.it/leva/login.php"

        payload = {
            "username": Secrets.username,
            "password": Secrets.password,
            "code": "log",
            "sent": "sent",
        }

        session_requests = requests.session()
        result = session_requests.post(
            login_url,
            data=payload,
            headers=dict(referer=login_url)
        )
        self.ok = result.ok
        if self.ok:
            self.request = session_requests
        else:
            raise BaseException(result.status_code)

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

        result = self.request.post(
            search_url,
            data=payload,
            headers=dict(referer=search_url)
        )

        return TabellaLeva(
            tree=BeautifulSoup(result.text,
                               'html.parser'),
            cognome_richiesto=cognome,
            cognome_esatto=cognome_esatto
        ).parsed


class RicercaLeva:
    def __init__(self, cognome, triplette, cognome_esatto) -> None:
        self.ricerche = set()
        self.triplette = triplette
        self.cognome_esatto = cognome_esatto
        self.cognome = cognome

    def search(self, filename=None, dump=True):
        connessione = LevaPadova()

        idx = 0
        totale = len(self.triplette.lista)
        lunghezza_str = len(str(totale))
        for tripletta, conteggio in self.triplette.lista.items():
            idx += 1
            cognome = self.cognome.strip()
            risultati = connessione.query(
                cognome,
                tripletta,
                cognome_esatto=self.cognome_esatto
            )
            print(
                f"[{idx:{lunghezza_str}}/{totale}]{cognome} {tripletta} {len(risultati)}")
            for el in risultati:
                r = (el[0], el[1], str(el[3])[:10], el[4], el[5],
                     el[7], el[8], el[9], el[10],)
                self.ricerche.add(r)
            if dump and filename is not None:
                self.dump(filename)

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
