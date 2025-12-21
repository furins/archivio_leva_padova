# FINALITÀ
Il progetto cerca di risolvere alcuni limiti all'interfaccia di ricerca dell'Archivio di Stato di Padova. In particolare:
- la ricerca quando si conosce solo il cognome, o parte di esso
- la ricerca sulla base del cognome della madre

# INSTALLAZIONE E UTILIZZO
Il programma può essere scaricato dalla repository github. Una volta clonata la sorgente lanciare i seguenti comandi:
```
uv sync
sudo apt install direnv
uv run leva-cli --config-env
direnv allow
```

**spiegazione dei comandi:**
```
uv sync
```
Installa le librerie necessarie al programma

```
sudo apt install direnv
```
Installa direnv (se già installato non causa problemi)

```
uv run leva-cli --config-env
```
Avvia una procedura guidata che legge eventuali credenziali già presenti in `.envrc`, propone quei valori come default e salva le nuove informazioni nel file (oltre a impostarle nella sessione corrente) così che `direnv` possa caricarle automaticamente.

```
direnv allow
```
Applica le modifiche


# FEATURES
Questo progetto automatizza la consultazione dell'archivio di leva di Padova e Rovigo. Si occupa di:
- Effettuare il login con le credenziali configurate in ambiente.
- Eseguire ricerche per uno o più cognomi utilizzando combinazioni di tre lettere derivate dai nomi noti.
- Deduplicare e mostrare i risultati direttamente a terminale oppure salvarli in formato tabulato.
- Aggiornare automaticamente il dizionario dei nomi nel database quando ne vengono trovati di nuovi.
- Gestire una cache locale per evitare richieste ripetute al sito.

## Opzioni della CLI

Il comando principale è `leva-cli`. Ogni opzione è descritta qui sotto con un esempio d'uso.

### Cognomi (argomenti posizionali)
Permette di passare uno o più cognomi (o parti di essi) da cercare. Se non si fornisce nessun cognome è necessario usare `--config-env`, `--search`, `--queue-status` o `--list-surnames`.

```
uv run leva-cli Rossi Bianchi
```

### `--no-cache`
Disabilita la cache locale delle richieste. Utile se si sospetta che i dati sul sito siano stati aggiornati e si vuole forzare nuove interrogazioni.

```
uv run leva-cli Rossi --no-cache
```

### `-o`, `--output`
Salva i risultati della sessione in un file TSV oltre a stamparli a video. La directory viene creata se non esiste.

```
uv run leva-cli Rossi --output risultati/rossi.tsv
```

### `--force-exact`
Forza la ricerca sul cognome esatto (evita corrispondenze parziali).

```
uv run leva-cli "De Rossi" --force-exact
```

### `--surname-match`
Imposta la modalità di ricerca del cognome: `partial` (default), `exact` o `soundex`. È un'alternativa a `--force-exact`.

```
uv run leva-cli "De Rossi" --surname-match exact
uv run leva-cli Rossi --surname-match soundex
```

### `--import-names FILE`
Importa un elenco iniziale di nomi nel database. Il file serve solo come base iniziale: dopo l'import, il database diventa l'unica fonte dei nomi e si aggiorna automaticamente.

```
uv run leva-cli --import-names data/nomi.txt
```

### `--db`
Specifica il percorso del database SQLite da usare per cache, deduplica e ricerche locali. Se non indicato viene usato `risultati/leva.sqlite`.

```
uv run leva-cli Rossi --db risultati/leva.sqlite
```

### `--search`
Esegue una ricerca nel database locale usando una regexp. È utile per filtrare risultati già scaricati senza interrogare il server.

```
uv run leva-cli --search "Francesco"
```

### `--search-fields`
Limita i campi su cui applicare la regexp di `--search`. I campi vanno separati da virgola e possono essere ad esempio `cognome,nome,localita`.

```
uv run leva-cli --search "Francesco" --search-fields "nome,cognome"
```

### `--search-limit`
Limita il numero di risultati restituiti dalla ricerca locale (`--search`).

```
uv run leva-cli --search "Rossi" --search-limit 20
```

### `--config-env`
Avvia una procedura guidata per impostare username e password in `.envrc`. Se sono già presenti vengono proposti come default.

```
uv run leva-cli --config-env
```

### `--queue-status`
Mostra l'elenco dei cognomi noti e lo stato delle interrogazioni in coda (utile per vedere cosa è già stato processato).

```
uv run leva-cli --queue-status
```

### `--list-surnames`
Stampa tutti i cognomi noti salvati nel database locale.

```
uv run leva-cli --list-surnames
```

### `--batch-size`
Numero massimo di cognomi da processare per iterazione della coda quando si lanciano più cognomi insieme. Il valore predefinito è 10.

```
uv run leva-cli Rossi Bianchi Verdi --batch-size 5
```

### `--max-iterations`
Numero massimo di iterazioni della coda per evitare loop infiniti. Il valore predefinito è 100.

```
uv run leva-cli Rossi Bianchi --max-iterations 50
```

## Algoritmo di ricerca ottimizzato

Il programma riduce le richieste al server combinando cache locale e inferenza sulle triplette (sequenze di tre lettere). L'idea è che alcune triplette compaiono **sempre** negli stessi nomi (o in un sottoinsieme) rispetto ad altre: se una tripla è già stata interrogata e copre tutte le occorrenze di un'altra, la seconda richiesta può essere evitata perché i risultati sono già noti.

### Passi principali
1. **Generazione delle triplette dai nomi noti**  
   Dal database locale vengono estratte tutte le triplette (finestre di 3 caratteri) per ogni nome. Si contano le occorrenze per stabilire l'ordine di ricerca. Se il database è vuoto è possibile inizializzarlo una sola volta con `--import-names`.

2. **Costruzione della copertura**  
   Per ogni tripletta viene costruito l'insieme degli indici dei nomi in cui compare. Questo permette di stabilire se una tripletta A è un sottoinsieme di un'altra tripletta B (ovvero, ogni nome che contiene A contiene anche B).

3. **Cache delle ricerche già fatte**  
   Ogni richiesta al sito viene salvata nel database locale con la chiave `(cognome, tripletta, cognome_esatto)` e il numero di risultati. Alla successiva esecuzione si recuperano tutte le triplette già consultate per quel cognome.

4. **Inferenza prima della richiesta**  
   Per ogni tripletta da processare:
   - se è presente in cache, la richiesta viene saltata;
   - altrimenti, si cerca una tripletta già in cache che la **copra** (insieme di nomi più ampio o uguale). Se esiste, la richiesta viene saltata perché i risultati sono deducibili.

5. **Richiesta solo se necessaria**  
   Solo quando non c'è cache né copertura si invia la richiesta al server, salvando poi i risultati e aggiornando la cache.

### Benefici
- **Meno richieste** al server a parità di risultati.
- **Riduzione del carico** grazie a cache e inferenza deterministica.
- **Velocità maggiore** nelle esecuzioni successive.

## Esempi di utilizzo

Ricordati di lanciare `direnv allow` la prima volta nella cartella del progetto così che username e password siano caricati dalle variabili d'ambiente definite in `.envrc`.

### Base (dopo import iniziale dei nomi)
```
uv run leva-cli Rossi
```
Cerca il cognome Rossi utilizzando i nomi salvati nel database locale e stampa i risultati sullo standard output.

### Più cognomi nella stessa sessione
```
uv run leva-cli Rossi Bianchi Verdi
```
Esegue tre ricerche consecutive riutilizzando la stessa sessione autenticata.

### Salvataggio dei risultati su file
```
uv run leva-cli Rossi --output risultati/rossi.tsv
```
Stampa i risultati e li salva anche nel file TSV indicato (la directory viene creata se non esiste).

### Ricerca senza cache
```
uv run leva-cli Rossi --no-cache
```
Ignora la cache locale (utile se il sito ha aggiornato i dati e vuoi forzare nuove richieste).

### Ricerca con cognome esatto
```
uv run leva-cli "De Rossi" --force-exact
```
Limita la ricerca al cognome esatto, evitando corrispondenze parziali.

### Import iniziale dei nomi
```
uv run leva-cli --import-names data/nomi.txt
```
Carica i nomi dal file nel database. Da questo momento in poi il database è la fonte unica dei nomi e viene aggiornato automaticamente quando si trovano nuovi risultati.
