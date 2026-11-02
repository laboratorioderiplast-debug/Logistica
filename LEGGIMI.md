# Certificati EN 10204 MOD. 3.1 — Deriplast Group

App Windows standalone per creare i certificati di controllo laboratorio
EN 10204 MOD. 3.1, con ricerca articoli/OP su Arca e anagrafica materie
prime (MP) locale.

---

## 1. Installazione (per usarla / svilupparla)

Serve **Python 3.10 o superiore** installato su Windows
([python.org](https://www.python.org/downloads/), spuntare "Add Python to PATH"
durante l'installazione).

Apri il Prompt dei comandi nella cartella del progetto e lancia:

```
pip install -r requirements.txt
```

Poi avvia l'app con:

```
python main.py
```

Al primo avvio l'app è in **modalità demo** (dati Arca finti), così puoi
provarla subito. Il database locale (bozze certificati + materie prime)
viene creato automaticamente in `%APPDATA%\CertificatiEN31\dati.db`.

### Per l'OCR (lettura CoA scansionati)

Se un CoA fornitore è una scansione (foto/fax senza testo selezionabile —
l'app lo rileva da sola e prova comunque a leggerlo), serve anche:

1. **Tesseract OCR** — installer per Windows:
   https://github.com/UB-Mannheim/tesseract/wiki (durante l'installazione,
   spunta anche la lingua "Italian" tra i language pack disponibili).
2. **Poppler** (serve a `pdf2image` per convertire le pagine PDF in
   immagini) — scarica i binari Windows da
   https://github.com/oschwartz10612/poppler-windows/releases, estrai
   lo zip e aggiungi la sotto-cartella `Library\bin` al PATH di sistema.

Senza questi due programmi, l'importazione da CoA funziona comunque per
i PDF "normali" (con testo selezionabile) — serve l'OCR solo per le
scansioni.

---

## 2. Collegare l'app ad Arca (dati reali)

Apri **config.ini** con un editor di testo e modifica la sezione `[arca]`:

```ini
[arca]
driver = SQL Server
server = svrgestionale
database = ADB_DERIPLAST
trusted_connection = yes
```

- `server` e `database`: verificati con successo su questo impianto —
  attenzione, "DERIPLAST" mostrato nel login di Arca NON è il nome
  tecnico del database (che è invece `ADB_DERIPLAST`).
- `trusted_connection = yes` usa l'autenticazione integrata di Windows
  — **nessuna password viene mai scritta in questo file**.
- Il driver confermato su questo PC è `SQL Server` (quello classico,
  incluso di default in Windows). Se in futuro installate
  "ODBC Driver 17/18 for SQL Server", potete usare quello.

Poi in `config.ini`, sezione `[app]`, metti:

```ini
modalita_demo = no
```

Infine, nella finestra principale dell'app, premi **"🔌 Test connessione
Arca"** per verificare che tutto funzioni.

### Tabelle usate

La ricerca Articoli/OP usa due **viste** di Arca (più complete delle
tabelle base, includono anche i limiti dimensionali):

- **Articoli**: `VV_Arca_Articoli` — codice, descrizione, norma/SDR
  (`DescSDR`), PN, e i limiti Min/Max di diametro e spessore.
- **Ordini di produzione (OP)**: `VV_Arca_Ordini` — OP, data, articolo,
  linea, quantità, e i limiti Min/Max specifici di quell'ordine (DN,
  Dmin, Dmax, SPmin, SPmax).

Quando cerchi un Articolo o un OP nell'editor del certificato, se
Arca restituisce questi limiti dimensionali, l'app propone di
aggiungere automaticamente una sezione **"Controlli dimensionali"**
già pre-compilata con Min/Max (i valori misurati Val1/Val2/Val3/Media
restano da inserire dopo la misurazione in laboratorio, come sempre).

Se in futuro questi nomi di vista/campo dovessero cambiare, si
aggiornano SOLO nella sezione `[arca_tabelle]` di `config.ini` — il
codice dell'app non va toccato.

---

## 3. Materie prime (MP)

Pulsante **"🧪 Materie prime"**, sia nella finestra principale sia
nell'editor del certificato:

- **📄 Importa da CoA (PDF)**: apri il certificato di analisi (CoA) del
  fornitore in PDF — l'app estrae il testo (con OCR automatico se il
  PDF è una scansione senza testo selezionabile, come spesso accade
  per i CoA ricevuti via fax/scanner) e prova a individuare
  fornitore, lotto, materiale, MFI, Carbon Black, Umidità, Densità,
  Volatili, Dispersione e OIT. Si apre una finestra con tutti i campi
  proposti a sinistra (da correggere se serve) e il testo completo
  estratto a destra, per verificare. Nel campo Note viene anche
  riportato il riepilogo di tutte le righe di prova riconosciute nel
  documento, così nessun valore va perso anche se non rientra in una
  casella dedicata. Il PDF originale viene copiato in
  `%APPDATA%\CertificatiEN31\coa_pdf\` e resta collegato al record: da
  "🧪 Materie prime" puoi riaprirlo in qualsiasi momento con
  **"📄 Apri CoA collegato"**.

  Se il PDF contiene **più di un certificato/lotto** (es. un unico
  file con due CoA allegati), l'app lo rileva automaticamente e apre
  una finestra di verifica in sequenza per ciascun lotto trovato.

  Verificato con successo su CoA reali di **LyondellBasell/Basell,
  Borealis, SABIC e PEBO** (compresi due scansionati via OCR).

  ⚠️ Il riconoscimento automatico è un aiuto, non una lettura certa:
  ogni fornitore (LyondellBasell, Borealis, Sabic, ecc.) usa un
  formato diverso, quindi **controlla sempre i valori proposti** prima
  di salvare, specialmente sui PDF scansionati (l'OCR occasionalmente
  confonde cifre simili). Se mi mandate CoA reali di altri fornitori,
  posso affinare parecchio il riconoscimento automatico anche per
  quei formati specifici (vedi `app/coa_reader.py`).

- **+ Nuova materia prima**: inserimento manuale (fornitore, lotto,
  materiale, MFI, Carbon Black, Umidità, Densità, Volatili,
  Dispersione, OIT, note) — gli stessi valori tracciati nel registro
  di accettazione reale (`02_ACCETTAZIONE_RIGHE` nel database
  `QUALITY`, vedi sezione 4).
- **📥 Importa da CSV**: carica in blocco un file CSV con queste colonne
  (intestazione obbligatoria):
  ```
  fornitore,codice_lotto,materiale,mfi_dichiarato,carbon_black,umidita,densita,volatili,dispersione,oit,note
  ```
  (vedi `esempio_import_materie_prime.csv` incluso nel progetto)
- Dall'editor del certificato, doppio clic su una materia prima per
  inserirla automaticamente in "Lot 1" o "Lot 2 Raw material".

Le materie prime **non** arrivano da Arca (come da indicazioni: il
collegamento ad Arca serve solo per Articoli e OP) — sono gestite in
un piccolo database locale su questo PC.

---

## 4. Storico materie prime e produzioni dal vecchio Access

Scavando nel vecchio `QUALITY R84.accdb` è emerso che **i dati storici
non sono dentro il file Access**: sono tabelle collegate a un secondo
database SQL Server, separato da Arca, che nelle vecchie stringhe di
connessione si chiama **`QUALITY`** (tabelle tipo
`dbo_02_ACCETTAZIONE_RIGHE` per l'accettazione materie prime,
`dbo_13_KR_REG_PRODUZIONE` per il registro di produzione,
`dbo_21_CERTIFICATI` per i certificati già emessi). L'Access è solo la
"vetrina" (maschere/report), i dati veri stanno lì.

Per recuperare questo storico ci sono due strade:

1. **Collegamento diretto** (come fatto per Arca): se questo database
   `QUALITY` è ancora raggiungibile in rete, basta sapere il nome del
   server attuale (nel vecchio file risultava `ctuarca`, ma potrebbe
   essere cambiato) e posso scrivere un connettore identico a quello
   di Arca per leggerne i dati direttamente.
2. **Esportazione una tantum**: se preferite non collegarvi in
   automatico, si può esportare da Access/SQL Server un CSV per la
   tabella interessata, e importarlo con:
   ```python
   from app import local_db
   local_db.importa_produzioni_da_csv("percorso\\storico.csv", fonte="Access QUALITY R84")
   ```
   Intestazioni CSV attese: `lotto,data,codice_articolo,descrizione,linea,turno,quantita,note`

> ⚠️ Nota di sicurezza: nel vecchio Access la password di questo
> database (`QLT` / `QLT1`) era anch'essa scritta in chiaro nel
> codice. Se il database `QUALITY` è ancora attivo con quelle
> credenziali, vale la pena farle cambiare dall'IT — sono visibili a
> chiunque apra il file Access con un editor di testo.

---

## 5. Creare il file .exe (per distribuirla senza installare Python)

Sul PC Windows dove volete generare l'eseguibile:

```
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --onefile --windowed --name CertificatiEN31 ^
    --add-data "assets;assets" ^
    --add-data "config.ini;." ^
    main.py
```

L'eseguibile finale sarà in `dist\CertificatiEN31.exe`. Copiate accanto
ad esso anche il file `config.ini` (così resta modificabile senza
dover rigenerare l'exe) e la cartella `assets` con logo e firma.

> Consiglio: build fatta *su Windows*, non da Linux/Mac — PyInstaller
> genera l'eseguibile per il sistema operativo su cui viene lanciato.

---

## 5. Struttura del progetto

```
CertificatiEN31/
  main.py                  punto di ingresso
  config.ini                configurazione (Arca, azienda, firmatari)
  requirements.txt
  assets/
    logo.jpg                logo Deriplast Group
    firma_buzzoni.png        firma per "Approved"
  app/
    config.py                lettura config.ini
    arca_connector.py         ricerca Articoli/OP su Arca (pyodbc)
    local_db.py               database locale SQLite (certificati + MP)
    modelli_certificato.py    struttura dati + certificato di esempio
    pdf_generator.py          generazione PDF (reportlab)
    ui_main.py                finestra principale (elenco certificati)
    ui_editor.py              editor certificato + ricerca Arca + MP
```

---

## 6. Nota sulla sicurezza

Nel vecchio archivio Access (`QUALITY R84.accdb`) erano salvate in
chiaro le credenziali (utente/password) di connessione al database.
Questa nuova app **non lo fa**: usa l'autenticazione integrata di
Windows, quindi non c'è nessuna password da proteggere nel file di
configurazione. Se in futuro serve un'autenticazione SQL con utente e
password, si consiglia di salvarla in **Gestione credenziali di
Windows** (Credential Manager) invece che in un file di testo.
