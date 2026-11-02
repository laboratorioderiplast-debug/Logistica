"""
Script diagnostico: fotografa lo stato completo di un documento (testata
DOTes + righe DORig) e lo salva su file. Si usa in coppia, prima e dopo
un'azione fatta manualmente dentro ARCA, per capire ESATTAMENTE quali
campi vengono modificati da un'operazione (es. "genera bolla da LP").

USO CONSIGLIATO (fallo su ADB_DERIPROVA, non sul database di produzione):

  1. In ARCA, apri o crea una Lista di Prelievo di prova. Annotati il
     numero doc (NumeroDoc) che vedi in ARCA.
  2. Trova il suo Id_DOTes:
         python snapshot_documento.py --trova-id LP <numero_doc>
  3. Fotografa lo stato PRIMA:
         python snapshot_documento.py <id_dotes> prima.json
  4. Dentro ARCA, premi il pulsante che genera la bolla dalla LP.
  5. Fotografa lo stato DOPO:
         python snapshot_documento.py <id_dotes> dopo.json
  6. Confronta i due file (anche solo aprendoli affiancati, o mandameli
     entrambi) per vedere quali campi sono cambiati.

  Nota: il punto 4-5 in genere crea anche un DOCUMENTO NUOVO (la bolla
  stessa). Se conosci anche il suo numero, fotografalo a parte con lo
  stesso script per vedere come e' popolato un documento "figlio".
"""

import json
import sys
from datetime import datetime, date
from decimal import Decimal

from database import arca_connection


def _json_safe(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.hex()
    return value


def trova_id(cd_do: str, numero_doc: str):
    query = "SELECT Id_DOTes FROM DOTes WHERE Cd_DO = ? AND NumeroDoc = ?"
    with arca_connection() as conn:
        cur = conn.cursor()
        # Cd_DO e' char(3): proviamo sia col padding che senza
        for candidato in (cd_do, cd_do.ljust(3)):
            cur.execute(query, candidato, numero_doc)
            righe = cur.fetchall()
            if righe:
                for r in righe:
                    print(f"Trovato Id_DOTes = {r[0]}")
                return
        print("Nessun documento trovato con questo Cd_DO/NumeroDoc.")


def fotografa(id_dotes: str, path_output: str):
    with arca_connection() as conn:
        cur = conn.cursor()

        cur.execute("SELECT * FROM DOTes WHERE Id_DOTes = ?", id_dotes)
        cols = [c[0] for c in cur.description]
        testata_row = cur.fetchone()
        testata = dict(zip(cols, testata_row)) if testata_row else None

        cur.execute("SELECT * FROM DORig WHERE Id_DOTes = ? ORDER BY Id_DORig", id_dotes)
        cols = [c[0] for c in cur.description]
        righe = [dict(zip(cols, r)) for r in cur.fetchall()]

    snapshot = {
        "id_dotes": id_dotes,
        "catturato_il": datetime.now().isoformat(),
        "testata": testata,
        "righe": righe,
    }

    with open(path_output, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, default=_json_safe, ensure_ascii=False)

    print(f"Salvato snapshot di Id_DOTes={id_dotes} in {path_output}")
    print(f"Testata trovata: {'si' if testata else 'NO - controlla id'}")
    print(f"Righe trovate: {len(righe)}")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--trova-id":
        trova_id(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 3:
        fotografa(sys.argv[1], sys.argv[2])
    else:
        print(__doc__)
