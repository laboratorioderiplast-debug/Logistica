import asyncio
import json
import os
import re
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import arca_repository
from database import app_connection, init_app_db
from models import (
    AssegnaTabletRequest,
    AssegnaCamionRequest,
    CaricataRequest,
    ConfermaLPResponse,
    LPHeaderOut,
    LPRigaOut,
    ModificaTabletRequest,
    ModificaRigaRequest,
    NotaRequest,
    RegistraTabletRequest,
    TabletInfo,
    TabletPredefinitoRequest,
)
from ws_manager import manager

load_dotenv()

APP_SHARED_TOKEN = os.getenv("APP_SHARED_TOKEN", "cambia_questo_token")
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "10"))

app = FastAPI(title="LP Tablet App")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restringere ai domini/IP Tailscale reali in produzione
    allow_methods=["*"],
    allow_headers=["*"],
)


def check_token(x_app_token: str | None = Header(default=None)):
    if x_app_token != APP_SHARED_TOKEN:
        raise HTTPException(status_code=401, detail="Token non valido")


def _valida_settimana(settimana: str):
    if not re.fullmatch(r"\d{4}-W\d{2}", settimana):
        raise HTTPException(status_code=400, detail="Settimana non valida")
    try:
        datetime.strptime(settimana + "-1", "%G-W%V-%u")
    except ValueError:
        raise HTTPException(status_code=400, detail="Settimana non valida")


@app.get("/api/pianificazione-carichi")
def leggi_pianificazione_carichi(settimana: str):
    _valida_settimana(settimana)
    with app_connection() as conn:
        righe = conn.execute(
            "SELECT id, settimana, giorno, dati, aggiornato_il FROM pianificazione_carichi WHERE settimana = ? ORDER BY CASE giorno WHEN 'lunedi' THEN 1 WHEN 'martedi' THEN 2 WHEN 'mercoledi' THEN 3 WHEN 'giovedi' THEN 4 WHEN 'venerdi' THEN 5 ELSE 6 END, id",
            (settimana,),
        ).fetchall()
    return [{"id": r["id"], "settimana": r["settimana"], "giorno": r["giorno"], **json.loads(r["dati"]), "aggiornato_il": r["aggiornato_il"]} for r in righe]


@app.post("/api/pianificazione-carichi")
def crea_carico_pianificato(req: dict):
    settimana = str(req.get("settimana", ""))
    giorno = str(req.get("giorno", ""))
    _valida_settimana(settimana)
    if giorno not in {"lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato"}:
        raise HTTPException(status_code=400, detail="Giorno non valido")
    dati = req.get("dati") or {}
    if not isinstance(dati, dict):
        raise HTTPException(status_code=400, detail="Dati del carico non validi")
    carico_id = str(uuid.uuid4())
    with app_connection() as conn:
        conn.execute("INSERT INTO pianificazione_carichi (id, settimana, giorno, dati) VALUES (?, ?, ?, ?)", (carico_id, settimana, giorno, json.dumps(dati, ensure_ascii=False)))
    return {"ok": True, "id": carico_id}


@app.put("/api/pianificazione-carichi/{carico_id}")
def aggiorna_carico_pianificato(carico_id: str, req: dict):
    settimana = str(req.get("settimana", ""))
    giorno = str(req.get("giorno", ""))
    _valida_settimana(settimana)
    if giorno not in {"lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato"}:
        raise HTTPException(status_code=400, detail="Giorno non valido")
    dati = req.get("dati") or {}
    if not isinstance(dati, dict):
        raise HTTPException(status_code=400, detail="Dati del carico non validi")
    with app_connection() as conn:
        cur = conn.execute("UPDATE pianificazione_carichi SET settimana=?, giorno=?, dati=?, aggiornato_il=CURRENT_TIMESTAMP WHERE id=?", (settimana, giorno, json.dumps(dati, ensure_ascii=False), carico_id))
        if not cur.rowcount:
            raise HTTPException(status_code=404, detail="Carico non trovato")
    return {"ok": True}


@app.delete("/api/pianificazione-carichi/{carico_id}")
def elimina_carico_pianificato(carico_id: str):
    with app_connection() as conn:
        cur = conn.execute("DELETE FROM pianificazione_carichi WHERE id=?", (carico_id,))
        if not cur.rowcount:
            raise HTTPException(status_code=404, detail="Carico non trovato")
    return {"ok": True}


def _tablet_predefinito_id() -> str | None:
    with app_connection() as conn:
        riga = conn.execute("SELECT valore FROM app_settings WHERE chiave = 'tablet_predefinito_id'").fetchone()
    return riga["valore"] if riga and riga["valore"] else None


# ---------------------------------------------------------------------
# Avvio: inizializza DB locale e lancia il polling in background
# ---------------------------------------------------------------------

@app.on_event("startup")
async def startup():
    init_app_db()
    asyncio.create_task(_poll_nuovi_lp_loop())


async def _poll_nuovi_lp_loop():
    """Ogni N secondi controlla se ci sono nuovi LP su ARCA non ancora
    conosciuti dall'app e, se si', li registra localmente e avvisa
    l'ufficio via WebSocket."""
    while True:
        try:
            _controlla_nuovi_lp()
        except Exception as e:
            # Non blocca il loop: logga e riprova al giro successivo
            print(f"[poll] errore lettura ARCA: {e}")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def _controlla_nuovi_lp():
    lp_arca = arca_repository.get_nuovi_lp()
    with app_connection() as conn:
        esistenti = {
            row["lp_id"] for row in conn.execute("SELECT lp_id FROM lp_assegnazioni")
        }
        nuovi = [lp for lp in lp_arca if str(lp["lp_id"]) not in esistenti]
        for lp in nuovi:
            lp_id = str(lp["lp_id"])
            nota_arca = arca_repository.get_nota_lp(lp_id)
            conn.execute(
                "INSERT INTO lp_assegnazioni (lp_id, stato, nota_arca) VALUES (?, 'nuovo', ?)",
                (lp_id, nota_arca),
            )

    if nuovi:
        asyncio.create_task(
            manager.send_to_channel("office", {"tipo": "nuovi_lp", "lp": nuovi})
        )


# ---------------------------------------------------------------------
# Rotte: Tablet (registrazione / elenco per l'ufficio)
# ---------------------------------------------------------------------

@app.post("/api/tablets", dependencies=[])
def registra_tablet(req: RegistraTabletRequest):
    with app_connection() as conn:
        conn.execute(
            """
            INSERT INTO tablets (id, nome, ultimo_visto) VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET nome=excluded.nome, ultimo_visto=excluded.ultimo_visto
            """,
            (req.id, req.nome, datetime.now(timezone.utc).isoformat()),
        )
    return {"ok": True}


@app.get("/api/tablets/{tablet_id}", response_model=TabletInfo)
def dettagli_tablet(tablet_id: str):
    with app_connection() as conn:
        riga = conn.execute("SELECT id, nome FROM tablets WHERE id = ?", (tablet_id,)).fetchone()
    if not riga:
        raise HTTPException(status_code=404, detail="Tablet non trovato")
    return TabletInfo(id=riga["id"], nome=riga["nome"], online=manager.is_online(f"tablet:{riga['id']}"))


@app.put("/api/tablets/{tablet_id}")
async def modifica_tablet(tablet_id: str, req: ModificaTabletRequest):
    nuovo_id = req.id.strip()
    nuovo_nome = req.nome.strip()
    if not nuovo_id or not nuovo_nome:
        raise HTTPException(status_code=400, detail="Inserisci nome e ID del tablet")
    with app_connection() as conn:
        esistente = conn.execute("SELECT 1 FROM tablets WHERE id = ?", (tablet_id,)).fetchone()
        if not esistente:
            raise HTTPException(status_code=404, detail="Tablet non trovato")
        conflitto = conn.execute("SELECT 1 FROM tablets WHERE id = ?", (nuovo_id,)).fetchone()
        if conflitto and nuovo_id != tablet_id:
            raise HTTPException(status_code=409, detail="Questo ID è già usato da un altro tablet")
        conn.execute("UPDATE tablets SET id = ?, nome = ? WHERE id = ?", (nuovo_id, nuovo_nome, tablet_id))
        if nuovo_id != tablet_id:
            conn.execute("UPDATE lp_assegnazioni SET tablet_id = ? WHERE tablet_id = ?", (nuovo_id, tablet_id))
            conn.execute("UPDATE camion SET tablet_id = ? WHERE tablet_id = ?", (nuovo_id, tablet_id))
            conn.execute(
                "UPDATE app_settings SET valore = ? WHERE chiave = 'tablet_predefinito_id' AND valore = ?",
                (nuovo_id, tablet_id),
            )
    await manager.send_to_channel(f"tablet:{nuovo_id}", {"tipo": "tablet_aggiornato", "nome": nuovo_nome})
    return {"ok": True, "id": nuovo_id, "nome": nuovo_nome}


@app.get("/api/tablets/{tablet_id}/assegnato", response_model=LPHeaderOut | None)
def lp_assegnato_a_tablet(tablet_id: str):
    """Restituisce l'LP attualmente assegnato a questo tablet (se c'e'),
    cosi' il tablet puo' recuperarlo da solo dopo un refresh della
    pagina, invece di perderlo in attesa di un nuovo invio."""
    with app_connection() as conn:
        riga = conn.execute(
            "SELECT lp_id FROM lp_assegnazioni WHERE tablet_id = ? AND stato = 'inviato_tablet' ORDER BY aggiornato_il DESC LIMIT 1",
            (tablet_id,),
        ).fetchone()
    if not riga:
        return None
    return _leggi_lp_completo(riga["lp_id"])


@app.get("/api/tablets/{tablet_id}/assegnati", response_model=list[LPHeaderOut])
def lp_assegnati_a_tablet(tablet_id: str):
    """Restituisce tutte le LP ancora assegnate al tablet."""
    with app_connection() as conn:
        righe = conn.execute(
            """SELECT lp_id FROM lp_assegnazioni
               WHERE tablet_id = ? AND stato IN ('inviato_tablet', 'in_attesa_approvazione')
               ORDER BY aggiornato_il DESC""",
            (tablet_id,),
        ).fetchall()
    return [_leggi_lp_completo(riga["lp_id"]) for riga in righe]


@app.get("/api/tablets/{tablet_id}/camion")
def camion_assegnati_a_tablet(tablet_id: str):
    """Il tablet predefinito vede tutti i camion; gli altri solo i propri."""
    default_id = _tablet_predefinito_id()
    vede_tutti = bool(default_id and tablet_id == default_id)
    with app_connection() as conn:
        camion = conn.execute(
            """SELECT c.id, c.nome, c.tablet_id, t.nome AS tablet_nome
               FROM camion c LEFT JOIN tablets t ON t.id = c.tablet_id
               WHERE (? = 1 OR c.tablet_id = ?)
               ORDER BY c.creato_il DESC""",
            (1 if vede_tutti else 0, tablet_id),
        ).fetchall()
        gruppi = []
        for c in camion:
            lp_ids = conn.execute(
                """SELECT lp_id FROM lp_assegnazioni
                   WHERE camion_id = ? AND tablet_id = ?
                     AND stato IN ('inviato_tablet', 'in_attesa_approvazione')
                   ORDER BY aggiornato_il DESC""",
                (c["id"], c["tablet_id"]),
            ).fetchall()
            if lp_ids:
                gruppi.append({
                    "id": c["id"], "nome": c["nome"], "lp_ids": [r["lp_id"] for r in lp_ids],
                    "tablet_id": c["tablet_id"], "tablet_nome": c["tablet_nome"],
                })
        senza_camion = conn.execute(
            """SELECT a.lp_id, t.nome AS tablet_nome FROM lp_assegnazioni a
               LEFT JOIN tablets t ON t.id = a.tablet_id
               WHERE a.tablet_id = ? AND a.camion_id IS NULL
                 AND a.stato IN ('inviato_tablet', 'in_attesa_approvazione')
               ORDER BY a.aggiornato_il DESC""",
            (tablet_id,),
        ).fetchall()

    if senza_camion:
        gruppi.append({
            "id": "senza-camion", "nome": "LP senza camion", "lp_ids": [r["lp_id"] for r in senza_camion],
            "tablet_id": tablet_id, "tablet_nome": senza_camion[0]["tablet_nome"],
        })
    return [
        {
            **gruppo,
            "tablet_predefinito": vede_tutti,
            "lp": [_leggi_lp_completo(lp_id).model_dump() for lp_id in gruppo["lp_ids"]],
        }
        for gruppo in gruppi
    ]


@app.get("/api/tablets", response_model=list[TabletInfo])
def elenco_tablet():
    with app_connection() as conn:
        righe = conn.execute("SELECT id, nome FROM tablets").fetchall()
    return [
        TabletInfo(id=r["id"], nome=r["nome"], online=manager.is_online(f"tablet:{r['id']}"))
        for r in righe
    ]


@app.get("/api/impostazioni")
def leggi_impostazioni():
    tablet_id = _tablet_predefinito_id()
    with app_connection() as conn:
        tablet = conn.execute("SELECT id, nome FROM tablets WHERE id = ?", (tablet_id,)).fetchone() if tablet_id else None
    return {"tablet_predefinito_id": tablet["id"] if tablet else None, "tablet_predefinito_nome": tablet["nome"] if tablet else None}


@app.put("/api/impostazioni/tablet-predefinito")
async def imposta_tablet_predefinito(req: TabletPredefinitoRequest):
    tablet_id = (req.tablet_id or "").strip() or None
    with app_connection() as conn:
        if tablet_id and not conn.execute("SELECT 1 FROM tablets WHERE id = ?", (tablet_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Tablet selezionato non trovato")
        conn.execute(
            "INSERT INTO app_settings (chiave, valore) VALUES ('tablet_predefinito_id', ?) "
            "ON CONFLICT(chiave) DO UPDATE SET valore=excluded.valore",
            (tablet_id,),
        )
        tablet_rows = conn.execute("SELECT id FROM tablets").fetchall()
    for row in tablet_rows:
        await manager.send_to_channel(f"tablet:{row['id']}", {"tipo": "impostazioni_aggiornate"})
    return {"ok": True, "tablet_predefinito_id": tablet_id}


@app.get("/api/ufficio/camion")
def camion_per_ufficio():
    """Riepilogo in sola lettura dei camion e del tablet che li ha in carico."""
    with app_connection() as conn:
        camion = conn.execute(
            """SELECT c.id, c.nome, c.tablet_id, t.nome AS tablet_nome
               FROM camion c LEFT JOIN tablets t ON t.id = c.tablet_id
               ORDER BY c.creato_il DESC"""
        ).fetchall()
        gruppi = []
        for c in camion:
            ids = conn.execute(
                """SELECT lp_id FROM lp_assegnazioni WHERE camion_id = ? AND tablet_id = ?
                   AND stato IN ('inviato_tablet', 'in_attesa_approvazione') ORDER BY aggiornato_il DESC""",
                (c["id"], c["tablet_id"]),
            ).fetchall()
            if ids:
                gruppi.append({"id": c["id"], "nome": c["nome"], "tablet_id": c["tablet_id"], "tablet_nome": c["tablet_nome"], "lp_ids": [r["lp_id"] for r in ids]})
        legacy = conn.execute(
            """SELECT a.tablet_id, t.nome AS tablet_nome, a.lp_id FROM lp_assegnazioni a
               LEFT JOIN tablets t ON t.id = a.tablet_id
               WHERE a.camion_id IS NULL AND a.tablet_id IS NOT NULL
                 AND a.stato IN ('inviato_tablet', 'in_attesa_approvazione')
               ORDER BY a.aggiornato_il DESC"""
        ).fetchall()
        legacy_by_tablet = {}
        for row in legacy:
            legacy_by_tablet.setdefault(row["tablet_id"], {"id": f"legacy-{row['tablet_id']}", "nome": "LP senza camion", "tablet_id": row["tablet_id"], "tablet_nome": row["tablet_nome"], "lp_ids": []})["lp_ids"].append(row["lp_id"])
        gruppi.extend(legacy_by_tablet.values())
    return [
        {**gruppo, "lp": [_leggi_lp_completo(lp_id).model_dump() for lp_id in gruppo["lp_ids"]]}
        for gruppo in gruppi
    ]


# ---------------------------------------------------------------------
# Rotte: LP lato ufficio
# ---------------------------------------------------------------------

@app.get("/api/lp/nuovi", response_model=list[LPHeaderOut])
def lp_nuovi():
    """Restituisce le LP recenti (stessa finestra di giorni usata per il
    polling), arricchite con i dati reali letti da ARCA (numero, data,
    cliente) - non solo quelle ancora 'nuove', cosi' l'ufficio continua
    a vederle anche dopo l'invio al tablet o la conferma, anche dopo un
    riavvio del backend o un refresh della pagina."""
    with app_connection() as conn:
        locali = {
            r["lp_id"]: {"stato": r["stato"], "tablet_id": r["tablet_id"], "camion_id": r["camion_id"], "camion_nome": r["camion_nome"]}
            for r in conn.execute(
                """SELECT a.lp_id, a.stato, a.tablet_id, a.camion_id, c.nome AS camion_nome
                   FROM lp_assegnazioni a LEFT JOIN camion c ON c.id = a.camion_id"""
            )
        }

    lp_da_arca = arca_repository.get_nuovi_lp()

    risultato = []
    for lp in lp_da_arca:
        lp_id = str(lp["lp_id"])
        info_locale = locali.get(lp_id, {"stato": "nuovo", "tablet_id": None, "camion_id": None, "camion_nome": None})
        risultato.append(
            LPHeaderOut(
                lp_id=lp_id,
                stato=info_locale["stato"],
                tablet_id=info_locale["tablet_id"],
                numero=str(lp.get("numero") or ""),
                data_creazione=str(lp.get("data_creazione") or ""),
                cliente_destinazione=str(lp.get("cliente_destinazione") or ""),
                cliente_nome=str(lp.get("cliente_nome") or ""),
                camion_id=info_locale["camion_id"],
                camion_nome=info_locale["camion_nome"],
            )
        )
    return risultato


@app.post("/api/lp/{lp_id}/assegna")
async def assegna_lp(lp_id: str, req: AssegnaTabletRequest):
    tablet_predefinito = _tablet_predefinito_id()
    if not tablet_predefinito or req.tablet_id != tablet_predefinito:
        raise HTTPException(status_code=409, detail="Le LP dell'ufficio si inviano solo al tablet predefinito")
    _assicura_righe_locali(lp_id)

    with app_connection() as conn:
        vecchia_riga = conn.execute(
            "SELECT tablet_id FROM lp_assegnazioni WHERE lp_id = ?", (lp_id,)
        ).fetchone()
        vecchio_tablet_id = vecchia_riga["tablet_id"] if vecchia_riga else None

        conn.execute(
            "UPDATE lp_assegnazioni SET tablet_id = ?, camion_id = NULL, stato = 'inviato_tablet', aggiornato_il = CURRENT_TIMESTAMP WHERE lp_id = ?",
            (req.tablet_id, lp_id),
        )

    lp_out = _leggi_lp_completo(lp_id)
    await manager.send_to_channel(f"tablet:{req.tablet_id}", {"tipo": "lp_assegnato", "lp": lp_out.model_dump()})

    # Se l'LP era gia' su un altro tablet (inoltro), avvisa quello vecchio
    # che l'LP non e' piu' suo, cosi' la sua schermata si libera.
    if vecchio_tablet_id and vecchio_tablet_id != req.tablet_id:
        await manager.send_to_channel(f"tablet:{vecchio_tablet_id}", {"tipo": "lp_rimosso", "lp_id": lp_id})

    return {"ok": True}


@app.post("/api/camion/assegna")
async def assegna_camion(req: AssegnaCamionRequest):
    nome = req.nome.strip()
    lp_ids = list(dict.fromkeys(str(lp_id) for lp_id in req.lp_ids if str(lp_id).strip()))
    if not nome:
        raise HTTPException(status_code=400, detail="Inserisci il nome del camion")
    if not lp_ids:
        raise HTTPException(status_code=400, detail="Seleziona almeno una LP")
    tablet_predefinito = _tablet_predefinito_id()
    if not tablet_predefinito:
        raise HTTPException(status_code=409, detail="Definisci prima il tablet predefinito nelle impostazioni ufficio")
    if req.tablet_id != tablet_predefinito:
        raise HTTPException(status_code=409, detail="I nuovi camion devono essere inviati al tablet predefinito")

    for lp_id in lp_ids:
        _assicura_righe_locali(lp_id)

    camion_id = str(uuid.uuid4())
    with app_connection() as conn:
        placeholders = ",".join("?" for _ in lp_ids)
        righe = conn.execute(
            f"SELECT lp_id, tablet_id, stato FROM lp_assegnazioni WHERE lp_id IN ({placeholders})",
            lp_ids,
        ).fetchall()
        if len(righe) != len(lp_ids):
            raise HTTPException(status_code=404, detail="Una o più LP non sono state trovate")
        if any(r["stato"] != "nuovo" for r in righe):
            raise HTTPException(status_code=409, detail="Puoi inserire nel camion solo LP non ancora assegnate")
        vecchi_tablet = {r["tablet_id"] for r in righe if r["tablet_id"] and r["tablet_id"] != req.tablet_id}
        conn.execute("INSERT INTO camion (id, nome, tablet_id) VALUES (?, ?, ?)", (camion_id, nome, req.tablet_id))
        conn.execute(
            f"""UPDATE lp_assegnazioni
                SET tablet_id = ?, camion_id = ?, stato = 'inviato_tablet', aggiornato_il = CURRENT_TIMESTAMP
                WHERE lp_id IN ({placeholders})""",
            [req.tablet_id, camion_id, *lp_ids],
        )

    lp = [_leggi_lp_completo(lp_id).model_dump() for lp_id in lp_ids]
    payload = {"id": camion_id, "nome": nome, "lp": lp}
    await manager.send_to_channel(f"tablet:{req.tablet_id}", {"tipo": "camion_assegnato", "camion": payload})
    await manager.send_to_channel(
        "office",
        {"tipo": "camion_inviato", "camion": {"id": camion_id, "nome": nome, "tablet_id": req.tablet_id, "lp_ids": lp_ids}},
    )
    for vecchio_tablet in vecchi_tablet:
        for lp_id in lp_ids:
            if any(r["lp_id"] == lp_id and r["tablet_id"] == vecchio_tablet for r in righe):
                await manager.send_to_channel(f"tablet:{vecchio_tablet}", {"tipo": "lp_rimosso", "lp_id": lp_id})
    return {"ok": True, "camion": payload}


@app.post("/api/tablets/{tablet_id}/camion/{camion_id}/conferma")
async def conferma_camion(tablet_id: str, camion_id: str):
    """Invia in approvazione tutte le LP non ancora inviate del camion."""
    with app_connection() as conn:
        if camion_id == "senza-camion":
            righe = conn.execute(
                """SELECT lp_id FROM lp_assegnazioni
                   WHERE tablet_id = ? AND camion_id IS NULL AND stato = 'inviato_tablet'
                   ORDER BY aggiornato_il DESC""",
                (tablet_id,),
            ).fetchall()
            if not righe:
                raise HTTPException(status_code=409, detail="Non ci sono LP da inviare all'ufficio")
            for riga in righe:
                stato_carico = conn.execute(
                    """SELECT COUNT(*) AS totale,
                              SUM(CASE WHEN caricata = 0 THEN 1 ELSE 0 END) AS mancanti
                       FROM lp_righe_stato WHERE lp_id = ? AND eliminata = 0""",
                    (riga["lp_id"],),
                ).fetchone()
                if not stato_carico["totale"] or stato_carico["mancanti"]:
                    raise HTTPException(status_code=409, detail="Completa il caricamento di tutte le righe prima di inviare il camion")
            conn.execute(
                """UPDATE lp_assegnazioni SET stato = 'in_attesa_approvazione', aggiornato_il = CURRENT_TIMESTAMP
                   WHERE tablet_id = ? AND camion_id IS NULL AND stato = 'inviato_tablet'""",
                (tablet_id,),
            )
        else:
            esiste = conn.execute(
                "SELECT 1 FROM camion WHERE id = ? AND tablet_id = ?", (camion_id, tablet_id)
            ).fetchone()
            if not esiste:
                raise HTTPException(status_code=404, detail="Camion non trovato")
            righe = conn.execute(
                """SELECT lp_id FROM lp_assegnazioni
                   WHERE tablet_id = ? AND camion_id = ? AND stato = 'inviato_tablet'
                   ORDER BY aggiornato_il DESC""",
                (tablet_id, camion_id),
            ).fetchall()
            if not righe:
                raise HTTPException(status_code=409, detail="Non ci sono LP da inviare all'ufficio")
            for riga in righe:
                stato_carico = conn.execute(
                    """SELECT COUNT(*) AS totale,
                              SUM(CASE WHEN caricata = 0 THEN 1 ELSE 0 END) AS mancanti
                       FROM lp_righe_stato WHERE lp_id = ? AND eliminata = 0""",
                    (riga["lp_id"],),
                ).fetchone()
                if not stato_carico["totale"] or stato_carico["mancanti"]:
                    raise HTTPException(status_code=409, detail="Completa il caricamento di tutte le righe prima di inviare il camion")
            conn.execute(
                """UPDATE lp_assegnazioni SET stato = 'in_attesa_approvazione', aggiornato_il = CURRENT_TIMESTAMP
                   WHERE tablet_id = ? AND camion_id = ? AND stato = 'inviato_tablet'""",
                (tablet_id, camion_id),
            )

        if camion_id == "senza-camion":
            lp_camion_attive = conn.execute(
                """SELECT lp_id FROM lp_assegnazioni
                   WHERE tablet_id = ? AND camion_id IS NULL
                     AND stato IN ('inviato_tablet', 'in_attesa_approvazione')""",
                (tablet_id,),
            ).fetchall()
        else:
            lp_camion_attive = conn.execute(
                """SELECT lp_id FROM lp_assegnazioni
                   WHERE tablet_id = ? AND camion_id = ?
                     AND stato IN ('inviato_tablet', 'in_attesa_approvazione')""",
                (tablet_id, camion_id),
            ).fetchall()
        for riga in lp_camion_attive:
            stato_carico = conn.execute(
                """SELECT COUNT(*) AS totale,
                          SUM(CASE WHEN caricata = 0 THEN 1 ELSE 0 END) AS mancanti
                   FROM lp_righe_stato WHERE lp_id = ? AND eliminata = 0""",
                (riga["lp_id"],),
            ).fetchone()
            if not stato_carico["totale"] or stato_carico["mancanti"]:
                raise HTTPException(status_code=409, detail="Completa il caricamento di tutte le righe prima di inviare il camion")

    lp_ids = [r["lp_id"] for r in righe]
    for lp_id in lp_ids:
        lp = _leggi_lp_completo(lp_id)
        await manager.send_to_channel("office", {"tipo": "richiesta_approvazione", "lp": lp.model_dump()})
    return {"ok": True, "lp_inviate": len(lp_ids), "lp_ids": lp_ids}


@app.post("/api/tablets/{tablet_id}/camion/{camion_id}/inoltra")
async def inoltra_camion(tablet_id: str, camion_id: str, req: AssegnaTabletRequest):
    """Sposta tutto il camion attivo su un altro tablet, mantenendo la cartella."""
    if camion_id == "senza-camion":
        raise HTTPException(status_code=400, detail="Le LP senza camion non possono essere inoltrate come gruppo")
    if req.tablet_id == tablet_id:
        raise HTTPException(status_code=400, detail="Scegli un tablet diverso da quello corrente")

    tablet_predefinito = _tablet_predefinito_id()
    if not tablet_predefinito:
        raise HTTPException(status_code=409, detail="Il tablet predefinito non è configurato")
    if tablet_id != tablet_predefinito and req.tablet_id != tablet_predefinito:
        raise HTTPException(status_code=403, detail="Un camion può essere restituito solo al tablet predefinito")
    with app_connection() as conn:
        camion = conn.execute(
            "SELECT id, nome, tablet_id FROM camion WHERE id = ? AND (? = 1 OR tablet_id = ?)",
            (camion_id, 1 if tablet_id == tablet_predefinito else 0, tablet_id),
        ).fetchone()
        if not camion:
            raise HTTPException(status_code=404, detail="Camion non trovato su questo tablet")
        tablet_destinazione = conn.execute("SELECT 1 FROM tablets WHERE id = ?", (req.tablet_id,)).fetchone()
        if not tablet_destinazione:
            raise HTTPException(status_code=404, detail="Tablet di destinazione non trovato")
        tablet_attuale = camion["tablet_id"]
        if req.tablet_id == tablet_attuale:
            raise HTTPException(status_code=400, detail="Il camion è già assegnato a questo tablet")
        righe = conn.execute(
            """SELECT lp_id FROM lp_assegnazioni
               WHERE camion_id = ? AND tablet_id = ?
                 AND stato IN ('inviato_tablet', 'in_attesa_approvazione')
               ORDER BY aggiornato_il DESC""",
            (camion_id, tablet_attuale),
        ).fetchall()
        lp_ids = [r["lp_id"] for r in righe]
        if not lp_ids:
            raise HTTPException(status_code=409, detail="Il camion non contiene LP attive da inoltrare")
        conn.execute("UPDATE camion SET tablet_id = ? WHERE id = ?", (req.tablet_id, camion_id))
        conn.execute(
            """UPDATE lp_assegnazioni
               SET tablet_id = ?, stato = 'inviato_tablet', aggiornato_il = CURRENT_TIMESTAMP
               WHERE camion_id = ? AND tablet_id = ?
                 AND stato IN ('inviato_tablet', 'in_attesa_approvazione')""",
            (req.tablet_id, camion_id, tablet_attuale),
        )

    lp = [_leggi_lp_completo(lp_id).model_dump() for lp_id in lp_ids]
    payload = {"id": camion_id, "nome": camion["nome"], "lp": lp}
    await manager.send_to_channel(f"tablet:{tablet_attuale}", {"tipo": "camion_rimosso", "camion_id": camion_id})
    await manager.send_to_channel(f"tablet:{req.tablet_id}", {"tipo": "camion_assegnato", "camion": payload})
    await manager.send_to_channel(
        "office",
        {"tipo": "camion_inviato", "camion": {"id": camion_id, "nome": camion["nome"], "tablet_id": req.tablet_id, "lp_ids": lp_ids}},
    )
    return {"ok": True, "camion": payload}


def _assicura_righe_locali(lp_id: str):
    """Se le righe di questo LP non sono ancora state importate nel
    database locale (perche' non e' mai stato aperto/assegnato prima),
    le importa ora da ARCA. Cosi' l'ufficio puo' vedere/modificare gli
    articoli anche prima di assegnare l'LP a un tablet."""
    with app_connection() as conn:
        esiste_testata = conn.execute(
            "SELECT 1 FROM lp_assegnazioni WHERE lp_id = ?", (lp_id,)
        ).fetchone()
        if not esiste_testata:
            nota_arca = arca_repository.get_nota_lp(lp_id)
            conn.execute(
                "INSERT INTO lp_assegnazioni (lp_id, stato, nota_arca) VALUES (?, 'nuovo', ?)",
                (lp_id, nota_arca),
            )

        esistono_righe = conn.execute(
            "SELECT 1 FROM lp_righe_stato WHERE lp_id = ?", (lp_id,)
        ).fetchone()
        if not esistono_righe:
            righe_arca = arca_repository.get_righe_lp(lp_id)
            for r in righe_arca:
                conn.execute(
                    """
                    INSERT INTO lp_righe_stato
                        (lp_id, riga_id_arca, articolo_codice, articolo_descrizione,
                         quantita_originale, quantita_corrente, eliminata, nota_riga, caricata)
                    VALUES (?, ?, ?, ?, ?, ?, 0, ?, 0)
                    """,
                    (
                        lp_id,
                        str(r["riga_id_arca"]),
                        r["articolo_codice"],
                        r["articolo_descrizione"],
                        float(r["quantita"]),
                        float(r["quantita"]),
                        r.get("nota_riga") or "",
                    ),
                )


def _estrai_metri_per_collo(descrizione: str | None) -> float | None:
    """Cerca nella descrizione dell'articolo un pattern tipo 'R.50' o
    'M.100' (rotolo/matassa da N metri) per dedurre quanti metri
    compongono un collo. Restituisce None se non trovato: in quel caso
    la conversione in colli non e' possibile per quella riga."""
    if not descrizione:
        return None
    m = re.search(r"\b[RM]\.(\d+)\b", descrizione)
    return float(m.group(1)) if m else None


def _leggi_lp_completo(lp_id: str) -> LPHeaderOut:
    anagrafica = arca_repository.get_testata_lp(lp_id) or {}
    with app_connection() as conn:
        testata = conn.execute(
            "SELECT lp_id, stato, tablet_id, camion_id, nota_arca, nota_magazziniere FROM lp_assegnazioni WHERE lp_id = ?",
            (lp_id,),
        ).fetchone()
        if not testata:
            raise HTTPException(status_code=404, detail="LP non trovato")
        righe = conn.execute(
            "SELECT * FROM lp_righe_stato WHERE lp_id = ?", (lp_id,)
        ).fetchall()
        camion = (
            conn.execute("SELECT nome FROM camion WHERE id = ?", (testata["camion_id"],)).fetchone()
            if testata["camion_id"] else None
        )

    return LPHeaderOut(
        lp_id=testata["lp_id"],
        numero=str(anagrafica.get("numero") or ""),
        data_creazione=str(anagrafica.get("data_creazione") or ""),
        cliente_destinazione=str(anagrafica.get("cliente_destinazione") or ""),
        cliente_nome=str(anagrafica.get("cliente_nome") or ""),
        stato=testata["stato"],
        tablet_id=testata["tablet_id"],
        camion_id=testata["camion_id"],
        camion_nome=camion["nome"] if camion else None,
        nota_arca=testata["nota_arca"],
        nota_magazziniere=testata["nota_magazziniere"] or "",
        righe=[
            LPRigaOut(
                riga_id_arca=r["riga_id_arca"],
                articolo_codice=r["articolo_codice"],
                articolo_descrizione=r["articolo_descrizione"],
                quantita_originale=r["quantita_originale"],
                quantita_corrente=r["quantita_corrente"],
                eliminata=bool(r["eliminata"]),
                metri_per_collo=_estrai_metri_per_collo(r["articolo_descrizione"]),
                nota_riga=r["nota_riga"] or "",
                caricata=bool(r["caricata"]),
            )
            for r in righe
        ],
    )


# ---------------------------------------------------------------------
# Rotte: LP lato tablet (magazziniere)
# ---------------------------------------------------------------------

@app.get("/api/lp/{lp_id}", response_model=LPHeaderOut)
def dettaglio_lp(lp_id: str):
    _assicura_righe_locali(lp_id)
    return _leggi_lp_completo(lp_id)


@app.patch("/api/lp/{lp_id}/riga/{riga_id_arca}")
async def modifica_riga(lp_id: str, riga_id_arca: str, req: ModificaRigaRequest):
    with app_connection() as conn:
        conn.execute(
            "UPDATE lp_righe_stato SET quantita_corrente = ? WHERE lp_id = ? AND riga_id_arca = ?",
            (req.quantita, lp_id, riga_id_arca),
        )
    await _notifica_office_stato(lp_id)
    return {"ok": True}


@app.delete("/api/lp/{lp_id}/riga/{riga_id_arca}")
async def elimina_riga(lp_id: str, riga_id_arca: str):
    with app_connection() as conn:
        conn.execute(
            "UPDATE lp_righe_stato SET eliminata = 1 WHERE lp_id = ? AND riga_id_arca = ?",
            (lp_id, riga_id_arca),
        )
    await _notifica_office_stato(lp_id)
    return {"ok": True}


@app.patch("/api/lp/{lp_id}/riga/{riga_id_arca}/nota")
async def modifica_nota_riga(lp_id: str, riga_id_arca: str, req: NotaRequest):
    with app_connection() as conn:
        conn.execute(
            "UPDATE lp_righe_stato SET nota_riga = ? WHERE lp_id = ? AND riga_id_arca = ?",
            (req.testo, lp_id, riga_id_arca),
        )
    await _notifica_office_stato(lp_id)
    return {"ok": True}


@app.patch("/api/lp/{lp_id}/riga/{riga_id_arca}/caricata")
async def modifica_caricata_riga(lp_id: str, riga_id_arca: str, req: CaricataRequest):
    with app_connection() as conn:
        conn.execute(
            "UPDATE lp_righe_stato SET caricata = ? WHERE lp_id = ? AND riga_id_arca = ?",
            (1 if req.caricata else 0, lp_id, riga_id_arca),
        )
    await _notifica_office_stato(lp_id)
    return {"ok": True}


@app.patch("/api/lp/{lp_id}/nota")
async def modifica_nota(lp_id: str, req: NotaRequest):
    with app_connection() as conn:
        conn.execute(
            "UPDATE lp_assegnazioni SET nota_magazziniere = ? WHERE lp_id = ?",
            (req.testo, lp_id),
        )
    await _notifica_office_stato(lp_id)
    return {"ok": True}


async def _notifica_office_stato(lp_id: str):
    lp = _leggi_lp_completo(lp_id)
    await manager.send_to_channel("office", {"tipo": "lp_aggiornato", "lp": lp.model_dump()})


@app.post("/api/lp/{lp_id}/conferma", response_model=ConfermaLPResponse)
async def conferma_lp(lp_id: str):
    """Il magazziniere preme 'Invia': l'LP NON viene ancora scritto su
    ARCA, passa in stato 'in_attesa_approvazione' e l'ufficio riceve
    una richiesta di approvazione. La scrittura vera avviene solo in
    approva_lp()."""
    with app_connection() as conn:
        conn.execute(
            "UPDATE lp_assegnazioni SET stato = 'in_attesa_approvazione', aggiornato_il = CURRENT_TIMESTAMP WHERE lp_id = ?",
            (lp_id,),
        )

    lp = _leggi_lp_completo(lp_id)
    await manager.send_to_channel(
        "office", {"tipo": "richiesta_approvazione", "lp": lp.model_dump()}
    )
    return ConfermaLPResponse(lp_id=lp_id, esito="in_attesa_approvazione")


@app.post("/api/lp/{lp_id}/approva", response_model=ConfermaLPResponse)
async def approva_lp(lp_id: str):
    """L'ufficio approva: SOLO ORA viene scritto davvero su ARCA."""
    lp = _leggi_lp_completo(lp_id)

    righe_confermate = [
        {
            "riga_id_arca": r.riga_id_arca,
            "quantita_corrente": r.quantita_corrente,
            "eliminata": r.eliminata,
            "nota_riga": r.nota_riga,
        }
        for r in lp.righe
    ]

    try:
        arca_repository.scrivi_esito_finale_lp(lp_id, righe_confermate, lp.nota_magazziniere)
    except Exception as e:
        return ConfermaLPResponse(lp_id=lp_id, esito="errore", dettaglio=str(e))

    with app_connection() as conn:
        conn.execute(
            "UPDATE lp_assegnazioni SET stato = 'confermato', aggiornato_il = CURRENT_TIMESTAMP WHERE lp_id = ?",
            (lp_id,),
        )

    await manager.send_to_channel("office", {"tipo": "lp_confermato", "lp_id": lp_id})
    if lp.tablet_id:
        await manager.send_to_channel(f"tablet:{lp.tablet_id}", {"tipo": "lp_approvato", "lp_id": lp_id})
    return ConfermaLPResponse(lp_id=lp_id, esito="ok")


@app.post("/api/lp/{lp_id}/rifiuta", response_model=ConfermaLPResponse)
async def rifiuta_lp(lp_id: str, req: NotaRequest | None = None):
    """L'ufficio rifiuta: l'LP torna al magazziniere per altre
    modifiche, senza scrivere nulla su ARCA. Se fornito, il motivo del
    rifiuto viene mostrato al magazziniere sul tablet."""
    with app_connection() as conn:
        conn.execute(
            "UPDATE lp_assegnazioni SET stato = 'inviato_tablet', aggiornato_il = CURRENT_TIMESTAMP WHERE lp_id = ?",
            (lp_id,),
        )

    lp = _leggi_lp_completo(lp_id)
    if lp.tablet_id:
        await manager.send_to_channel(
            f"tablet:{lp.tablet_id}",
            {
                "tipo": "lp_rifiutato",
                "lp": lp.model_dump(),
                "motivo": (req.testo if req else "") or "",
            },
        )
    return ConfermaLPResponse(lp_id=lp_id, esito="rifiutato")


# ---------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------

@app.websocket("/ws/office")
async def ws_office(websocket: WebSocket):
    await manager.connect("office", websocket)
    try:
        while True:
            await websocket.receive_text()  # non usiamo messaggi in arrivo, solo keepalive
    except WebSocketDisconnect:
        manager.disconnect("office", websocket)


@app.websocket("/ws/tablet/{tablet_id}")
async def ws_tablet(websocket: WebSocket, tablet_id: str):
    channel = f"tablet:{tablet_id}"
    await manager.connect(channel, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(channel, websocket)


# Serve le pagine frontend statiche (office.html, tablet.html)
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")
