"""
Finestra di modifica di un certificato: dati di testata, sezioni/righe
di prova dinamiche, piede pagina. Interamente basata su Tkinter (nessuna
libreria grafica esterna, per semplificare l'installazione su Windows).
"""
import copy
import os
import shutil
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from . import local_db
from . import arca_connector
from . import coa_reader
from .config import get_config
from .pdf_generator import genera_pdf
from .modelli_certificato import certificato_vuoto


FONT_LABEL = ("Segoe UI", 9, "bold")
FONT_NORMAL = ("Segoe UI", 9)


class EditorCertificato(tk.Toplevel):
    def __init__(self, master, dati=None, id_certificato=None, nome_bozza=None):
        super().__init__(master)
        self.title("Certificato EN 10204 MOD. 3.1")
        self.geometry("1180x760")
        self.minsize(900, 600)

        self.dati = dati if dati is not None else certificato_vuoto()
        self.id_certificato = id_certificato
        self.nome_bozza = nome_bozza or "Nuovo certificato"

        self.header_widgets = {}
        self.footer_widgets = {}
        self.section_frames = []  # ogni elemento: dict con 'frame' e 'rows' (lista di dict widget)

        self._build_toolbar()
        self._build_scroll_area()
        self._build_header()
        self._build_sections_area()
        self._build_footer()

        self._redraw_sections()

    # ------------------------------------------------------------------
    # Layout generale
    # ------------------------------------------------------------------
    def _build_toolbar(self):
        bar = tk.Frame(self, bg="#33339A")
        bar.pack(side="top", fill="x")
        tk.Label(bar, text=self.nome_bozza, bg="#33339A", fg="white",
                  font=("Segoe UI", 11, "bold")).pack(side="left", padx=10, pady=8)

        def btn(text, cmd):
            b = tk.Button(bar, text=text, command=cmd, bg="white", fg="#33339A",
                          font=("Segoe UI", 9, "bold"), relief="flat", padx=8, pady=4)
            b.pack(side="left", padx=4, pady=6)
            return b

        btn("💾 Salva", self.salva)
        btn("📄 Esporta PDF", self.esporta_pdf)
        btn("🔎 Cerca articolo (Arca)", self.cerca_articolo)
        btn("🔎 Cerca OP (Arca)", self.cerca_op)
        btn("🧪 Materie prime", self.gestisci_materie_prime)

    def _build_scroll_area(self):
        container = tk.Frame(self)
        container.pack(side="top", fill="both", expand=True)

        canvas = tk.Canvas(container, borderwidth=0, highlightthickness=0)
        vscroll = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.scrollable_frame = tk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=vscroll.set)

        canvas.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

    # ------------------------------------------------------------------
    # Testata
    # ------------------------------------------------------------------
    def _build_header(self):
        frame = tk.LabelFrame(self.scrollable_frame, text="Dati certificato", font=FONT_LABEL, padx=8, pady=8)
        frame.pack(side="top", fill="x", padx=10, pady=8)

        h = self.dati.get("header", {})

        def entry(row, col, key, label, width=14, colspan=1):
            tk.Label(frame, text=label, font=FONT_LABEL).grid(row=row, column=col, sticky="w", padx=4, pady=3)
            e = tk.Entry(frame, width=width, font=FONT_NORMAL)
            e.insert(0, h.get(key, ""))
            e.grid(row=row, column=col + 1, columnspan=colspan, sticky="we", padx=4, pady=3)
            self.header_widgets[key] = e
            return e

        entry(0, 0, "id_certificate", "Id Certificate")
        entry(0, 2, "line", "Line", width=6)
        entry(0, 4, "dn", "DN", width=6)
        entry(0, 6, "sdr", "SDR", width=6)
        entry(0, 8, "date", "Date", width=12)

        entry(1, 0, "article", "Article - HDPE PIPE", width=90, colspan=9)
        entry(2, 0, "ref_standard", "Ref. Standard", width=90, colspan=9)
        entry(3, 0, "lot1", "Lot 1 Raw material", width=90, colspan=9)
        entry(4, 0, "lot2", "Lot 2 Raw material", width=90, colspan=9)
        entry(5, 0, "production_batch", "Production Batch", width=30, colspan=3)
        entry(6, 0, "notes", "Notes", width=90, colspan=9)

    # ------------------------------------------------------------------
    # Sezioni di prova
    # ------------------------------------------------------------------
    def _build_sections_area(self):
        outer = tk.LabelFrame(self.scrollable_frame, text="Prove / risultati", font=FONT_LABEL, padx=8, pady=8)
        outer.pack(side="top", fill="both", expand=True, padx=10, pady=8)
        self.sections_container = outer

        btnbar = tk.Frame(self.scrollable_frame)
        btnbar.pack(side="top", fill="x", padx=10)
        tk.Button(btnbar, text="+ Aggiungi sezione di prova", command=self.aggiungi_sezione).pack(side="left", pady=4)
        tk.Button(btnbar, text="📋 Carica esempio", command=self.carica_esempio).pack(side="left", padx=6)

    def _redraw_sections(self):
        for child in self.sections_container.winfo_children():
            child.destroy()

        for si, section in enumerate(self.dati.get("sections", [])):
            sframe = tk.Frame(self.sections_container, bd=1, relief="solid", padx=4, pady=4)
            sframe.pack(side="top", fill="x", pady=(0, 8))

            top = tk.Frame(sframe)
            top.pack(side="top", fill="x")
            tk.Label(top, text=f"Sezione {si + 1}", font=FONT_LABEL, fg="#33339A").pack(side="left")
            tk.Button(top, text="+ riga", command=lambda si=si: self.aggiungi_riga(si)).pack(side="right", padx=2)
            tk.Button(top, text="× rimuovi sezione", fg="#b33",
                      command=lambda si=si: self.rimuovi_sezione(si)).pack(side="right", padx=2)

            for ri, row in enumerate(section.get("rows", [])):
                self._build_row(sframe, si, ri, row)

    def _build_row(self, parent, si, ri, row):
        rframe = tk.Frame(parent, bd=1, relief="groove", padx=4, pady=4)
        rframe.pack(side="top", fill="x", pady=3)

        desc = tk.Text(rframe, width=60, height=2, font=FONT_NORMAL, wrap="word")
        desc.insert("1.0", row.get("desc", ""))
        desc.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=4)
        desc.bind("<FocusOut>", lambda e, si=si, ri=ri: self._sync_row_desc(si, ri))

        confframe = tk.Frame(rframe)
        confframe.grid(row=0, column=1, rowspan=2, padx=6)
        tk.Label(confframe, text="Conformity", font=FONT_LABEL).pack()
        conf_val = tk.Entry(confframe, width=8, font=FONT_NORMAL, justify="center")
        conf_val.insert(0, row.get("conf_value", "Pos"))
        conf_val.pack()

        colframe = tk.Frame(rframe)
        colframe.grid(row=0, column=2, rowspan=2, padx=6, sticky="w")

        col_widgets = []
        for ci, c in enumerate(row.get("columns", [])):
            cw = tk.Frame(colframe)
            cw.pack(side="left", padx=4)
            lbl = tk.Entry(cw, width=8, font=FONT_LABEL, justify="center")
            lbl.insert(0, c.get("label", ""))
            lbl.pack()
            val = tk.Entry(cw, width=8, font=FONT_NORMAL, justify="center")
            val.insert(0, c.get("value", ""))
            val.pack()
            rm = tk.Button(cw, text="×", fg="#b33", command=lambda si=si, ri=ri, ci=ci: self.rimuovi_colonna(si, ri, ci))
            rm.pack()
            col_widgets.append((lbl, val))

        actions = tk.Frame(rframe)
        actions.grid(row=0, column=3, rowspan=2, padx=4, sticky="ne")
        tk.Button(actions, text="+ valore", command=lambda si=si, ri=ri: self.aggiungi_colonna(si, ri)).pack(fill="x")
        tk.Button(actions, text="× riga", fg="#b33",
                  command=lambda si=si, ri=ri: self.rimuovi_riga(si, ri)).pack(fill="x", pady=(2, 0))

        # riferimenti ai widget per poter rileggere i valori al momento del salvataggio
        row["_widgets"] = {"desc": desc, "conf_value": conf_val, "columns": col_widgets}

    # ------------------------------------------------------------------
    # Piede pagina
    # ------------------------------------------------------------------
    def _build_footer(self):
        frame = tk.LabelFrame(self.scrollable_frame, text="Piede pagina", font=FONT_LABEL, padx=8, pady=8)
        frame.pack(side="top", fill="x", padx=10, pady=(0, 12))

        f = self.dati.get("footer", {})

        def entry(row, col, key, label, width=20):
            tk.Label(frame, text=label, font=FONT_LABEL).grid(row=row, column=col, sticky="w", padx=4, pady=3)
            e = tk.Entry(frame, width=width, font=FONT_NORMAL)
            e.insert(0, f.get(key, ""))
            e.grid(row=row, column=col + 1, sticky="we", padx=4, pady=3)
            self.footer_widgets[key] = e

        entry(0, 0, "location", "Luogo")
        entry(0, 2, "date", "Data")
        entry(1, 0, "prepared_by", "Prepared (nome)")
        entry(1, 2, "approved_by", "Approved (nome)")
        entry(2, 0, "notes", "Notes", width=60)

    # ------------------------------------------------------------------
    # Sincronizzazione widget -> dati
    # ------------------------------------------------------------------
    def _sync_row_desc(self, si, ri):
        pass  # la lettura definitiva avviene in _raccogli_dati()

    def _raccogli_dati(self):
        """Legge tutti i widget e aggiorna self.dati. Da chiamare prima di salvare/esportare."""
        h = self.dati.setdefault("header", {})
        for key, w in self.header_widgets.items():
            h[key] = w.get()

        for section in self.dati.get("sections", []):
            for row in section.get("rows", []):
                widgets = row.get("_widgets")
                if not widgets:
                    continue
                row["desc"] = widgets["desc"].get("1.0", "end").strip()
                row["conf_value"] = widgets["conf_value"].get()
                row["conf_label"] = "Conformity"
                new_cols = []
                for lbl_w, val_w in widgets["columns"]:
                    new_cols.append({"label": lbl_w.get(), "value": val_w.get()})
                row["columns"] = new_cols

        f = self.dati.setdefault("footer", {})
        for key, w in self.footer_widgets.items():
            f[key] = w.get()

    # ------------------------------------------------------------------
    # Azioni: sezioni/righe/colonne
    # ------------------------------------------------------------------
    def aggiungi_sezione(self):
        self._raccogli_dati()
        self.dati.setdefault("sections", []).append({
            "rows": [{"desc": "Descrizione della prova...", "conf_label": "Conformity",
                      "conf_value": "Pos", "columns": [{"label": "Val1", "value": "0,00"}]}]
        })
        self._redraw_sections()

    def rimuovi_sezione(self, si):
        if not messagebox.askyesno("Conferma", "Rimuovere questa intera sezione di prova?"):
            return
        self._raccogli_dati()
        del self.dati["sections"][si]
        self._redraw_sections()

    def aggiungi_riga(self, si):
        self._raccogli_dati()
        self.dati["sections"][si]["rows"].append({
            "desc": "Descrizione della prova...", "conf_label": "Conformity",
            "conf_value": "Pos", "columns": [{"label": "Val1", "value": "0,00"}]
        })
        self._redraw_sections()

    def rimuovi_riga(self, si, ri):
        self._raccogli_dati()
        del self.dati["sections"][si]["rows"][ri]
        self._redraw_sections()

    def aggiungi_colonna(self, si, ri):
        self._raccogli_dati()
        self.dati["sections"][si]["rows"][ri]["columns"].append({"label": "Val", "value": "0,00"})
        self._redraw_sections()

    def rimuovi_colonna(self, si, ri, ci):
        self._raccogli_dati()
        del self.dati["sections"][si]["rows"][ri]["columns"][ci]
        self._redraw_sections()

    def carica_esempio(self):
        if not messagebox.askyesno("Conferma", "Sostituire il contenuto attuale con il certificato di esempio?"):
            return
        from .modelli_certificato import certificato_esempio
        self.dati = certificato_esempio()
        self._refresh_all()

    def _refresh_all(self):
        # ricostruisce testata/piede pagina/sezioni dai nuovi dati
        for w in self.scrollable_frame.winfo_children():
            w.destroy()
        self.header_widgets = {}
        self.footer_widgets = {}
        self._build_header()
        self._build_sections_area()
        self._build_footer()
        self._redraw_sections()

    # ------------------------------------------------------------------
    # Salvataggio / Esportazione
    # ------------------------------------------------------------------
    def salva(self):
        self._raccogli_dati()
        dati_puliti = self._dati_senza_widget()
        nome = self.nome_bozza
        top = tk.Toplevel(self)
        top.title("Salva bozza")
        tk.Label(top, text="Nome bozza:").pack(padx=10, pady=(10, 0))
        var = tk.StringVar(value=nome)
        e = tk.Entry(top, textvariable=var, width=40)
        e.pack(padx=10, pady=6)
        e.focus_set()

        def conferma():
            nuovo_nome = var.get().strip() or nome
            nuovo_id = local_db.salva_certificato(nuovo_nome, dati_puliti, self.id_certificato)
            self.id_certificato = nuovo_id
            self.nome_bozza = nuovo_nome
            self.title(f"Certificato EN 10204 MOD. 3.1 — {nuovo_nome}")
            top.destroy()
            messagebox.showinfo("Salvato", f"Bozza salvata: {nuovo_nome}")

        tk.Button(top, text="Salva", command=conferma).pack(pady=(0, 10))

    def _dati_senza_widget(self):
        dati = copy.deepcopy(self.dati)
        for section in dati.get("sections", []):
            for row in section.get("rows", []):
                row.pop("_widgets", None)
        return dati

    def esporta_pdf(self):
        self._raccogli_dati()
        dati_puliti = self._dati_senza_widget()
        suggerito = f"Certificato_{dati_puliti['header'].get('id_certificate', 'senza_id')}.pdf"
        percorso = filedialog.asksaveasfilename(
            defaultextension=".pdf", initialfile=suggerito,
            filetypes=[("File PDF", "*.pdf")],
        )
        if not percorso:
            return
        try:
            genera_pdf(dati_puliti, percorso)
        except Exception as exc:
            messagebox.showerror("Errore", f"Impossibile generare il PDF:\n{exc}")
            return
        if messagebox.askyesno("PDF generato", f"PDF creato in:\n{percorso}\n\nAprirlo ora?"):
            try:
                os.startfile(percorso)  # Windows
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Integrazione Arca
    # ------------------------------------------------------------------
    def cerca_articolo(self):
        FinestraRicercaArca(self, tipo="articolo", on_scelta=self._applica_articolo)

    def cerca_op(self):
        FinestraRicercaArca(self, tipo="op", on_scelta=self._applica_op)

    def _applica_articolo(self, art):
        h = self.header_widgets
        h["article"].delete(0, "end")
        h["article"].insert(0, f"{art.get('codice_articolo','')} - {art.get('descrizione','')}")
        h["ref_standard"].delete(0, "end")
        h["ref_standard"].insert(0, art.get("norma", ""))
        h["dn"].delete(0, "end")
        h["dn"].insert(0, art.get("de", ""))
        h["sdr"].delete(0, "end")
        h["sdr"].insert(0, art.get("sdr", ""))
        self._proponi_sezione_dimensionale(art)

    def _applica_op(self, op):
        h = self.header_widgets
        h["line"].delete(0, "end")
        h["line"].insert(0, op.get("linea", ""))
        h["date"].delete(0, "end")
        h["date"].insert(0, op.get("data", ""))
        h["production_batch"].delete(0, "end")
        h["production_batch"].insert(0, op.get("lotto", ""))
        if op.get("dn"):
            h["dn"].delete(0, "end")
            h["dn"].insert(0, op.get("dn", ""))
        self._proponi_sezione_dimensionale(op)

    def _proponi_sezione_dimensionale(self, dati_arca):
        """Se Arca ha restituito i limiti Min/Max diametro/spessore, propone
        di aggiungere una sezione 'Controlli dimensionali' gia' pre-compilata
        (i valori misurati Val1/Val2/Val3 restano da inserire in laboratorio)."""
        diam_min = dati_arca.get("diam_min", "")
        diam_max = dati_arca.get("diam_max", "")
        spess_min = dati_arca.get("spess_min", "")
        spess_max = dati_arca.get("spess_max", "")
        if not any([diam_min, diam_max, spess_min, spess_max]):
            return  # Arca non ha restituito limiti dimensionali per questo articolo/OP

        if not messagebox.askyesno(
            "Limiti dimensionali trovati",
            "Arca ha restituito i limiti Min/Max di diametro e/o spessore per questo "
            "articolo.\n\nVuoi aggiungere una sezione 'Controlli dimensionali' "
            "gia' pre-compilata con questi limiti? (I valori misurati Val1/Val2/Val3 "
            "andranno poi inseriti a mano dopo la misurazione in laboratorio.)"
        ):
            return

        self._raccogli_dati()
        righe = []
        if diam_min or diam_max:
            righe.append({
                "desc": "Dimensional diameter - Diameter meter - Value between diameter Min and diameter Max",
                "conf_label": "Conformity", "conf_value": "Pos",
                "columns": [
                    {"label": "Min", "value": diam_min}, {"label": "Max", "value": diam_max},
                    {"label": "Val1", "value": ""}, {"label": "Val2", "value": ""},
                    {"label": "Val3", "value": ""}, {"label": "Media", "value": ""},
                ],
            })
        if spess_min or spess_max:
            righe.append({
                "desc": "Dimensional thickness - Micrometer - Value between Min thickness and Max thickness",
                "conf_label": "Conformity", "conf_value": "Pos",
                "columns": [
                    {"label": "Min", "value": spess_min}, {"label": "Max", "value": spess_max},
                    {"label": "Val1", "value": ""}, {"label": "Val2", "value": ""},
                    {"label": "Val3", "value": ""}, {"label": "Media", "value": ""},
                ],
            })
        if righe:
            self.dati.setdefault("sections", []).append({"rows": righe})
            self._redraw_sections()

    def gestisci_materie_prime(self):
        FinestraMateriePrime(self, on_scelta=self._applica_materia_prima)

    def _applica_materia_prima(self, mp):
        h = self.header_widgets
        testo = f"{mp.get('fornitore','')} - {mp.get('materiale','')} - Lotto: {mp.get('codice_lotto','')}"
        if not h["lot1"].get():
            h["lot1"].delete(0, "end")
            h["lot1"].insert(0, testo)
        else:
            h["lot2"].delete(0, "end")
            h["lot2"].insert(0, testo)


class FinestraRicercaArca(tk.Toplevel):
    """Piccola finestra di ricerca Articoli/OP su Arca (o dati demo)."""

    def __init__(self, master, tipo, on_scelta):
        super().__init__(master)
        self.tipo = tipo
        self.on_scelta = on_scelta
        self.title("Cerca articolo su Arca" if tipo == "articolo" else "Cerca ordine di produzione (OP) su Arca")
        self.geometry("720x420")

        cfg = get_config()
        top = tk.Frame(self)
        top.pack(fill="x", padx=8, pady=8)
        if cfg.modalita_demo:
            tk.Label(top, text="⚠ Modalita' demo attiva (dati finti) — vedi config.ini",
                      fg="#a66", font=FONT_NORMAL).pack(side="top", anchor="w")

        search_row = tk.Frame(self)
        search_row.pack(fill="x", padx=8)
        tk.Label(search_row, text="Cerca:", font=FONT_LABEL).pack(side="left")
        self.var_search = tk.StringVar()
        e = tk.Entry(search_row, textvariable=self.var_search, width=40)
        e.pack(side="left", padx=6)
        e.bind("<Return>", lambda ev: self._cerca())
        tk.Button(search_row, text="Cerca", command=self._cerca).pack(side="left")

        columns = ("codice_articolo", "descrizione", "de", "sdr", "diam_min", "diam_max", "spess_min", "spess_max") if tipo == "articolo" else \
                  ("lotto", "data", "codice_articolo", "linea", "quantita", "dn", "diam_min", "diam_max")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        for c in columns:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=130)
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree.bind("<Double-1>", lambda ev: self._conferma())

        btnrow = tk.Frame(self)
        btnrow.pack(fill="x", padx=8, pady=(0, 8))
        tk.Button(btnrow, text="Usa selezionato", command=self._conferma).pack(side="right")

        self._risultati = []
        self._cerca()

    def _cerca(self):
        testo = self.var_search.get()
        try:
            if self.tipo == "articolo":
                self._risultati = arca_connector.cerca_articoli(testo)
            else:
                self._risultati = arca_connector.cerca_op(testo)
        except arca_connector.ArcaConnectionError as exc:
            messagebox.showerror("Errore connessione Arca", str(exc))
            self._risultati = []

        for i in self.tree.get_children():
            self.tree.delete(i)
        for r in self._risultati:
            values = [r.get(c, "") for c in self.tree["columns"]]
            self.tree.insert("", "end", values=values)

    def _conferma(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        self.on_scelta(self._risultati[idx])
        self.destroy()


class RevisioneCoA(tk.Toplevel):
    """
    Mostra i campi individuati automaticamente nel CoA (da correggere se
    serve) affiancati al testo completo estratto dal PDF, cosi' l'utente
    puo' verificare prima di salvare la materia prima.
    """

    def __init__(self, master, percorso_pdf, campi_proposti, testo_estratto, on_conferma=None, numero_pagina=None):
        super().__init__(master)
        self.percorso_pdf = percorso_pdf
        self.on_conferma = on_conferma
        self.title("Verifica dati estratti dal CoA")
        self.geometry("980x560")

        etichetta_file = os.path.basename(percorso_pdf)
        if numero_pagina:
            etichetta_file += f" — pagina {numero_pagina}"
        tk.Label(self, text=f"File: {etichetta_file}",
                  font=("Segoe UI", 9, "italic"), fg="#555").pack(anchor="w", padx=10, pady=(8, 0))
        tk.Label(self, text="⚠ Riconoscimento automatico: controlla sempre i valori prima di salvare.",
                  fg="#a66", font=("Segoe UI", 9)).pack(anchor="w", padx=10, pady=(0, 6))

        body = tk.Frame(self)
        body.pack(fill="both", expand=True, padx=10, pady=6)

        # --- colonna sinistra: campi proposti, modificabili ---
        left = tk.LabelFrame(body, text="Dati proposti (verifica e correggi)", padx=8, pady=8)
        left.pack(side="left", fill="y", padx=(0, 8))

        self.vars = {}
        campi_label = [
            ("fornitore", "Fornitore"), ("codice_lotto", "Codice lotto"),
            ("materiale", "Materiale / grade"),
            ("mfi_dichiarato", "MFI"), ("carbon_black", "Carbon Black"),
            ("umidita", "Umidità"), ("densita", "Densità"),
            ("volatili", "Volatili"), ("dispersione", "Dispersione"),
            ("oit", "OIT"),
        ]
        for i, (key, label) in enumerate(campi_label):
            tk.Label(left, text=label, font=("Segoe UI", 9, "bold")).grid(row=i, column=0, sticky="w", pady=4)
            v = tk.StringVar(value=campi_proposti.get(key, ""))
            tk.Entry(left, textvariable=v, width=32).grid(row=i, column=1, pady=4, padx=6)
            self.vars[key] = v

        tk.Label(left, text="Note", font=("Segoe UI", 9, "bold")).grid(row=len(campi_label), column=0, sticky="nw", pady=4)
        self.note_text = tk.Text(left, width=32, height=6)
        self.note_text.insert("1.0", campi_proposti.get("note", ""))
        self.note_text.grid(row=len(campi_label), column=1, pady=4, padx=6)

        tk.Button(left, text="💾 Salva materia prima", bg="#33339A", fg="white",
                  command=self._salva).grid(row=len(campi_label) + 1, column=0, columnspan=2, pady=12, sticky="we")

        # --- colonna destra: testo completo estratto, per confronto ---
        right = tk.LabelFrame(body, text="Testo estratto dal PDF (per confronto)", padx=6, pady=6)
        right.pack(side="left", fill="both", expand=True)
        txt = tk.Text(right, wrap="word", font=("Consolas", 9))
        txt.insert("1.0", testo_estratto or "(nessun testo estratto dal PDF — potrebbe essere una scansione senza testo selezionabile)")
        txt.config(state="disabled")
        scroll = ttk.Scrollbar(right, command=txt.yview)
        txt.configure(yscrollcommand=scroll.set)
        txt.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def _salva(self):
        codice_lotto = self.vars["codice_lotto"].get().strip()
        if not codice_lotto:
            messagebox.showwarning("Campo mancante", "Il codice lotto e' obbligatorio (verificalo nel testo a destra).")
            return

        # copia il PDF nella cartella locale dei CoA, cosi' resta collegato al record
        cartella = local_db.cartella_coa()
        nome_file = f"{codice_lotto}_{os.path.basename(self.percorso_pdf)}".replace(" ", "_")
        destinazione = os.path.join(cartella, nome_file)
        try:
            shutil.copy2(self.percorso_pdf, destinazione)
        except Exception:
            destinazione = self.percorso_pdf  # se la copia fallisce, teniamo almeno il percorso originale

        local_db.aggiungi_materia_prima(
            fornitore=self.vars["fornitore"].get().strip(),
            codice_lotto=codice_lotto,
            materiale=self.vars["materiale"].get().strip(),
            mfi_dichiarato=self.vars["mfi_dichiarato"].get().strip(),
            carbon_black=self.vars["carbon_black"].get().strip(),
            umidita=self.vars["umidita"].get().strip(),
            densita=self.vars["densita"].get().strip(),
            volatili=self.vars["volatili"].get().strip(),
            dispersione=self.vars["dispersione"].get().strip(),
            oit=self.vars["oit"].get().strip(),
            note=self.note_text.get("1.0", "end").strip(),
            pdf_coa=destinazione,
        )
        messagebox.showinfo("Salvato", f"Materia prima '{codice_lotto}' salvata con il CoA collegato.")
        if self.on_conferma:
            self.on_conferma()
        self.destroy()


class FinestraMateriePrime(tk.Toplevel):
    """Gestione anagrafica materie prime (MP) locale: elenco, aggiunta, import CSV."""

    def __init__(self, master, on_scelta=None):
        super().__init__(master)
        self.on_scelta = on_scelta
        self.title("Materie prime (MP)")
        self.geometry("1150x480")

        top = tk.Frame(self)
        top.pack(fill="x", padx=8, pady=8)
        tk.Button(top, text="+ Nuova materia prima", command=self._nuova).pack(side="left")
        tk.Button(top, text="📄 Importa da CoA (PDF)", command=self._importa_da_coa).pack(side="left", padx=6)
        tk.Button(top, text="📥 Importa da CSV", command=self._importa_csv).pack(side="left")
        tk.Button(top, text="🔄 Aggiorna", command=self._ricarica).pack(side="left", padx=6)

        search_row = tk.Frame(self)
        search_row.pack(fill="x", padx=8)
        tk.Label(search_row, text="Filtro:").pack(side="left")
        self.var_filtro = tk.StringVar()
        e = tk.Entry(search_row, textvariable=self.var_filtro, width=40)
        e.pack(side="left", padx=6)
        e.bind("<KeyRelease>", lambda ev: self._ricarica())

        columns = ("id", "fornitore", "codice_lotto", "materiale", "mfi_dichiarato",
                   "carbon_black", "umidita", "densita", "volatili", "dispersione", "oit")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        larghezze = {"id": 40, "fornitore": 130, "codice_lotto": 120, "materiale": 150}
        for c in columns:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=larghezze.get(c, 80))
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        if self.on_scelta:
            self.tree.bind("<Double-1>", lambda ev: self._usa_selezionato())

        btnrow = tk.Frame(self)
        btnrow.pack(fill="x", padx=8, pady=(0, 8))
        if self.on_scelta:
            tk.Button(btnrow, text="Usa selezionato nel certificato", command=self._usa_selezionato).pack(side="right")
        tk.Button(btnrow, text="Elimina selezionato", fg="#b33", command=self._elimina).pack(side="right", padx=6)
        tk.Button(btnrow, text="📄 Apri CoA collegato", command=self._apri_coa).pack(side="left")

        self._righe = []
        self._ricarica()

    def _ricarica(self):
        self._righe = local_db.elenco_materie_prime(self.var_filtro.get())
        for i in self.tree.get_children():
            self.tree.delete(i)
        for r in self._righe:
            values = [r.get(c, "") for c in self.tree["columns"]]
            self.tree.insert("", "end", values=values)

    def _nuova(self):
        win = tk.Toplevel(self)
        win.title("Nuova materia prima")
        campi = ["fornitore", "codice_lotto", "materiale", "mfi_dichiarato",
                 "carbon_black", "umidita", "densita", "volatili", "dispersione", "oit", "note"]
        etichette = {
            "fornitore": "Fornitore", "codice_lotto": "Codice lotto", "materiale": "Materiale",
            "mfi_dichiarato": "MFI", "carbon_black": "Carbon Black", "umidita": "Umidità",
            "densita": "Densità", "volatili": "Volatili", "dispersione": "Dispersione",
            "oit": "OIT", "note": "Note",
        }
        vars_ = {}
        for i, c in enumerate(campi):
            tk.Label(win, text=etichette[c]).grid(row=i, column=0, sticky="w", padx=6, pady=4)
            v = tk.StringVar()
            tk.Entry(win, textvariable=v, width=40).grid(row=i, column=1, padx=6, pady=4)
            vars_[c] = v

        def salva():
            local_db.aggiungi_materia_prima(
                fornitore=vars_["fornitore"].get(), codice_lotto=vars_["codice_lotto"].get(),
                materiale=vars_["materiale"].get(), mfi_dichiarato=vars_["mfi_dichiarato"].get(),
                carbon_black=vars_["carbon_black"].get(), umidita=vars_["umidita"].get(),
                densita=vars_["densita"].get(), volatili=vars_["volatili"].get(),
                dispersione=vars_["dispersione"].get(), oit=vars_["oit"].get(),
                note=vars_["note"].get(),
            )
            win.destroy()
            self._ricarica()

        tk.Button(win, text="Salva", command=salva).grid(row=len(campi), column=0, columnspan=2, pady=8)

    def _importa_da_coa(self):
        percorso = filedialog.askopenfilename(
            title="Seleziona il CoA del fornitore (PDF)",
            filetypes=[("File PDF", "*.pdf")],
        )
        if not percorso:
            return
        try:
            candidati = coa_reader.estrai_candidati(percorso)
        except coa_reader.LetturaCoAError as exc:
            messagebox.showerror("Errore lettura PDF", str(exc))
            return

        if not candidati:
            messagebox.showwarning(
                "Nessun valore trovato",
                "Non ho trovato una tabella di valori di prova riconoscibile in questo PDF.\n"
                "Puoi comunque inserire la materia prima a mano con '+ Nuova materia prima'."
            )
            return

        if len(candidati) > 1:
            messagebox.showinfo(
                "Più lotti trovati",
                f"Questo PDF sembra contenere {len(candidati)} certificati/lotti diversi "
                f"(pagine {', '.join(str(c['pagina']) for c in candidati)}).\n\n"
                "Si aprirà una finestra di verifica per ciascuno, in sequenza."
            )

        self._coda_import_coa = list(candidati)
        self._percorso_coa_corrente = percorso
        self._apri_prossima_revisione_coa()

    def _apri_prossima_revisione_coa(self):
        if not getattr(self, "_coda_import_coa", None):
            return
        candidato = self._coda_import_coa.pop(0)
        RevisioneCoA(self, percorso_pdf=self._percorso_coa_corrente, campi_proposti=candidato,
                     testo_estratto=candidato.get("testo_pagina", ""),
                     numero_pagina=candidato.get("pagina"),
                     on_conferma=self._dopo_salvataggio_coa)

    def _dopo_salvataggio_coa(self):
        self._ricarica()
        if getattr(self, "_coda_import_coa", None):
            self._apri_prossima_revisione_coa()

    def _importa_csv(self):
        percorso = filedialog.askopenfilename(filetypes=[("File CSV", "*.csv")])
        if not percorso:
            return
        try:
            n = local_db.importa_materie_prime_da_csv(percorso)
        except Exception as exc:
            messagebox.showerror("Errore import", str(exc))
            return
        messagebox.showinfo("Import completato", f"Importate {n} righe.")
        self._ricarica()

    def _elimina(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        mp = self._righe[idx]
        if messagebox.askyesno("Conferma", f"Eliminare la materia prima '{mp.get('codice_lotto')}'?"):
            local_db.elimina_materia_prima(mp["id"])
            self._ricarica()

    def _usa_selezionato(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        self.on_scelta(self._righe[idx])
        self.destroy()

    def _apri_coa(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Nessuna selezione", "Seleziona prima una materia prima dall'elenco.")
            return
        idx = self.tree.index(sel[0])
        mp = self._righe[idx]
        percorso = mp.get("pdf_coa")
        if not percorso or not os.path.exists(percorso):
            messagebox.showinfo("Nessun CoA", "Questa materia prima non ha un PDF CoA collegato (e' stata inserita a mano).")
            return
        try:
            os.startfile(percorso)  # Windows
        except Exception as exc:
            messagebox.showerror("Errore", f"Impossibile aprire il file:\n{exc}")
