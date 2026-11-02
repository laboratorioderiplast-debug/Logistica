"""
Punto di ingresso dell'applicazione "Certificati EN 10204 MOD. 3.1".

Avvio:
    python main.py

Per creare l'eseguibile Windows (.exe), vedi README_BUILD.md.
"""
import sys
import traceback
import tkinter as tk
from tkinter import messagebox


def main():
    from app.ui_main import FinestraPrincipale
    app = FinestraPrincipale()
    app.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Evita che l'app sparisca senza spiegazioni se lanciata come .exe
        err = traceback.format_exc()
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Errore imprevisto", err)
        except Exception:
            print(err, file=sys.stderr)
        sys.exit(1)
