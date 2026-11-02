"""
Elenca i driver ODBC installati sul PC, per capire quale nome usare
in ARCA_DRIVER nel file .env.

Uso:
    python list_odbc_drivers.py
"""

import pyodbc

driver_sql_server = [d for d in pyodbc.drivers() if "SQL Server" in d]

print("Tutti i driver ODBC installati sul PC:\n")
for d in pyodbc.drivers():
    print(f"  {d}")

print("\n--- Driver SQL Server trovati ---")
if driver_sql_server:
    for d in driver_sql_server:
        print(f"  {d}")
    print(f"\nUsa questo in .env (con le graffe):")
    print(f"  ARCA_DRIVER={{{driver_sql_server[-1]}}}")
else:
    print("  Nessun driver SQL Server trovato.")
    print("\n  Devi installare il 'Microsoft ODBC Driver for SQL Server'.")
    print("  Scaricabile da: https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server")
    print("  In alternativa, se Arca stesso usa un driver OLE DB o un altro")
    print("  client SQL già installato, potrebbe già esserci un driver 'SQL")
    print("  Server' generico (quello nativo di Windows) tra quelli elencati")
    print("  sopra: puoi provare con quello, es. ARCA_DRIVER={SQL Server}")
