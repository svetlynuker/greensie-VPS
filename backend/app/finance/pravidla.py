"""Fakturační pravidla z Freela – KAM SE DOPLŇUJE LOGIKA.

Zadání říká, že přesná pravidla "kdy se má co fakturovat" (např. "po podpisu
SOD/SOP se vystavuje Faktura 1") zatím nejsou plně nadefinovaná a budou se
ladit iterativně. Aby se to dalo dopisovat bez zásahu do zbytku appky, žije
veškerá tahle logika JEN v tomhle souboru.

Zatím je záměrně prázdná: appka funguje s ručním nastavováním stavů. Až budou
pravidla známá, doplní se do `navrhni_stavy` – nic jiného se měnit nemusí.
"""

from app.finance.models import Faktura


def navrhni_stavy(projekt, faktury: list[Faktura], freelo_ukoly: list[dict]) -> None:
    """Podle stavu úkolů/fází ve Freelu navrhne stavy faktur projektu.

    Vstup:
      - projekt: řádek projektu (app.matice.models.Projekt)
      - faktury: faktury toho projektu (mění se in-place)
      - freelo_ukoly: úkoly projektu z Freela (viz matice.freelo.nacti_ukoly)

    Ruční úpravy mají přednost: fakturu s `upraveno_rucne=True` NIKDY nepřepisuj.

    Zatím no-op. Příklad budoucího pravidla:

        for f in faktury:
            if f.upraveno_rucne:
                continue
            if f.poradi == 1 and _faze_hotova(freelo_ukoly, "SOD"):
                f.stav = "vystaveno"
    """
    return None
