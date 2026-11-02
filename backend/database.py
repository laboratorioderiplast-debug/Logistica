"""
Gestione delle due connessioni dati dell'app:

1. ARCA (SQL Server) - il gestionale. Vi si legge SEMPRE (nuovi LP) e vi si
   scrive SOLO nel momento della conferma finale del magazziniere.
2. app_state.db (SQLite locale) - "brutta copia" di lavoro: assegnazione
   tablet, quantita' modificate, righe cancellate, finche' non si conferma.

Tenere le due cose separate e' la scelta architetturale chiave: ARCA non
vede nulla finche' non e' tutto deciso.
"""

import os
import sqlite3
from contextlib import contextmanager

import pyodbc
from dotenv import load_dotenv

load_dotenv()

# ---------- ARCA (SQL Server) ----------

def _build_arca_connection_string() -> str:
    driver = os.getenv("ARCA_DRIVER", "{ODBC Driver 17 for SQL Server}")
    server = os.getenv("ARCA_SERVER")
    database = os.getenv("ARCA_DATABASE")
    trusted = os.getenv("ARCA_TRUSTED_CONNECTION", "no").lower() == "yes"

    parts = [f"DRIVER={driver}", f"SERVER={server}", f"DATABASE={database}"]

    if trusted:
        parts.append("Trusted_Connection=yes")
    else:
        user = os.getenv("ARCA_USER")
        password = os.getenv("ARCA_PASSWORD")
        parts.append(f"UID={user}")
        parts.append(f"PWD={password}")

    return ";".join(parts)


@contextmanager
def arca_connection():
    """Context manager per una connessione ad ARCA. Uso:

        with arca_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT ...")
    """
    conn_str = _build_arca_connection_string()
    conn = pyodbc.connect(conn_str, timeout=10)
    try:
        yield conn
    finally:
        conn.close()


# ---------- Database locale (SQLite) ----------

APP_DB_PATH = os.getenv("APP_DB_PATH", "./app_state.db")


@contextmanager
def app_connection():
    conn = sqlite3.connect(APP_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_app_db():
    with app_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tablets (
                id TEXT PRIMARY KEY,
                nome TEXT NOT NULL,
                ultimo_visto TEXT
            );

            CREATE TABLE IF NOT EXISTS lp_assegnazioni (
                lp_id TEXT PRIMARY KEY,
                tablet_id TEXT,
                camion_id TEXT,
                stato TEXT NOT NULL DEFAULT 'nuovo',
                -- stati: nuovo | inviato_tablet | confermato | bolla_creata
                nota_arca TEXT,
                nota_magazziniere TEXT DEFAULT '',
                creato_il TEXT DEFAULT CURRENT_TIMESTAMP,
                aggiornato_il TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS lp_righe_stato (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lp_id TEXT NOT NULL,
                riga_id_arca TEXT NOT NULL,
                articolo_codice TEXT,
                articolo_descrizione TEXT,
                quantita_originale REAL,
                quantita_corrente REAL,
                eliminata INTEGER DEFAULT 0,
                nota_riga TEXT DEFAULT '',
                caricata INTEGER DEFAULT 0,
                FOREIGN KEY (lp_id) REFERENCES lp_assegnazioni(lp_id)
            );

            CREATE TABLE IF NOT EXISTS camion (
                id TEXT PRIMARY KEY,
                nome TEXT NOT NULL,
                tablet_id TEXT NOT NULL,
                creato_il TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                chiave TEXT PRIMARY KEY,
                valore TEXT
            );

            CREATE TABLE IF NOT EXISTS pianificazione_carichi (
                id TEXT PRIMARY KEY,
                settimana TEXT NOT NULL,
                giorno TEXT NOT NULL,
                dati TEXT NOT NULL,
                aggiornato_il TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_pianificazione_settimana
                ON pianificazione_carichi(settimana, giorno);
            """
        )
        try:
            conn.execute("ALTER TABLE lp_assegnazioni ADD COLUMN camion_id TEXT")
        except sqlite3.OperationalError:
            pass  # colonna gia' presente
        # Migrazione per database locali creati prima dell'introduzione
        # delle note: aggiunge le colonne se mancano (ignora l'errore se
        # esistono gia').
        for colonna, tipo in [("nota_arca", "TEXT"), ("nota_magazziniere", "TEXT DEFAULT ''")]:
            try:
                conn.execute(f"ALTER TABLE lp_assegnazioni ADD COLUMN {colonna} {tipo}")
            except sqlite3.OperationalError:
                pass  # colonna gia' presente
        try:
            conn.execute("ALTER TABLE lp_righe_stato ADD COLUMN nota_riga TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # colonna gia' presente
        try:
            conn.execute("ALTER TABLE lp_righe_stato ADD COLUMN caricata INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # colonna gia' presente


if __name__ == "__main__":
    init_app_db()
    print(f"Database locale inizializzato in: {APP_DB_PATH}")
