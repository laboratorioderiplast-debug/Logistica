"""
Cerca un documento per Cd_DO e un numero (anche parziale/con formato
incerto - slash, zeri iniziali, spazi).

Uso:
    python cerca_documento.py LP 1780
"""

import sys
from database import arca_connection


def cerca(cd_do: str, numero_parziale: str):
    query = """
        SELECT Id_DOTes, NumeroDoc, Cd_DO, DataDoc
        FROM DOTes
        WHERE RTRIM(Cd_DO) = ?
          AND NumeroDoc LIKE ?
        ORDER BY DataDoc DESC
    """
    with arca_connection() as conn:
        cur = conn.cursor()
        cur.execute(query, cd_do.strip(), f"%{numero_parziale}%")
        righe = cur.fetchall()

    if not righe:
        print("Nessun documento trovato.")
        return

    print(f"Trovati {len(righe)} documenti:")
    for r in righe:
        print(f"  Id_DOTes={r[0]}  NumeroDoc='{r[1]}'  Cd_DO='{r[2]}'  DataDoc={r[3]}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python cerca_documento.py CD_DO NUMERO_PARZIALE")
        print("Esempio: python cerca_documento.py LP 1780")
    else:
        cerca(sys.argv[1], sys.argv[2])
