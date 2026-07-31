"""Jednorázově přesune do koše sirotčí duplicitní složku klienta na Disku.

Sirotek „Karel Boxan [252]" (1nhyAlc09tLRFxcf4sgDgajttwVOMVNBm) – nedokončená
kopie vzoru (chybí „1. Obchodní Případy"), není v mapování, 0 souborů.
Přesun do KOŠE je vratný. Po doběhnutí smaž tento soubor.
"""
from app.database import SessionLocal
from app.konektor import crypto
from app.konektor.google_klient import DriveClient
from app.konektor.models import KonektorNastaveni

SIROTEK = "1nhyAlc09tLRFxcf4sgDgajttwVOMVNBm"

db = SessionLocal()
try:
    n = db.get(KonektorNastaveni, 1)
    sa = crypto.desifruj(n.google_sa_json_enc)
    drive = DriveClient(sa, n.google_subject_email or None)

    meta = drive.get_file(SIROTEK)
    print(f"Přesouvám do koše: „{meta.get('name')}“  ({SIROTEK})")
    drive.service.files().update(
        fileId=SIROTEK, body={"trashed": True}, supportsAllDrives=True
    ).execute(num_retries=5)
    print("Hotovo – složka je v koši Google Disku (lze obnovit).")
finally:
    db.close()
