Questo progetto automatizza la consultazione dell'archivio di leva di Padova e Rovigo. Si occupa di:
- Effettuare il login con le credenziali configurate in ambiente.
- Eseguire ricerche per uno o più cognomi utilizzando combinazioni di tre lettere derivate dai nomi noti.
- Deduplicare e mostrare i risultati direttamente a terminale oppure salvarli in formato tabulato.
- Aggiornare automaticamente il dizionario dei nomi quando ne vengono trovati di nuovi.
- Gestire una cache locale per evitare richieste ripetute al sito.

## Esempi di utilizzo

Ricordati di lanciare `direnv allow` la prima volta nella cartella del progetto così che username e password siano caricati dalle variabili d'ambiente definite in `.envrc`.

### Base
```
python -m src.cli Rossi
```
Cerca il cognome Rossi utilizzando il file `data/nomi.txt` e stampa i risultati sullo standard output.

### Più cognomi nella stessa sessione
```
python -m src.cli Rossi Bianchi Verdi
```
Esegue tre ricerche consecutive riutilizzando la stessa sessione autenticata.

### Salvataggio dei risultati su file
```
python -m src.cli Rossi --output risultati/rossi.tsv
```
Stampa i risultati e li salva anche nel file TSV indicato (la directory viene creata se non esiste).

### Ricerca senza cache
```
python -m src.cli Rossi --no-cache
```
Ignora la cache locale (utile se il sito ha aggiornato i dati e vuoi forzare nuove richieste).

### Ricerca con cognome esatto
```
python -m src.cli "De Rossi" --force-exact
```
Limita la ricerca al cognome esatto, evitando corrispondenze parziali.

### Aggiornare il dizionario dei nomi
```
python -m src.cli Rossi --aggiorna data/nomi.txt
```
Oltre alle ricerche, aggiunge alla lista dei nomi qualsiasi nuovo nome scoperto e salva l’elenco aggiornato.
