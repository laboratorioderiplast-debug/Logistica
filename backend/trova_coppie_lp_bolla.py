"""
Script di SOLA LETTURA: cerca documenti di tipo bolla (BI, BC, BE, BS...)
che sono stati generati da una Lista di Prelievo, usando i campi
NumeroDocRif/DataDocRif che ARCA valorizza automaticamente quando genera
un documento da un altro.

Non modifica nulla: e' sicuro da eseguire anche sul database di
produzione.

Uso:
    python trova_coppie_lp_bolla.py
    python trova_coppie_lp_bolla.py --dettaglio ID_LP ID_BOLLA
"""

import sys
from database import arca_connection

CODICI_BOLLA = ["BI ", "BC ", "BE ", "BS ", "BN ", "BO ", "BV ", "BT "]
CODICI_LP = ["LP ", "LM "]


def trova_coppie(limite: int = 15):
    """Usa DORig.Id_DORig_Evade: quando ARCA genera un documento da un
    altro, le righe del nuovo documento sembrano puntare, riga per riga,
    alla riga del documento di origine che "evadono". Risaliamo da li'
    ai due Id_DOTes (documento origine e documento generato)."""
    placeholders_bolla = ",".join("?" for _ in CODICI_BOLLA)
    placeholders_lp = ",".join("?" for _ in CODICI_LP)

    query = f"""
        SELECT DISTINCT TOP {limite}
            bolla_tes.Id_DOTes AS id_bolla,
            bolla_tes.Cd_DO AS cd_do_bolla,
            bolla_tes.NumeroDoc AS numero_bolla,
            bolla_tes.DataDoc AS data_bolla,
            lp_tes.Id_DOTes AS id_lp,
            lp_tes.Cd_DO AS cd_do_lp,
            lp_tes.NumeroDoc AS numero_lp,
            lp_tes.DataDoc AS data_lp
        FROM DORig bolla_rig
        INNER JOIN DOTes bolla_tes ON bolla_tes.Id_DOTes = bolla_rig.Id_DOTes
        INNER JOIN DORig lp_rig ON lp_rig.Id_DORig = bolla_rig.Id_DORig_Evade
        INNER JOIN DOTes lp_tes ON lp_tes.Id_DOTes = lp_rig.Id_DOTes
        WHERE bolla_tes.Cd_DO IN ({placeholders_bolla})
          AND lp_tes.Cd_DO IN ({placeholders_lp})
          AND bolla_rig.Id_DORig_Evade IS NOT NULL
        ORDER BY bolla_tes.DataDoc DESC
    """
    with arca_connection() as conn:
        cur = conn.cursor()
        cur.execute(query, CODICI_BOLLA + CODICI_LP)
        cols = [c[0] for c in cur.description]
        righe = [dict(zip(cols, r)) for r in cur.fetchall()]

    if not righe:
        print("Nessuna coppia trovata con questo criterio (NumeroDocRif/DataDocRif).")
        print("Puo' darsi che il collegamento venga tracciato diversamente.")
        return

    print(f"Trovate {len(righe)} coppie LP -> Bolla:\n")
    for r in righe:
        print(
            f"  LP: Id={r['id_lp']:<8} {r['cd_do_lp']}{r['numero_lp']} del {r['data_lp']}   "
            f"->   Bolla: Id={r['id_bolla']:<8} {r['cd_do_bolla']}{r['numero_bolla']} del {r['data_bolla']}"
        )

    print("\nPer confrontare le righe di una coppia specifica:")
    print("  python trova_coppie_lp_bolla.py --dettaglio ID_LP ID_BOLLA")


def confronta_dettaglio(id_lp: str, id_bolla: str):
    query = """
        SELECT Id_DORig, Cd_AR, Descrizione, Qta, QtaEvadibile, QtaEvasa,
               Evadibile, Id_DORig_Evade
        FROM DORig
        WHERE Id_DOTes = ?
        ORDER BY Id_DORig
    """
    with arca_connection() as conn:
        cur = conn.cursor()

        print(f"=== Righe della LP (Id_DOTes={id_lp}) ===")
        cur.execute(query, id_lp)
        cols = [c[0] for c in cur.description]
        for r in cur.fetchall():
            print(dict(zip(cols, r)))

        print(f"\n=== Righe della Bolla (Id_DOTes={id_bolla}) ===")
        cur.execute(query, id_bolla)
        cols = [c[0] for c in cur.description]
        for r in cur.fetchall():
            print(dict(zip(cols, r)))


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--dettaglio":
        confronta_dettaglio(sys.argv[2], sys.argv[3])
    else:
        trova_coppie()
