"""
Lettura dei CoA (Certificate of Analysis) dei fornitori di materia
prima in PDF: estrae il testo (con OCR automatico se il PDF e' una
scansione senza testo selezionabile) e prova a individuare fornitore,
lotto, materiale e tutti i valori di prova (MFI, Carbon Black,
Umidita', Densita', Volatili, Dispersione, OIT).

Un singolo PDF puo' contenere PIU' di un lotto (es. un documento con
due certificati allegati): "estrai_candidati" ritorna quindi una
LISTA di record proposti, uno per ogni tabella di valori trovata,
cosi' l'utente puo' scegliere quali salvare.

IMPORTANTE: il riconoscimento resta un aiuto, non una lettura certa.
Ogni fornitore (LyondellBasell, Borealis, SABIC, PEBO, ecc.) usa un
layout diverso — questo modulo e' stato verificato contro esempi
reali di questi 4 fornitori, ma formati nuovi/mai visti potrebbero
essere riconosciuti solo in parte. Per questo la finestra di
importazione mostra sempre anche il testo completo estratto, per
verifica manuale prima di salvare.
"""
import re

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import pytesseract
    from pdf2image import convert_from_path
except ImportError:
    pytesseract = None
    convert_from_path = None


class LetturaCoAError(Exception):
    pass


_FORNITORI_NOTI = [
    "LYONDELLBASELL", "LYONDELL BASELL", "BASELL", "BOREALIS", "SABIC",
    "BRASKEM", "TOTALENERGIES", "TOTAL PETROCHEMICALS", "EXXONMOBIL",
    "EXXON MOBIL", "DOW", "INEOS", "REPSOL", "MOL GROUP", "SASOL",
    "QATAR PETROCHEMICAL", "QAPCO", "PEBO",
]

# ---------------------------------------------------------------------------
# Estrazione testo (PDF nativo, colonna-consapevole; OCR per le scansioni)
# ---------------------------------------------------------------------------
def _ricostruisci_righe(parole):
    """Raggruppa parole per riga (stessa 'top', ordinate per x) -> lista di stringhe."""
    righe = {}
    for w in parole:
        key = round(w["top"])
        righe.setdefault(key, []).append(w)
    out = []
    for k in sorted(righe.keys()):
        ordinate = sorted(righe[k], key=lambda w: w["x0"])
        out.append(" ".join(p["text"] for p in ordinate))
    return out


def _righe_pagina(page):
    """
    Ritorna (righe_intere, righe_colonna) per una pagina con testo nativo:
    - righe_intere: ricostruzione normale (serve per leggere le righe della
      tabella valori, che spesso attraversa tutta la larghezza pagina).
    - righe_colonna: parole separate in meta' sinistra/destra prima di
      ricostruire le righe, cosi' campi come "Numero lotto" nella
      testata non si mescolano col testo del blocco affiancato
      (mittente/destinatario) che sta alla stessa altezza.
    """
    parole = page.extract_words(use_text_flow=False, keep_blank_chars=False)
    if not parole:
        return [], []
    righe_intere = _ricostruisci_righe(parole)
    mid_x = page.width / 2
    sinistra = [w for w in parole if w["x0"] < mid_x]
    destra = [w for w in parole if w["x0"] >= mid_x]
    righe_colonna = _ricostruisci_righe(destra) + _ricostruisci_righe(sinistra)
    return righe_intere, righe_colonna


def _pagine_da_pdf(percorso_pdf):
    """
    Genera, per ogni pagina del PDF, (righe_intere, righe_colonna, testo_completo).
    Se una pagina non ha testo nativo (scansione), usa l'OCR: in quel caso
    righe_intere == righe_colonna (testo semplice, senza info di colonna).
    """
    if pdfplumber is None:
        raise LetturaCoAError("Il modulo 'pdfplumber' non e' installato. Esegui: pip install pdfplumber")

    pagine_ocr_da_fare = []
    risultati = []
    try:
        with pdfplumber.open(percorso_pdf) as pdf:
            for page in pdf.pages:
                righe_intere, righe_colonna = _righe_pagina(page)
                if righe_intere:
                    testo = "\n".join(righe_intere)
                    risultati.append((righe_intere, righe_colonna, testo))
                else:
                    risultati.append(None)  # segnaposto: serve OCR
                    pagine_ocr_da_fare.append(len(risultati) - 1)
    except Exception as exc:
        raise LetturaCoAError(f"Impossibile aprire il PDF: {exc}") from exc

    if pagine_ocr_da_fare:
        if pytesseract is None or convert_from_path is None:
            raise LetturaCoAError(
                "Questo PDF sembra una scansione (senza testo selezionabile) e servirebbe "
                "l'OCR, ma i moduli 'pytesseract'/'pdf2image' non sono installati "
                "(serve anche Tesseract OCR installato sul sistema)."
            )
        try:
            immagini = convert_from_path(percorso_pdf, dpi=300)
        except Exception as exc:
            raise LetturaCoAError(f"Impossibile convertire il PDF in immagine per l'OCR: {exc}") from exc
        for idx in pagine_ocr_da_fare:
            if idx >= len(immagini):
                risultati[idx] = ([], [], "")
                continue
            testo_ocr = pytesseract.image_to_string(immagini[idx], lang="ita+eng")
            righe = [r for r in testo_ocr.split("\n") if r.strip()]
            risultati[idx] = (righe, righe, testo_ocr)

    return risultati


# ---------------------------------------------------------------------------
# Estrazione dei valori di prova da una riga di testo
# ---------------------------------------------------------------------------
# Rimuove dalla riga: condizioni di prova (es. "190°C/5.0kg", "at 190 C"),
# codici metodo (es. "ISO1133-1", "ASTM D1238", "EN 728 / ISO 11357-6") e
# unita' di misura note — cio' che resta e' quasi sempre il valore.
_RIMUOVI_CONDIZIONI = [
    r"\d+[.,]?\d*\s*°?\s*C\s*/\s*\d+[.,]?\d*\s*(?:kg)?",
    r"\d+[.,]?\d*\s*Kg\s+at\s+\d+\s*°?\s*C\b",
    r"\d+[.,]?\d*\s*°C\b",
]
_RIMUOVI_METODO = r"\b(?:[A-Z]{1,6}\.?\s*){1,3}\d[\d\-\/\.]*\b"
_RIMUOVI_UNITA = [
    r"g\s*/?\s*10\s*min", r"g\s*/\s*cm\s*3", r"g\s*/\s*em\s*3", r"g\s*/\s*ml",
    r"kg\s*/\s*m\s*3", r"wt\s*%", r"ppm", r"hours?", r"minuti", r"min\b", r"%",
]

_NUM_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


def _estrai_valore_da_riga(riga, keyword_pattern):
    """Rimuove parola chiave/condizioni/metodo/unita' dalla riga e ritorna il
    primo numero (o codice breve tipo 'OK'/'A2') rimasto — e' il valore."""
    resto = re.sub(keyword_pattern, " ", riga, count=1, flags=re.IGNORECASE)
    for pat in _RIMUOVI_CONDIZIONI:
        resto = re.sub(pat, " ", resto, flags=re.IGNORECASE)
    resto = re.sub(_RIMUOVI_METODO, " ", resto)
    for pat in _RIMUOVI_UNITA:
        resto = re.sub(pat, " ", resto, flags=re.IGNORECASE)
    resto = resto.replace("_", " ").replace("|", " ")
    # OCR a volte introduce uno spazio dopo la virgola/punto decimale (es. "0, 957"): lo sana
    resto = re.sub(r"(?<=\d)[.,]\s+(?=\d)", ",", resto)

    m = _NUM_RE.search(resto)
    if m:
        return m.group(0)
    # nessun numero: forse un esito qualitativo (es. "OK", "Pos", "Conform")
    m2 = re.search(r"\b([A-Za-z]{2,10})\b", resto)
    if m2 and m2.group(1).lower() not in ("kg", "wt", "min", "the", "and", "for"):
        return m2.group(1)
    return ""


# Ordine di priorità: se una riga contiene piu' parole chiave (es. "Carbon
# Black Dispersion" contiene sia "carbon black" sia "dispersion"), vince la
# prima voce di questa lista che trova corrispondenza.
_CAMPI_PROPRIETA = [
    ("dispersione", r"dispersion[ei]?"),
    ("oit", r"\bOIT\b|oxidation\s*induction\s*time"),
    ("umidita", r"moisture(\s*content)?|water\s*content|umidit[àa]"),
    ("carbon_black", r"carbon\s*black(\s*content)?|nero\s*(di\s*)?fumo"),
    ("densita", r"density|densit[àa]"),
    ("volatili", r"volatile"),
    ("mfi_dichiarato", r"\bMFR\b|\bMFI\b|melt\s*(flow|index)"),
]


def _estrai_proprieta(righe_intere):
    """Cerca nelle righe i valori di prova noti. Ritorna (dict_campi, righe_riconosciute)."""
    campi = {}
    righe_riconosciute = []
    righe_gia_usate = set()

    for nome_campo, pattern in _CAMPI_PROPRIETA:
        if nome_campo in campi:
            continue
        for i, riga in enumerate(righe_intere):
            if i in righe_gia_usate:
                continue
            if re.search(pattern, riga, flags=re.IGNORECASE):
                valore = _estrai_valore_da_riga(riga, pattern)
                if valore:
                    campi[nome_campo] = valore
                    righe_gia_usate.add(i)
                    righe_riconosciute.append(riga.strip())
                break
    return campi, righe_riconosciute


# ---------------------------------------------------------------------------
# Estrazione fornitore / lotto / materiale
# ---------------------------------------------------------------------------
_PATTERNS_LOTTO_STESSA_RIGA = [
    r"^(?:Numero\s*(?:di\s*)?lotto|Numero\s*partita|Batch\s*Number|Lotto\s*n[°r]?\.?\s*/?\s*Batch\s*n[°r]?\.?|Batch\s*No\.?|Lot(?:to)?\s*(?:No\.?|Number|N[°r]\.?)?|Batch)\s*[:\-]?\s*([A-Z0-9][A-Z0-9 \-\/\.]{2,20}[A-Z0-9])",
]
_ETICHETTE_LOTTO_SOLE = re.compile(
    r"^(?:Numero\s*(?:di\s*)?lotto|Numero\s*partita|Batch\s*Number|Lotto\s*n[°r]?\.?\s*/?\s*Batch\s*n[°r]?\.?|Lot(?:to)?)\s*[:\-]?\s*$",
    re.IGNORECASE,
)

_PATTERNS_MATERIALE_STESSA_RIGA = [
    r"^(?:Grade)\s*[:\-]?\s*([A-Za-z0-9\-]{3,20})",
    r"^(?:Materiale\s*/\s*Material|Prodotto|Product(?:\s*name)?)\s*[:\-]\s*([A-Za-z0-9 \-\.\(\)_]{4,60})",
]
_ETICHETTE_MATERIALE_SOLE = re.compile(
    r"^(?:Materiale\s*/\s*Material|Prodotto|Product(?:\s*name)?|Grade|Material:\s*(?:Our\s*/\s*Your\s*description)?)\s*$",
    re.IGNORECASE,
)


def _primo_match(patterns, testo):
    for p in patterns:
        m = re.search(p, testo, flags=re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(1).strip()
    return ""


def _cerca_con_fallback_riga_dopo(righe, patterns_stessa_riga, etichetta_sola_regex):
    """Prova prima 'Etichetta: valore' sulla stessa riga; se l'etichetta e'
    da sola sulla sua riga, prende come valore la riga successiva utile."""
    testo = "\n".join(righe)
    trovato = _primo_match(patterns_stessa_riga, testo)
    if trovato:
        return trovato
    for i, riga in enumerate(righe):
        if etichetta_sola_regex.match(riga.strip()):
            for j in range(i + 1, min(i + 4, len(righe))):
                candidata = righe[j].strip()
                if candidata and len(candidata) < 60:
                    return candidata
    return ""


def _rileva_fornitore(righe):
    testo_upper = "\n".join(righe).upper()
    for nome in _FORNITORI_NOTI:
        if nome in testo_upper:
            return nome.title()
    return ""


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------
def estrai_candidati(percorso_pdf):
    """
    Analizza il PDF (anche multi-pagina, anche scansionato) e ritorna una
    lista di record candidati, uno per ogni pagina in cui sono stati
    trovati valori di prova. Ogni candidato e' un dict con:
    pagina, fornitore, codice_lotto, materiale, mfi_dichiarato,
    carbon_black, umidita, densita, volatili, dispersione, oit,
    note (riepilogo di TUTTE le righe di prova riconosciute in quella
    pagina, anche quelle senza una casella dedicata), testo_pagina.
    """
    pagine = _pagine_da_pdf(percorso_pdf)
    candidati = []

    for idx, dati_pagina in enumerate(pagine):
        if dati_pagina is None:
            continue
        righe_intere, righe_colonna, testo = dati_pagina
        if not righe_intere:
            continue

        campi, righe_riconosciute = _estrai_proprieta(righe_intere)
        if not campi:
            continue  # questa pagina non sembra contenere una tabella di valori di prova

        fornitore = _rileva_fornitore(righe_colonna or righe_intere)
        lotto = _cerca_con_fallback_riga_dopo(righe_colonna, _PATTERNS_LOTTO_STESSA_RIGA, _ETICHETTE_LOTTO_SOLE)
        materiale = _cerca_con_fallback_riga_dopo(righe_colonna, _PATTERNS_MATERIALE_STESSA_RIGA, _ETICHETTE_MATERIALE_SOLE)

        riepilogo = "\n".join(righe_riconosciute)
        candidato = {
            "pagina": idx + 1,
            "fornitore": fornitore,
            "codice_lotto": lotto,
            "materiale": materiale,
            "note": riepilogo,
            "testo_pagina": testo,
        }
        for nome_campo, _ in _CAMPI_PROPRIETA:
            candidato[nome_campo] = campi.get(nome_campo, "")
        candidati.append(candidato)

    return candidati
