"""
Script di supporto: elenca tutti i database visibili sul server SQL
indicato in .env (ARCA_SERVER), per trovare il nome esatto del database
di ARCA (che di solito NON coincide con il nome della "ditta" mostrato
nella finestra di login di Arca, es. "DERIPLAST").

Si connette al database di sistema 'master', che esiste sempre ed e'
sempre accessibile in lettura con l'autenticazione Windows.

Uso:
    python list_databases.py
"""

import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()


def _connection_string_master() -> str:
    driver = os.getenv("ARCA_DRIVER", "{ODBC Driver 17 for SQL Server}")
    server = os.getenv("ARCA_SERVER")
    trusted = os.getenv("ARCA_TRUSTED_CONNECTION", "no").lower() == "yes"

    parts = [f"DRIVER={driver}", f"SERVER={server}", "DATABASE=master"]

    if trusted:
        parts.append("Trusted_Connection=yes")
    else:
        user = os.getenv("ARCA_USER")
        password = os.getenv("ARCA_PASSWORD")
        parts.append(f"UID={user}")
        parts.append(f"PWD={password}")

    return ";".join(parts)


def elenca_database():
    conn_str = _connection_string_master()
    print(f"Connessione a: SERVER={os.getenv('ARCA_SERVER')} (database master)...\n")

    conn = pyodbc.connect(conn_str, timeout=10)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sys.databases ORDER BY name")
    nomi = [row[0] for row in cur.fetchall()]
    conn.close()

    print(f"Trovati {len(nomi)} database sul server:\n")
    for n in nomi:
        print(f"  {n}")

    print("\nCerca un nome che assomiglia a 'DERIPLAST', 'ARCA', 'EVO' o simili.")
    print("Quello e' quasi certamente il valore da mettere in ARCA_DATABASE nel .env")


if __name__ == "__main__":
    try:
        elenca_database()
    except Exception as e:
        print(f"Errore di connessione: {e}")
        print("\nControlla in .env: ARCA_SERVER, ARCA_TRUSTED_CONNECTION,")
        print("e se serve autenticazione SQL invece che Windows, ARCA_USER/ARCA_PASSWORD.")
