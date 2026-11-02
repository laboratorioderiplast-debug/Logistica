"""
Questo file e' l'UNICO punto in cui il codice parla con le tabelle di ARCA.

Schema confermato dall'esplorazione fatta con discover_schema.py e
find_doc_type.py sul database ADB_DERIPLAST:

  - Il motore documenti di ARCA e' generico: DOTes (testata) / DORig (righe)
    per QUALSIASI tipo di documento.
  - Il tipo "Lista di Prelievo" corrisponde a Cd_DO = 'LP ' (char(3), con
    spazio finale!) - descrizione "LISTA PRELIEVO - Spedizione".
    Esiste anche 'LM ' ("LISTA PRELIEVO MGO - Spedizione"): se in azienda
    si usano entrambe le varianti, aggiungere anche 'LM ' al filtro sotto.

########################################################################
# CONFERMATO tramite confronto di coppie storiche reali LP -> Bolla
# (usando trova_coppie_lp_bolla.py):
#
#   - Su una LP non ancora evasa: Qta = QtaEvadibile, QtaEvasa = 0.
#   - Quando l'ufficio genera la bolla, ARCA legge QtaEvadibile (non
#     Qta) per decidere quanto trasferire nella riga generata.
#   - Dopo la generazione: sulla LP, QtaEvadibile scende a 0 e QtaEvasa
#     sale al valore trasferito; sulla bolla generata, la nuova riga ha
#     Qta = QtaEvadibile = QtaEvasa = valore preso dalla LP, e
#     Id_DORig_Evade punta alla riga della LP di origine.
#
# Conseguenza: quando il magazziniere modifica una quantita', dobbiamo
# aggiornare SIA Qta CHE QtaEvadibile sulla riga della LP, altrimenti
# l'ufficio genererebbe la bolla con la quantita' originale.
#
# Questo e' stato dedotto da dati storici reali (sola lettura, nessun
# rischio), non da un test diretto del pulsante "genera". Prima di un
# uso esteso in produzione, resta comunque consigliabile una verifica
# pratica: far modificare una quantita' su una LP di test tramite
# l'app, poi far generare la bolla all'ufficio come fanno normalmente,
# e controllare che la quantita' sulla bolla sia quella corretta.
########################################################################
"""

from database import arca_connection
import os

# Codice/i tipo documento che rappresentano una Lista di Prelievo.
# 'LP ' e 'LM ' hanno lo spazio finale perche' Cd_DO e' char(3) in ARCA.
CODICI_LISTA_PRELIEVO = ["LP ", "LM "]


def get_nuovi_lp() -> list[dict]:
    """Restituisce gli LP creati su ARCA (l'app filtra poi, a livello
    locale, quali sono gia' stati presi in carico - vedi main.py).

    Filtra per data recente per non ripescare anni di storico ad ogni
    polling. Numero di giorni configurabile via .env (STORICO_LP_GIORNI,
    default 3).
    """
    giorni = int(os.getenv("STORICO_LP_GIORNI", "3"))
    placeholders = ",".join("?" for _ in CODICI_LISTA_PRELIEVO)
    query = f"""
        SELECT
            do.Id_DOTes AS lp_id,
            LTRIM(RTRIM(do.NumeroDoc)) AS numero,
            do.DataDoc AS data_creazione,
            do.Cd_CF AS cliente_destinazione,
            cf.Descrizione AS cliente_nome
        FROM DOTes do
        LEFT JOIN CF cf ON cf.Cd_CF = do.Cd_CF
        WHERE do.Cd_DO IN ({placeholders})
          AND do.DataDoc >= DATEADD(day, -?, CAST(GETDATE() AS date))
        ORDER BY do.DataDoc DESC, do.Id_DOTes DESC
    """
    with arca_connection() as conn:
        cur = conn.cursor()
        cur.execute(query, CODICI_LISTA_PRELIEVO + [giorni])
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_testata_lp(lp_id: str) -> dict | None:
    """Restituisce i dati anagrafici di una LP a partire dal suo ID ARCA."""
    query = """
        SELECT
            do.Id_DOTes AS lp_id,
            LTRIM(RTRIM(do.NumeroDoc)) AS numero,
            do.DataDoc AS data_creazione,
            do.Cd_CF AS cliente_destinazione,
            cf.Descrizione AS cliente_nome
        FROM DOTes do
        LEFT JOIN CF cf ON cf.Cd_CF = do.Cd_CF
        WHERE do.Id_DOTes = ?
    """
    with arca_connection() as conn:
        cur = conn.cursor()
        cur.execute(query, lp_id)
        row = cur.fetchone()
        if not row:
            return None
        cols = [c[0] for c in cur.description]
        return dict(zip(cols, row))


def get_righe_lp(lp_id: str) -> list[dict]:
    """Righe (articoli/quantita') di un LP, identificato da Id_DOTes.

    Esclude le righe "di nota" (es. riferimenti a ordini, del tipo
    "VS.ORD. ... del ...") che hanno Cd_AR nullo: non sono articoli
    veri, servono solo come testo di riferimento dentro il documento.
    """
    query = """
        SELECT
            Id_DORig AS riga_id_arca,
            Cd_AR AS articolo_codice,
            Descrizione AS articolo_descrizione,
            Qta AS quantita,
            NoteRiga AS nota_riga
        FROM DORig
        WHERE Id_DOTes = ?
          AND Cd_AR IS NOT NULL
        ORDER BY Id_DORig
    """
    with arca_connection() as conn:
        cur = conn.cursor()
        cur.execute(query, lp_id)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_nota_lp(lp_id: str) -> str | None:
    """Nota generale dell'LP scritta in ARCA (scheda Info -> Note
    principali, salvata nel campo NotePiede della testata documento).
    Sola lettura: l'app non scrive mai qui direttamente, se non in
    append quando il magazziniere conferma (vedi scrivi_esito_finale_lp)."""
    query = "SELECT NotePiede FROM DOTes WHERE Id_DOTes = ?"
    with arca_connection() as conn:
        cur = conn.cursor()
        cur.execute(query, lp_id)
        row = cur.fetchone()
        return row[0] if row and row[0] else None


def scrivi_esito_finale_lp(
    lp_id: str, righe_confermate: list[dict], nota_magazziniere: str | None = None
) -> None:
    """Scrittura FINALE su ARCA quando il magazziniere preme 'Invia'.

    righe_confermate: lista di dict con riga_id_arca, quantita_corrente, eliminata
    nota_magazziniere: testo libero scritto dal magazziniere (opzionale).
        Viene appeso al campo NotePiede esistente, cosi' l'ufficio lo
        vede dentro ARCA nella stessa nota, senza cancellare quella
        gia' presente.

    Logica confermata confrontando coppie storiche LP -> Bolla reali
    (vedi trova_coppie_lp_bolla.py): quando l'ufficio genera la bolla,
    ARCA usa il campo QtaEvadibile (non solo Qta) per decidere quanto
    trasferire. Per questo aggiorniamo ENTRAMBI i campi con la quantita'
    confermata dal magazziniere.

    Le righe cancellate dal magazziniere NON vengono eliminate fisicamente
    (rischierebbe di rompere riferimenti come Id_DORig_Evade), ma azzerate
    (Qta=0, QtaEvadibile=0): cosi' la riga resta ma non genera nulla in
    fase di creazione bolla, come se non ci fosse.
    """
    with arca_connection() as conn:
        cur = conn.cursor()
        try:
            for riga in righe_confermate:
                if riga["eliminata"]:
                    cur.execute(
                        "UPDATE DORig SET Qta = 0, QtaEvadibile = 0 WHERE Id_DORig = ?",
                        riga["riga_id_arca"],
                    )
                else:
                    cur.execute(
                        "UPDATE DORig SET Qta = ?, QtaEvadibile = ?, NoteRiga = ? WHERE Id_DORig = ?",
                        riga["quantita_corrente"],
                        riga["quantita_corrente"],
                        riga.get("nota_riga") or "",
                        riga["riga_id_arca"],
                    )

            if nota_magazziniere:
                cur.execute(
                    """
                    UPDATE DOTes
                    SET NotePiede = ISNULL(NotePiede, '') + CHAR(13) + CHAR(10)
                        + '[Magazzino] ' + ?
                    WHERE Id_DOTes = ?
                    """,
                    nota_magazziniere,
                    lp_id,
                )

            conn.commit()
        except Exception:
            conn.rollback()
            raise
