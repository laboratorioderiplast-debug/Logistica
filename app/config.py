"""
Caricamento della configurazione da config.ini.

Tenuto volutamente semplice: un unico oggetto Config con attributi,
cosi' il resto del programma non deve mai leggere ConfigParser
direttamente.
"""
import configparser
import os
import sys


def _app_dir():
    """Cartella dove si trova l'eseguibile/script (funziona anche da .exe PyInstaller)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _default_local_db_path():
    appdata = os.environ.get("APPDATA")
    if appdata:
        folder = os.path.join(appdata, "CertificatiEN31")
    else:
        folder = os.path.join(_app_dir(), "dati")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "dati.db")


class Config:
    def __init__(self, path=None):
        self.path = path or os.path.join(_app_dir(), "config.ini")
        parser = configparser.ConfigParser()
        if os.path.exists(self.path):
            parser.read(self.path, encoding="utf-8")

        arca = parser["arca"] if "arca" in parser else {}
        tabelle = parser["arca_tabelle"] if "arca_tabelle" in parser else {}
        app = parser["app"] if "app" in parser else {}

        # --- connessione Arca ---
        self.driver = arca.get("driver", "ODBC Driver 17 for SQL Server")
        self.server = arca.get("server", "")
        self.database = arca.get("database", "")
        self.trusted_connection = arca.get("trusted_connection", "yes")
        self.timeout = int(arca.get("timeout", "5"))

        # --- tabelle Arca ---
        self.tabella_articoli = tabelle.get("tabella_articoli", "ARCA_ARTICOLI")
        self.campo_codice_articolo = tabelle.get("campo_codice_articolo", "CODICE_AR")
        self.campo_descrizione = tabelle.get("campo_descrizione", "Descrizione")
        self.campo_norma = tabelle.get("campo_norma", "Norma")
        self.campo_famiglia = tabelle.get("campo_famiglia", "Famiglia")
        self.campo_applicazione = tabelle.get("campo_applicazione", "Applicazione")
        self.campo_pn = tabelle.get("campo_pn", "PN")
        self.campo_sdr = tabelle.get("campo_sdr", "SDR")
        self.campo_de = tabelle.get("campo_de", "DE")
        self.campo_diam_min = tabelle.get("campo_diam_min", "")
        self.campo_diam_max = tabelle.get("campo_diam_max", "")
        self.campo_spess_min = tabelle.get("campo_spess_min", "")
        self.campo_spess_max = tabelle.get("campo_spess_max", "")
        self.campo_ovalizzazione = tabelle.get("campo_ovalizzazione", "")

        self.vista_op = tabelle.get("vista_op", "VV_Arca")
        self.campo_op_lotto = tabelle.get("campo_op_lotto", "LOTTO")
        self.campo_op_data = tabelle.get("campo_op_data", "DataDoc")
        self.campo_op_codice_articolo = tabelle.get("campo_op_codice_articolo", "Cd_AR")
        self.campo_op_linea = tabelle.get("campo_op_linea", "LINEA")
        self.campo_op_turno = tabelle.get("campo_op_turno", "Nav_Turno")
        self.campo_op_descrizione = tabelle.get("campo_op_descrizione", "Descrizione")
        self.campo_op_quantita = tabelle.get("campo_op_quantita", "QTA_MT")
        self.campo_op_id_riga = tabelle.get("campo_op_id_riga", "IDRIG")
        self.campo_op_diam_min = tabelle.get("campo_op_diam_min", "")
        self.campo_op_diam_max = tabelle.get("campo_op_diam_max", "")
        self.campo_op_spess_min = tabelle.get("campo_op_spess_min", "")
        self.campo_op_spess_max = tabelle.get("campo_op_spess_max", "")
        self.campo_op_dn = tabelle.get("campo_op_dn", "")

        # --- app ---
        self.ragione_sociale = app.get("ragione_sociale", "Deriplast Group")
        self.preparato_da = app.get("preparato_da", "")
        self.approvato_da = app.get("approvato_da", "")
        db_locale = app.get("db_locale", "").strip()
        self.db_locale = db_locale if db_locale else _default_local_db_path()
        self.modalita_demo = app.get("modalita_demo", "si").strip().lower() in (
            "si", "sì", "yes", "true", "1"
        )

    def assets_dir(self):
        return os.path.join(_app_dir(), "assets")

    def logo_path(self):
        return os.path.join(self.assets_dir(), "logo.jpg")

    def firma_path(self):
        return os.path.join(self.assets_dir(), "firma_buzzoni.png")


_config_instance = None


def get_config():
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance
