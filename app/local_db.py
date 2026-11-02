"""
Database locale (SQLite) per:
  - Certificati salvati (bozze / storico)
  - Anagrafica materie prime (MP)

E' un file unico sul PC (vedi config.ini -> db_locale), non serve
nessun server. Arca invece resta la fonte per Articoli e OP (vedi
arca_connector.py).
"""
import json
import os
import sqlite3
from datetime import datetime

from .config import get_config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS certificati (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    dati_json TEXT NOT NULL,
    creato_il TEXT NOT NULL,
    aggiornato_il TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS materie_prime (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fornitore TEXT,
    codice_lotto TEXT NOT NULL,
    materiale TEXT,
    mfi_dichiarato TEXT,
    carbon_black TEXT,
    umidita TEXT,
    densita TEXT,
    volatili TEXT,
    dispersione TEXT,
    oit TEXT,
    note TEXT,
    pdf_coa TEXT,
    creato_il TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS produzioni_storico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lotto TEXT,
    data TEXT,
    codice_articolo TEXT,
    descrizione TEXT,
    linea TEXT,
    turno TEXT,
    quantita TEXT,
    note TEXT,
    fonte_import TEXT,
    creato_il TEXT NOT NULL
);
"""


def _migra_schema(conn):
    """Aggiunge colonne nuove a database creati con versioni precedenti dell'app."""
    cur = conn.execute("PRAGMA table_info(materie_prime)")
    colonne = {row[1] for row in cur.fetchall()}
    nuove_colonne = {
        "pdf_coa": "TEXT",
        "carbon_black": "TEXT",
        "umidita": "TEXT",
        "densita": "TEXT",
        "volatili": "TEXT",
        "dispersione": "TEXT",
        "oit": "TEXT",
    }
    for nome, tipo in nuove_colonne.items():
        if nome not in colonne:
            conn.execute(f"ALTER TABLE materie_prime ADD COLUMN {nome} {tipo}")
    conn.commit()


def _connect():
    cfg = get_config()
    os.makedirs(os.path.dirname(cfg.db_locale), exist_ok=True)
    conn = sqlite3.connect(cfg.db_locale)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _connect()
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
        _migra_schema(conn)
    finally:
        conn.close()


def cartella_coa():
    """Cartella dove vengono conservate le copie dei PDF CoA importati."""
    cfg = get_config()
    folder = os.path.join(os.path.dirname(cfg.db_locale), "coa_pdf")
    os.makedirs(folder, exist_ok=True)
    return folder


def _now():
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Certificati
# ---------------------------------------------------------------------------
def salva_certificato(nome, dati_dict, id_esistente=None):
    """Crea o aggiorna un certificato salvato. Ritorna l'id."""
    conn = _connect()
    try:
        payload = json.dumps(dati_dict, ensure_ascii=False)
        if id_esistente:
            conn.execute(
                "UPDATE certificati SET nome=?, dati_json=?, aggiornato_il=? WHERE id=?",
                (nome, payload, _now(), id_esistente),
            )
            conn.commit()
            return id_esistente
        cur = conn.execute(
            "INSERT INTO certificati (nome, dati_json, creato_il, aggiornato_il) VALUES (?, ?, ?, ?)",
            (nome, payload, _now(), _now()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def elenco_certificati():
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT id, nome, creato_il, aggiornato_il FROM certificati ORDER BY aggiornato_il DESC"
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def carica_certificato(id_certificato):
    conn = _connect()
    try:
        cur = conn.execute("SELECT * FROM certificati WHERE id=?", (id_certificato,))
        row = cur.fetchone()
        if not row:
            return None
        result = dict(row)
        result["dati"] = json.loads(result["dati_json"])
        return result
    finally:
        conn.close()


def elimina_certificato(id_certificato):
    conn = _connect()
    try:
        conn.execute("DELETE FROM certificati WHERE id=?", (id_certificato,))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Materie prime (MP)
# ---------------------------------------------------------------------------
def aggiungi_materia_prima(fornitore, codice_lotto, materiale, mfi_dichiarato="", note="", pdf_coa="",
                            carbon_black="", umidita="", densita="", volatili="", dispersione="", oit=""):
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO materie_prime "
            "(fornitore, codice_lotto, materiale, mfi_dichiarato, carbon_black, umidita, densita, "
            " volatili, dispersione, oit, note, pdf_coa, creato_il) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (fornitore, codice_lotto, materiale, mfi_dichiarato, carbon_black, umidita, densita,
             volatili, dispersione, oit, note, pdf_coa, _now()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def elenco_materie_prime(filtro_testo=""):
    conn = _connect()
    try:
        if filtro_testo:
            like = f"%{filtro_testo}%"
            cur = conn.execute(
                "SELECT * FROM materie_prime WHERE fornitore LIKE ? OR codice_lotto LIKE ? OR materiale LIKE ? "
                "ORDER BY creato_il DESC",
                (like, like, like),
            )
        else:
            cur = conn.execute("SELECT * FROM materie_prime ORDER BY creato_il DESC")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def elimina_materia_prima(id_mp):
    conn = _connect()
    try:
        conn.execute("DELETE FROM materie_prime WHERE id=?", (id_mp,))
        conn.commit()
    finally:
        conn.close()


def importa_materie_prime_da_csv(percorso_csv):
    """
    Importa materie prime da un CSV con intestazioni:
    fornitore,codice_lotto,materiale,mfi_dichiarato,carbon_black,umidita,densita,volatili,dispersione,oit,note
    (le colonne mancanti vengono lasciate vuote). Ritorna il numero di righe importate.
    """
    import csv

    count = 0
    with open(percorso_csv, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("codice_lotto"):
                continue
            aggiungi_materia_prima(
                fornitore=row.get("fornitore", "").strip(),
                codice_lotto=row.get("codice_lotto", "").strip(),
                materiale=row.get("materiale", "").strip(),
                mfi_dichiarato=row.get("mfi_dichiarato", "").strip(),
                carbon_black=row.get("carbon_black", "").strip(),
                umidita=row.get("umidita", "").strip(),
                densita=row.get("densita", "").strip(),
                volatili=row.get("volatili", "").strip(),
                dispersione=row.get("dispersione", "").strip(),
                oit=row.get("oit", "").strip(),
                note=row.get("note", "").strip(),
            )
            count += 1
    return count


# ---------------------------------------------------------------------------
# Storico produzioni (import una tantum da vecchi archivi / database QUALITY)
# ---------------------------------------------------------------------------
def importa_produzioni_da_csv(percorso_csv, fonte="import CSV"):
    """
    Importa righe di produzione storiche da un CSV con intestazioni:
    lotto,data,codice_articolo,descrizione,linea,turno,quantita,note
    (le colonne mancanti vengono lasciate vuote). Ritorna il numero di
    righe importate.
    """
    import csv

    count = 0
    with open(percorso_csv, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        conn = _connect()
        try:
            for row in reader:
                if not (row.get("lotto") or row.get("codice_articolo")):
                    continue
                conn.execute(
                    "INSERT INTO produzioni_storico "
                    "(lotto, data, codice_articolo, descrizione, linea, turno, quantita, note, fonte_import, creato_il) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        row.get("lotto", "").strip(),
                        row.get("data", "").strip(),
                        row.get("codice_articolo", "").strip(),
                        row.get("descrizione", "").strip(),
                        row.get("linea", "").strip(),
                        row.get("turno", "").strip(),
                        row.get("quantita", "").strip(),
                        row.get("note", "").strip(),
                        fonte,
                        _now(),
                    ),
                )
                count += 1
            conn.commit()
        finally:
            conn.close()
    return count


def elenco_produzioni_storico(filtro_testo=""):
    conn = _connect()
    try:
        if filtro_testo:
            like = f"%{filtro_testo}%"
            cur = conn.execute(
                "SELECT * FROM produzioni_storico WHERE lotto LIKE ? OR codice_articolo LIKE ? "
                "ORDER BY creato_il DESC",
                (like, like),
            )
        else:
            cur = conn.execute("SELECT * FROM produzioni_storico ORDER BY creato_il DESC")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
