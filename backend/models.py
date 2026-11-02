from typing import Optional
from pydantic import BaseModel


class TabletInfo(BaseModel):
    id: str
    nome: str
    online: bool = False


class RegistraTabletRequest(BaseModel):
    id: str
    nome: str


class ModificaTabletRequest(BaseModel):
    id: str
    nome: str


class TabletPredefinitoRequest(BaseModel):
    tablet_id: Optional[str] = None


class LPRigaOut(BaseModel):
    riga_id_arca: str
    articolo_codice: str
    articolo_descrizione: str
    quantita_originale: float
    quantita_corrente: float
    eliminata: bool
    metri_per_collo: Optional[float] = None
    nota_riga: Optional[str] = ""
    caricata: bool = False


class LPHeaderOut(BaseModel):
    lp_id: str
    numero: Optional[str] = None
    data_creazione: Optional[str] = None
    cliente_destinazione: Optional[str] = None
    cliente_nome: Optional[str] = None
    stato: str
    tablet_id: Optional[str] = None
    camion_id: Optional[str] = None
    camion_nome: Optional[str] = None
    nota_arca: Optional[str] = None
    nota_magazziniere: Optional[str] = ""
    righe: list[LPRigaOut] = []


class AssegnaTabletRequest(BaseModel):
    tablet_id: str


class AssegnaCamionRequest(BaseModel):
    nome: str
    tablet_id: str
    lp_ids: list[str]


class ModificaRigaRequest(BaseModel):
    quantita: float


class NotaRequest(BaseModel):
    testo: str


class CaricataRequest(BaseModel):
    caricata: bool


class ConfermaLPResponse(BaseModel):
    lp_id: str
    esito: str
    dettaglio: Optional[str] = None
