from __future__ import annotations

import contextlib
import io
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, RichLog, Static

from controller import DEFAULT_DB_FILE, ENVRC_PATH, read_envrc_values, run, write_envrc_values
from libraries.secrets import PASSWORD_ENV, USERNAME_ENV
from libraries.storage import connect_db


@dataclass
class FormField:
    name: str
    label: str
    kind: str = "text"
    placeholder: str = ""
    value: str = ""
    password: bool = False


class CommandForm(ModalScreen[Optional[Dict[str, object]]]):
    def __init__(
        self,
        title: str,
        fields: Iterable[FormField],
        on_submit: Callable[[Dict[str, object]], None],
    ) -> None:
        super().__init__()
        self.title = title
        self.fields = list(fields)
        self.on_submit = on_submit
        self._widgets: Dict[str, object] = {}

    def compose(self) -> ComposeResult:
        with Vertical(id="form-dialog"):
            yield Static(self.title, id="form-title")
            for field in self.fields:
                if field.kind == "bool":
                    checkbox = Checkbox(field.label, value=bool(field.value))
                    self._widgets[field.name] = checkbox
                    yield checkbox
                    continue
                with Horizontal(classes="form-row"):
                    yield Label(field.label, classes="form-label")
                    input_widget = Input(
                        value=field.value,
                        placeholder=field.placeholder,
                        password=field.password,
                        classes="form-input",
                    )
                    self._widgets[field.name] = input_widget
                    yield input_widget
            with Horizontal(id="form-actions"):
                yield Button("Annulla", id="cancel")
                yield Button("Esegui", id="submit", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        values: Dict[str, object] = {}
        for field in self.fields:
            widget = self._widgets[field.name]
            if field.kind == "bool":
                values[field.name] = widget.value
                continue
            raw = widget.value.strip()
            if field.kind == "int":
                values[field.name] = int(raw) if raw else None
            else:
                values[field.name] = raw
        self.dismiss(values)
        self.on_submit(values)


class WidgetWriter(io.TextIOBase):
    def __init__(self, app: App, targets: Iterable[RichLog]) -> None:
        super().__init__()
        self.app = app
        self.targets = list(targets)
        self._buffer = ""

    def write(self, message: str) -> int:
        if not message:
            return 0
        self._buffer += message
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._emit(line)
        return len(message)

    def flush(self) -> None:
        if self._buffer:
            self._emit(self._buffer)
            self._buffer = ""

    def _emit(self, line: str) -> None:
        if not line:
            return
        for target in self.targets:
            self.app.call_from_thread(target.write, line)


class LevaTuiApp(App):
    CSS = """
    #menu-bar {
        height: 3;
        background: $panel;
        padding: 0 1;
        align-horizontal: left;
    }
    #menu-bar Button {
        margin-right: 1;
    }
    #main-area {
        height: 1fr;
    }
    #log {
        width: 2fr;
        border: round $secondary;
    }
    #output {
        width: 1fr;
        border: round $accent;
    }
    #stats-bar {
        height: 3;
        background: $panel;
        padding: 0 1;
        align-horizontal: center;
    }
    #form-dialog {
        width: 80%;
        max-width: 80;
        padding: 1 2;
        border: round $accent;
        background: $panel;
    }
    .form-row {
        height: auto;
        margin-bottom: 1;
    }
    .form-label {
        width: 20;
    }
    .form-input {
        width: 1fr;
    }
    #form-actions {
        margin-top: 1;
        align-horizontal: right;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.current_db_path = DEFAULT_DB_FILE

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal(id="menu-bar"):
                yield Button("Esegui scraping", id="cmd-scrape")
                yield Button("Ricerca DB", id="cmd-search")
                yield Button("Importa nomi", id="cmd-import")
                yield Button("Stato coda", id="cmd-queue")
                yield Button("Configura .envrc", id="cmd-env")
                yield Button("Esci", id="cmd-exit", variant="error")
            with Horizontal(id="main-area"):
                yield RichLog(id="log", wrap=True, highlight=True)
                yield RichLog(id="output", wrap=True, highlight=True)
            with Horizontal(id="stats-bar"):
                yield Static("", id="stat-records")
                yield Static("", id="stat-names")
                yield Static("", id="stat-surnames")

    def on_mount(self) -> None:
        self.refresh_stats()
        self.set_interval(10, self.refresh_stats)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "cmd-exit":
            self.exit()
            return
        if button_id == "cmd-scrape":
            self.open_scrape_form()
        elif button_id == "cmd-search":
            self.open_search_form()
        elif button_id == "cmd-import":
            self.open_import_form()
        elif button_id == "cmd-queue":
            self.open_queue_form()
        elif button_id == "cmd-env":
            self.open_env_form()

    def log_widget(self) -> RichLog:
        return self.query_one("#log", RichLog)

    def output_widget(self) -> RichLog:
        return self.query_one("#output", RichLog)

    def refresh_stats(self) -> None:
        try:
            conn = connect_db(self.current_db_path)
            cursor = conn.execute("SELECT COUNT(*) FROM persons;")
            total_records = int(cursor.fetchone()[0])
            cursor = conn.execute("SELECT COUNT(DISTINCT nome) FROM persons;")
            unique_names = int(cursor.fetchone()[0])
            cursor = conn.execute("SELECT COUNT(DISTINCT cognome) FROM persons;")
            unique_surnames = int(cursor.fetchone()[0])
            conn.close()
        except Exception as exc:  # pragma: no cover - UI feedback only
            self.log_widget().write(f"Errore lettura statistiche: {exc}")
            return
        self.query_one("#stat-records", Static).update(
            f"Record DB: {total_records}"
        )
        self.query_one("#stat-names", Static).update(
            f"Nomi univoci: {unique_names}"
        )
        self.query_one("#stat-surnames", Static).update(
            f"Cognomi univoci: {unique_surnames}"
        )

    def open_scrape_form(self) -> None:
        fields = [
            FormField("surnames", "Cognomi (separati da virgola)", placeholder="Es. Rossi, Bianchi"),
            FormField("no_cache", "Disabilita cache", kind="bool"),
            FormField("force_exact", "Cognome esatto", kind="bool"),
            FormField("output", "File output TSV", placeholder="risultati/output.tsv"),
            FormField("db", "Percorso DB", value=str(self.current_db_path)),
            FormField("batch_size", "Batch size", kind="int", value="10"),
            FormField("max_iterations", "Max iterazioni", kind="int", value="100"),
        ]
        self.push_screen(CommandForm("Esegui scraping", fields, self.submit_scrape))

    def open_search_form(self) -> None:
        fields = [
            FormField("pattern", "Regexp di ricerca", placeholder="Es. ^Rossi$"),
            FormField("fields", "Campi (csv)", placeholder="cognome,nome"),
            FormField("limit", "Limite risultati", kind="int"),
            FormField("db", "Percorso DB", value=str(self.current_db_path)),
        ]
        self.push_screen(CommandForm("Ricerca nel database", fields, self.submit_search))

    def open_import_form(self) -> None:
        fields = [
            FormField("file", "File nomi", placeholder="data/nomi.txt"),
            FormField("db", "Percorso DB", value=str(self.current_db_path)),
        ]
        self.push_screen(CommandForm("Importa elenco nomi", fields, self.submit_import))

    def open_queue_form(self) -> None:
        fields = [
            FormField("force_exact", "Cognome esatto", kind="bool"),
            FormField("db", "Percorso DB", value=str(self.current_db_path)),
        ]
        self.push_screen(CommandForm("Stato coda cognomi", fields, self.submit_queue))

    def open_env_form(self) -> None:
        existing = read_envrc_values(ENVRC_PATH)
        fields = [
            FormField(USERNAME_ENV, "Username", value=existing.get(USERNAME_ENV, "")),
            FormField(
                PASSWORD_ENV,
                "Password",
                value=existing.get(PASSWORD_ENV, ""),
                password=True,
            ),
        ]
        self.push_screen(CommandForm("Configura .envrc", fields, self.submit_env))

    def submit_scrape(self, values: Dict[str, object]) -> None:
        surnames_raw = str(values.get("surnames", "")).strip()
        surnames = [item.strip() for item in surnames_raw.split(",") if item.strip()]
        if not surnames:
            self.output_widget().write("Inserire almeno un cognome da cercare.")
            return
        self._run_controller(
            args_namespace={
                "surnames": surnames,
                "no_cache": bool(values.get("no_cache")),
                "output": values.get("output") or None,
                "force_exact": bool(values.get("force_exact")),
                "import_names": None,
                "db": values.get("db") or None,
                "search": None,
                "search_fields": None,
                "search_limit": None,
                "config_env": False,
                "queue_status": False,
                "list_surnames": False,
                "batch_size": values.get("batch_size") or 10,
                "max_iterations": values.get("max_iterations") or 100,
            },
            output_targets=(self.log_widget(),),
        )

    def submit_search(self, values: Dict[str, object]) -> None:
        if not values.get("pattern"):
            self.output_widget().write("Inserire una regexp per la ricerca.")
            return
        self._run_controller(
            args_namespace={
                "surnames": [],
                "no_cache": False,
                "output": None,
                "force_exact": False,
                "import_names": None,
                "db": values.get("db") or None,
                "search": values.get("pattern") or None,
                "search_fields": values.get("fields") or None,
                "search_limit": values.get("limit"),
                "config_env": False,
                "queue_status": False,
                "list_surnames": False,
                "batch_size": 10,
                "max_iterations": 100,
            },
            output_targets=(self.output_widget(),),
        )

    def submit_import(self, values: Dict[str, object]) -> None:
        if not values.get("file"):
            self.output_widget().write("Specificare il file di nomi da importare.")
            return
        self._run_controller(
            args_namespace={
                "surnames": [],
                "no_cache": False,
                "output": None,
                "force_exact": False,
                "import_names": values.get("file") or None,
                "db": values.get("db") or None,
                "search": None,
                "search_fields": None,
                "search_limit": None,
                "config_env": False,
                "queue_status": False,
                "list_surnames": False,
                "batch_size": 10,
                "max_iterations": 100,
            },
            output_targets=(self.output_widget(),),
        )

    def submit_queue(self, values: Dict[str, object]) -> None:
        self._run_controller(
            args_namespace={
                "surnames": [],
                "no_cache": False,
                "output": None,
                "force_exact": bool(values.get("force_exact")),
                "import_names": None,
                "db": values.get("db") or None,
                "search": None,
                "search_fields": None,
                "search_limit": None,
                "config_env": False,
                "queue_status": True,
                "list_surnames": False,
                "batch_size": 10,
                "max_iterations": 100,
            },
            output_targets=(self.output_widget(),),
        )

    def submit_env(self, values: Dict[str, object]) -> None:
        def worker() -> None:
            self.output_widget().clear()
            try:
                write_envrc_values(
                    ENVRC_PATH,
                    {
                        USERNAME_ENV: str(values.get(USERNAME_ENV, "")).strip(),
                        PASSWORD_ENV: str(values.get(PASSWORD_ENV, "")).strip(),
                    },
                )
                os.environ[USERNAME_ENV] = str(values.get(USERNAME_ENV, ""))
                os.environ[PASSWORD_ENV] = str(values.get(PASSWORD_ENV, ""))
                self.output_widget().write("Variabili salvate in .envrc.")
            except Exception as exc:  # pragma: no cover - UI feedback only
                self.output_widget().write(f"Errore configurazione env: {exc}")

        self.run_worker(worker, thread=True)

    def _run_controller(
        self,
        args_namespace: Dict[str, object],
        output_targets: Iterable[RichLog],
    ) -> None:
        db_value = args_namespace.get("db")
        self.current_db_path = Path(db_value) if db_value else DEFAULT_DB_FILE
        for target in output_targets:
            target.clear()

        def worker() -> None:
            writer = WidgetWriter(self, output_targets)
            try:
                with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                    run(
                        type("Args", (), args_namespace),
                        envrc_path=ENVRC_PATH,
                        default_db_path=DEFAULT_DB_FILE,
                    )
            except Exception as exc:  # pragma: no cover - UI feedback only
                writer.write(f"Errore esecuzione comando: {exc}")
            finally:
                writer.flush()
                self.call_from_thread(self.refresh_stats)

        self.run_worker(worker, thread=True)


def main() -> None:
    LevaTuiApp().run()


if __name__ == "__main__":
    main()
