# LP Tablet App

App web per il flusso: **ARCA crea LP → Ufficio assegna a un tablet →
Magazziniere modifica quantità/righe → Invia → l'esito finale viene
scritto su ARCA per la creazione della bolla.**

## Architettura

```
┌─────────────┐   polling ogni N sec    ┌───────────────────┐
│   ARCA      │ ───────────────────────▶│  Backend FastAPI   │
│ (SQL Server)│                          │  (Python)          │
│             │◀──── scrittura finale ──│                     │
└─────────────┘      (solo su "Invia")  │  + SQLite locale    │
                                          │  (stato in lavor.) │
                                          └─────────┬──────────┘
                                                     │ WebSocket
                                        ┌────────────┼────────────┐
                                        ▼                         ▼
                                 office.html               tablet.html
                                 (PC ufficio)              (tablet magazziniere)
```

Punto chiave: **mentre il magazziniere lavora, ARCA non viene toccato.**
Tutto (assegnazione tablet, modifiche quantità, righe cancellate) vive in
un piccolo database SQLite locale dell'app. Solo quando si preme **Invia**
l'app scrive il risultato finale su ARCA in un'unica operazione.
Questo evita di interferire con la logica interna del gestionale mentre
l'LP è "in lavorazione".

## Cosa devi fare tu prima che funzioni davvero

1. **Trovare le tabelle reali di ARCA.** Non conosco lo schema del tuo
   database. In `backend/arca_repository.py` ci sono query segnaposto
   (cerca `# TODO ARCA:`). Usa `backend/discover_schema.py` per
   individuare le tabelle vere:
   ```
   cd backend
   python discover_schema.py
   python discover_schema.py --colonne NOME_TABELLA_TROVATA
   ```
2. **Verificare la scrittura finale con cautela.** La funzione
   `scrivi_esito_finale_lp()` fa UPDATE/DELETE dirette. Prima di usarla
   su dati reali:
   - provala su un database di test/copia, non in produzione;
   - controlla se ARCA ha trigger o stored procedure che si aspettano
     di essere chiamate invece di una UPDATE diretta;
   - verifica il nome/valore di stato corretto che fa comparire l'LP
     come "pronto per bolla" lato ufficio in ARCA.
3. **Driver ODBC.** Serve il driver SQL Server installato sul PC dove
   gira il backend (es. "ODBC Driver 17 for SQL Server" di Microsoft).

## Avvio in locale

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env         # poi modifica .env con i dati veri di ARCA
python database.py             # crea il database locale SQLite
uvicorn main:app --host 0.0.0.0 --port 8000
```

- Interfaccia ufficio: `http://localhost:8000/office.html`
- Interfaccia tablet: `http://localhost:8000/tablet.html`

## Accesso da fuori rete (tablet in giro, ufficio remoto)

Dato che usi già Tailscale per l'accesso remoto ad Arca via RDP, la
strada più semplice è:

1. Installa Tailscale anche sul PC/server dove gira questo backend.
2. Sui tablet e sui PC ufficio, installa il client Tailscale (o usa il
   subnet router che hai già configurato).
3. Apri le pagine usando l'IP Tailscale del backend, es.
   `http://100.x.y.z:8000/tablet.html` invece di `localhost`.

Nessuna esposizione su internet pubblico necessaria.

## Sicurezza (da rafforzare prima di un uso reale)

Questo scheletro ha solo un controllo minimale (`APP_SHARED_TOKEN` non
ancora applicato a tutte le rotte). Prima di usarlo con dati reali:
- aggiungi autenticazione vera (almeno una password per ufficio e una
  per registrazione tablet);
- restringi CORS (`allow_origins`) agli IP Tailscale invece di `*`;
- valuta HTTPS anche in LAN se i tablet passano da reti non fidate
  (4G, WiFi cliente, come nel tuo scenario RDP).

## Struttura file

```
lp-tablet-app/
├── README.md
├── backend/
│   ├── main.py              # app FastAPI, rotte REST + WebSocket, polling
│   ├── arca_repository.py   # UNICO punto che parla con ARCA (da adattare!)
│   ├── discover_schema.py   # script per trovare le tabelle reali di ARCA
│   ├── database.py          # connessione ARCA (pyodbc) + SQLite locale
│   ├── models.py            # modelli dati (Pydantic)
│   ├── ws_manager.py        # gestione canali WebSocket
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── office.html          # interfaccia ufficio
    └── tablet.html          # interfaccia magazziniere (pensata per tablet)
```

## Prossimi passi consigliati

1. Esegui `discover_schema.py` sul DB di ARCA e mandami/annota i nomi
   reali delle tabelle LP testata/righe.
2. Aggiorniamo insieme `arca_repository.py` con le query vere.
3. Test end-to-end con un LP di prova, partendo da un DB di test se
   possibile.
4. Aggiungiamo autenticazione minima e la mettiamo su Tailscale.
