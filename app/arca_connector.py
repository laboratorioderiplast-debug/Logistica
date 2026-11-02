"""
Connessione ad Arca (SQL Server) in sola lettura, per recuperare:
  - Articoli  (tabella ARCA_ARTICOLI o equivalente)
  - Ordini di produzione / OP (vista VV_Arca o equivalente)

Usa autenticazione integrata di Windows (Trusted_Connection), come
il client Arca mostrato nello screenshot di login (Server / Ditta).

Nessuna password viene mai letta o salvata da questo modulo.

Se in config.ini "modalita_demo = si", le funzioni restituiscono
dati finti: utile per sviluppare/collaudare l'app senza essere sul
PC collegato alla rete aziendale.

IMPORTANTE: i nomi di tabella/campo usati qui sono quelli confermati
per l'app attuale, letti da config.ini (sezione [arca_tabelle]).
Se in futuro Arca cambia struttura, si aggiorna SOLO config.ini.
"""
from .config import get_config

try:
    import pyodbc
except ImportError:  # pyodbc non installato (es. ambiente di sviluppo su Linux/Mac)
    pyodbc = None


class ArcaConnectionError(Exception):
    pass


def _connection_string(cfg):
    parts = [
        f"DRIVER={{{cfg.driver}}}",
        f"SERVER={cfg.server}",
        f"DATABASE={cfg.database}",
    ]
    if str(cfg.trusted_connection).lower() in ("yes", "si", "sì", "true", "1"):
        parts.append("Trusted_Connection=yes")
    return ";".join(parts) + ";"


def get_connection():
    """Apre una connessione ad Arca. Solleva ArcaConnectionError se non riesce."""
    cfg = get_config()
    if pyodbc is None:
        raise ArcaConnectionError(
            "Il modulo 'pyodbc' non e' installato. Su Windows: pip install pyodbc "
            "(richiede anche il driver ODBC per SQL Server installato nel sistema)."
        )
    try:
        conn_str = _connection_string(cfg)
        return pyodbc.connect(conn_str, timeout=cfg.timeout)
    except Exception as exc:  # pragma: no cover - dipende dall'ambiente Windows/Arca
        raise ArcaConnectionError(
            f"Impossibile collegarsi ad Arca (server={cfg.server}, database={cfg.database}).\n"
            f"Dettaglio tecnico: {exc}\n\n"
            "Verifica: di essere sulla rete aziendale, che il Driver ODBC indicato in "
            "config.ini sia installato, e che il nome server/database sia corretto."
        ) from exc


def test_connection():
    """Ritorna (True, 'ok') oppure (False, messaggio_errore)."""
    cfg = get_config()
    if cfg.modalita_demo:
        return True, "Modalita' demo attiva: nessuna connessione reale ad Arca viene effettuata."
    try:
        conn = get_connection()
        conn.close()
        return True, "Connessione ad Arca riuscita."
    except ArcaConnectionError as exc:
        return False, str(exc)


# ---------------------------------------------------------------------------
# Dati finti per la modalita' demo
# ---------------------------------------------------------------------------
_DEMO_ARTICOLI = [
    {
        "codice_articolo": "AHNN01250010B13.40",
        "descrizione": "PE100 NOIR NF PN10 D.125X7,4MM M.13,40",
        "norma": "NF 114 - GR4 - PE100  e > 5 mm - APPLICAZIONI INDUSTRIALI, ACQUA NON POTABILE E FOGNA",
        "famiglia": "HDPE PIPE",
        "applicazione": "Acqua non potabile e fogna",
        "pn": "10",
        "sdr": "17",
        "de": "125",
        "diam_min": "125,00", "diam_max": "125,80",
        "spess_min": "7,40", "spess_max": "8,30",
        "ovalizzazione": "2,50",
    },
    {
        "codice_articolo": "AHNN02000010B13.40",
        "descrizione": "PE100 NOIR NF PN10 D.200X11,9MM",
        "norma": "NF 114 - GR4 - PE100  e > 5 mm - APPLICAZIONI INDUSTRIALI, ACQUA NON POTABILE E FOGNA",
        "famiglia": "HDPE PIPE",
        "applicazione": "Acqua non potabile e fogna",
        "pn": "10",
        "sdr": "17",
        "de": "200",
        "diam_min": "200,00", "diam_max": "200,90",
        "spess_min": "11,40", "spess_max": "12,60",
        "ovalizzazione": "3,00",
    },
]

_DEMO_OP = [
    {
        "lotto": "OP251856",
        "data": "2025-11-01",
        "codice_articolo": "AHNN01250010B13.40",
        "linea": "6",
        "turno": "M",
        "descrizione": "PE100 NOIR NF PN10 D.125X7,4MM M.13,40",
        "quantita": "1200",
        "id_riga": "1",
        "dn": "125",
        "diam_min": "125,00", "diam_max": "125,80",
        "spess_min": "7,40", "spess_max": "8,30",
    },
    {
        "lotto": "OP251900",
        "data": "2025-11-03",
        "codice_articolo": "AHNN02000010B13.40",
        "linea": "4",
        "turno": "P",
        "descrizione": "PE100 NOIR NF PN10 D.200X11,9MM",
        "quantita": "800",
        "id_riga": "2",
        "dn": "200",
        "diam_min": "200,00", "diam_max": "200,90",
        "spess_min": "11,40", "spess_max": "12,60",
    },
]


def _rows_to_dicts(cursor):
    columns = [c[0] for c in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _col_o_vuoto(nome_campo, alias):
    """Restituisce 'nome_campo AS alias', oppure una stringa vuota letterale
    se in config.ini quel campo non e' configurato (dato non disponibile
    in Arca per questa tabella)."""
    nome_campo = (nome_campo or "").strip()
    if not nome_campo:
        return f"'' AS {alias}"
    return f"{nome_campo} AS {alias}"


def cerca_articoli(testo_ricerca):
    """Cerca articoli per codice o descrizione (LIKE %testo%)."""
    cfg = get_config()
    testo_ricerca = (testo_ricerca or "").strip()

    if cfg.modalita_demo:
        t = testo_ricerca.lower()
        return [
            a for a in _DEMO_ARTICOLI
            if t in a["codice_articolo"].lower() or t in a["descrizione"].lower()
        ] if t else list(_DEMO_ARTICOLI)

    colonne = ", ".join([
        _col_o_vuoto(cfg.campo_codice_articolo, "codice_articolo"),
        _col_o_vuoto(cfg.campo_descrizione, "descrizione"),
        _col_o_vuoto(cfg.campo_norma, "norma"),
        _col_o_vuoto(cfg.campo_famiglia, "famiglia"),
        _col_o_vuoto(cfg.campo_applicazione, "applicazione"),
        _col_o_vuoto(cfg.campo_pn, "pn"),
        _col_o_vuoto(cfg.campo_sdr, "sdr"),
        _col_o_vuoto(cfg.campo_de, "de"),
        _col_o_vuoto(cfg.campo_diam_min, "diam_min"),
        _col_o_vuoto(cfg.campo_diam_max, "diam_max"),
        _col_o_vuoto(cfg.campo_spess_min, "spess_min"),
        _col_o_vuoto(cfg.campo_spess_max, "spess_max"),
        _col_o_vuoto(cfg.campo_ovalizzazione, "ovalizzazione"),
    ])
    sql = (
        f"SELECT {colonne} FROM {cfg.tabella_articoli} "
        f"WHERE {cfg.campo_codice_articolo} LIKE ? OR {cfg.campo_descrizione} LIKE ?"
    )
    like = f"%{testo_ricerca}%"
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, (like, like))
        return _rows_to_dicts(cur)
    finally:
        conn.close()


def cerca_op(testo_ricerca):
    """Cerca ordini di produzione per lotto o codice articolo (LIKE %testo%)."""
    cfg = get_config()
    testo_ricerca = (testo_ricerca or "").strip()

    if cfg.modalita_demo:
        t = testo_ricerca.lower()
        return [
            o for o in _DEMO_OP
            if t in o["lotto"].lower() or t in o["codice_articolo"].lower()
        ] if t else list(_DEMO_OP)

    colonne = ", ".join([
        _col_o_vuoto(cfg.campo_op_lotto, "lotto"),
        _col_o_vuoto(cfg.campo_op_data, "data"),
        _col_o_vuoto(cfg.campo_op_codice_articolo, "codice_articolo"),
        _col_o_vuoto(cfg.campo_op_linea, "linea"),
        _col_o_vuoto(cfg.campo_op_turno, "turno"),
        _col_o_vuoto(cfg.campo_op_descrizione, "descrizione"),
        _col_o_vuoto(cfg.campo_op_quantita, "quantita"),
        _col_o_vuoto(cfg.campo_op_id_riga, "id_riga"),
        _col_o_vuoto(cfg.campo_op_dn, "dn"),
        _col_o_vuoto(cfg.campo_op_diam_min, "diam_min"),
        _col_o_vuoto(cfg.campo_op_diam_max, "diam_max"),
        _col_o_vuoto(cfg.campo_op_spess_min, "spess_min"),
        _col_o_vuoto(cfg.campo_op_spess_max, "spess_max"),
    ])
    sql = (
        f"SELECT {colonne} FROM {cfg.vista_op} "
        f"WHERE {cfg.campo_op_lotto} LIKE ? OR {cfg.campo_op_codice_articolo} LIKE ?"
    )
    like = f"%{testo_ricerca}%"
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, (like, like))
        return _rows_to_dicts(cur)
    finally:
        conn.close()
