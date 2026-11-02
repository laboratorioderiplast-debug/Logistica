"""
Script di supporto: cerca nel database ARCA le tabelle che
probabilmente riguardano le Liste di Prelievo, cosi' puoi
trovare i nomi reali da usare in arca_repository.py.

Uso:
    python discover_schema.py
    python discover_schema.py --colonne NOME_TABELLA_TROVATA
"""

import sys
from database import arca_connection

# Parole chiave plausibili: adattale se in ARCA si chiamano diversamente
# (es. "Ordini di Prelievo", "Picking List", "Prep. Bolla", ecc.)
KEYWORDS = ["LP", "PRELIEV", "PICKING", "LISTA"]


def elenca_tabelle_candidate():
    query = """
        SELECT TABLE_SCHEMA, TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_NAME
    """
    with arca_connection() as conn:
        cur = conn.cursor()
        cur.execute(query)
        tutte = cur.fetchall()

    print(f"Trovate {len(tutte)} tabelle totali nel database.\n")
    print("--- Tabelle il cui nome contiene una parola chiave LP/prelievo ---")
    for schema, nome in tutte:
        if any(k in nome.upper() for k in KEYWORDS):
            print(f"  {schema}.{nome}")

    print("\nSe non vedi nulla di sensato, apri la lista completa qui sotto")
    print("e cerca ad occhio (es. potrebbe chiamarsi 'ODP', 'PRE_BOLLA', ecc.):\n")
    for schema, nome in tutte:
        print(f"  {schema}.{nome}")


def mostra_colonne(nome_tabella: str):
    query = """
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = ?
        ORDER BY ORDINAL_POSITION
    """
    with arca_connection() as conn:
        cur = conn.cursor()
        cur.execute(query, nome_tabella)
        righe = cur.fetchall()

    if not righe:
        print(f"Nessuna colonna trovata per la tabella '{nome_tabella}'.")
        return

    print(f"Colonne di {nome_tabella}:")
    for nome_colonna, tipo, nullable in righe:
        print(f"  {nome_colonna:30s} {tipo:15s} NULL={nullable}")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--colonne":
        mostra_colonne(sys.argv[2])
    else:
        elenca_tabelle_candidate()
