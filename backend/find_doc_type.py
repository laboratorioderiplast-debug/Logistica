"""
Cerca nella tabella anagrafica dbo.DO (tipi documento di ARCA) quale
codice corrisponde a "Lista di Prelievo", cosi' sappiamo quale valore
di Cd_DO cercare in DOTes/DORig.

Uso:
    python find_doc_type.py
"""

from database import arca_connection


def elenca_tipi_documento():
    with arca_connection() as conn:
        cur = conn.cursor()

        # Prima vediamo le colonne di dbo.DO per capire come si chiama
        # la colonna descrizione
        cur.execute(
            """
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'DO' ORDER BY ORDINAL_POSITION
            """
        )
        colonne = [r[0] for r in cur.fetchall()]
        print("Colonne di dbo.DO:")
        for c in colonne:
            print(f"  {c}")
        print()

        # Proviamo a leggere tutta la tabella (di solito sono poche righe:
        # e' un'anagrafica di tipi documento, non dati transazionali)
        cur.execute("SELECT * FROM dbo.DO")
        cols = [c[0] for c in cur.description]
        righe = cur.fetchall()

    print(f"Trovati {len(righe)} tipi documento:\n")
    for r in righe:
        riga = dict(zip(cols, r))
        print(riga)

    print("\nCerca a occhio la riga con descrizione tipo 'Lista di Prelievo'")
    print("o simile, e prendi nota del suo codice (di solito Cd_DO o simile).")


if __name__ == "__main__":
    try:
        elenca_tipi_documento()
    except Exception as e:
        print(f"Errore: {e}")
