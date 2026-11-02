"""
Mostra il contenuto grezzo dei possibili campi "note" sulla testata di
un documento (DOTes), per capire quale corrisponde alla casella
"Note principali" nella scheda Info di ARCA e in che formato e' salvato
(testo semplice o XML).

Uso:
    python ispeziona_note.py ID_DOTES
"""

import sys
from database import arca_connection


def ispeziona(id_dotes: str):
    query = """
        SELECT NotePiede, NoteXML, Attributi, ExtraInfo
        FROM DOTes
        WHERE Id_DOTes = ?
    """
    with arca_connection() as conn:
        cur = conn.cursor()
        cur.execute(query, id_dotes)
        row = cur.fetchone()

    if not row:
        print(f"Nessun documento trovato con Id_DOTes={id_dotes}")
        return

    cols = ["NotePiede", "NoteXML", "Attributi", "ExtraInfo"]
    for nome, valore in zip(cols, row):
        print(f"--- {nome} ---")
        print(repr(valore))
        print()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python ispeziona_note.py ID_DOTES")
    else:
        ispeziona(sys.argv[1])
