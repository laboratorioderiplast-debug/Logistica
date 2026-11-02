"""
Finestra principale: elenco dei certificati salvati, con pulsanti per
crearne uno nuovo, aprire/duplicare/eliminare, e verificare la
connessione ad Arca.
"""
import copy
import tkinter as tk
from tkinter import ttk, messagebox

from . import local_db
from . import arca_connector
from .config import get_config
from .modelli_certificato import certificato_vuoto, certificato_esempio
from .ui_editor import EditorCertificato, FinestraMateriePrime


class FinestraPrincipale(tk.Tk):
    def __init__(self):
        super().__init__()
        local_db.init_db()

        cfg = get_config()
        self.title("Certificati EN 10204 MOD. 3.1 — Deriplast Group")
        self.geometry("900x560")

        bar = tk.Frame(self, bg="#33339A")
        bar.pack(side="top", fill="x")
        tk.Label(bar, text="Certificati EN 10204 MOD. 3.1", bg="#33339A", fg="white",
                  font=("Segoe UI", 12, "bold")).pack(side="left", padx=12, pady=10)

        def btn(text, cmd):
            b = tk.Button(bar, text=text, command=cmd, bg="white", fg="#33339A",
                          font=("Segoe UI", 9, "bold"), relief="flat", padx=8, pady=4)
            b.pack(side="left", padx=4, pady=8)
            return b

        btn("➕ Nuovo certificato", self.nuovo_certificato)
        btn("📋 Nuovo da esempio", self.nuovo_da_esempio)
        btn("📂 Apri", self.apri_selezionato)
        btn("🗐 Duplica", self.duplica_selezionato)
        btn("🗑 Elimina", self.elimina_selezionato)
        btn("🧪 Materie prime", self.materie_prime)
        btn("🔌 Test connessione Arca", self.test_connessione)

        status = "Modalita' DEMO (dati Arca finti)" if cfg.modalita_demo else f"Arca: {cfg.server} / {cfg.database}"
        tk.Label(self, text=status, anchor="w", fg="#555",
                  font=("Segoe UI", 8, "italic")).pack(side="top", fill="x", padx=10, pady=(4, 0))

        columns = ("id", "nome", "aggiornato_il")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        self.tree.heading("id", text="ID")
        self.tree.heading("nome", text="Nome certificato")
        self.tree.heading("aggiornato_il", text="Ultima modifica")
        self.tree.column("id", width=60, anchor="center")
        self.tree.column("nome", width=460)
        self.tree.column("aggiornato_il", width=200)
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        self.tree.bind("<Double-1>", lambda e: self.apri_selezionato())

        self._ricarica_elenco()

    def _ricarica_elenco(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        self._elenco = local_db.elenco_certificati()
        for c in self._elenco:
            self.tree.insert("", "end", values=(c["id"], c["nome"], c["aggiornato_il"]))

    def _selezionato(self):
        sel = self.tree.selection()
        if not sel:
            return None
        idx = self.tree.index(sel[0])
        return self._elenco[idx]

    def nuovo_certificato(self):
        editor = EditorCertificato(self, dati=certificato_vuoto(), nome_bozza="Nuovo certificato")
        self.wait_window(editor)
        self._ricarica_elenco()

    def nuovo_da_esempio(self):
        editor = EditorCertificato(self, dati=certificato_esempio(), nome_bozza="Nuovo (da esempio)")
        self.wait_window(editor)
        self._ricarica_elenco()

    def apri_selezionato(self):
        row = self._selezionato()
        if not row:
            messagebox.showinfo("Nessuna selezione", "Seleziona prima un certificato dall'elenco.")
            return
        record = local_db.carica_certificato(row["id"])
        editor = EditorCertificato(self, dati=record["dati"], id_certificato=record["id"], nome_bozza=record["nome"])
        self.wait_window(editor)
        self._ricarica_elenco()

    def duplica_selezionato(self):
        row = self._selezionato()
        if not row:
            messagebox.showinfo("Nessuna selezione", "Seleziona prima un certificato dall'elenco.")
            return
        record = local_db.carica_certificato(row["id"])
        nuovo_nome = record["nome"] + " (copia)"
        nuovo_id = local_db.salva_certificato(nuovo_nome, copy.deepcopy(record["dati"]))
        self._ricarica_elenco()
        messagebox.showinfo("Duplicato", f"Creata la copia: {nuovo_nome}")

    def elimina_selezionato(self):
        row = self._selezionato()
        if not row:
            messagebox.showinfo("Nessuna selezione", "Seleziona prima un certificato dall'elenco.")
            return
        if messagebox.askyesno("Conferma", f"Eliminare definitivamente '{row['nome']}'?"):
            local_db.elimina_certificato(row["id"])
            self._ricarica_elenco()

    def materie_prime(self):
        FinestraMateriePrime(self)

    def test_connessione(self):
        ok, msg = arca_connector.test_connection()
        if ok:
            messagebox.showinfo("Connessione Arca", msg)
        else:
            messagebox.showerror("Connessione Arca", msg)
