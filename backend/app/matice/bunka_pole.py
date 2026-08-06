"""Ukládání buňky matice po jednotlivých polích („porovnej a zapiš“).

Proč po polích a ne celá buňka: dosavadní `PUT /matice/bunka` posílal stav,
termín, osobu i poznámku pohromadě. Když dva lidé měli otevřenou tutéž buňku,
druhý uložil i tři pole, kterých se ani nedotkl, a tím přepsal práci prvního —
tiše, bez jakékoli hlášky. Automatické ukládání by tuhle past jen zrychlilo,
proto se pole ukládají zvlášť.

Druhá pojistka je `puvodni`: prohlížeč posílá hodnotu, kterou zobrazoval, než
člověk začal psát. Když se od té doby v DB změnila, ukládání se zastaví
a vyhodí `Konflikt` — člověk pak vidí, kdo a co změnil, a rozhodne sám.
Verze záznamu se hlídat nemůže, protože roste i při změně JINÉHO pole; pak by
se lidem hlásila kolize u věcí, které si vzájemně nevadí.
"""

from datetime import date, datetime

from app.matice.razitko import oznac_zmenu

# Pole buňky, která smí měnit člověk. `url` a `freelo_task_id` sem nepatří —
# to jsou metadata z Freela, ne vstup uživatele.
POLE = ("stav", "termin", "osoba", "poznamka")

STAVY = ("", "done", "todo")


class Konflikt(Exception):
    """Pole mezitím změnil někdo jiný — nepřepisujeme, ptáme se."""

    def __init__(self, *, pole: str, aktualni: str, zmenil_id: int | None, zmeneno_at):
        super().__init__(f"Pole {pole} mezitím změnil někdo jiný")
        self.pole = pole
        self.aktualni = aktualni
        self.zmenil_id = zmenil_id
        self.zmeneno_at = zmeneno_at


def parse_datum(s):
    """„YYYY-MM-DD“ → date. Prázdné = None. Neplatné vyhodí ValueError."""
    if not s:
        return None
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


def datum_text(d):
    return d.isoformat() if isinstance(d, date) else None


def hodnota_textem(bunka, pole: str) -> str:
    """Hodnota pole tak, jak ji vidí prohlížeč — nevyplněno je prázdný text.

    Sjednocení na text je tu proto, aby se dalo porovnat s tím, co přišlo
    z formuláře. Tam je „nevyplněno“ vždycky prázdný string, nikdy None.
    """
    if pole not in POLE:
        raise ValueError(f"Neznámé pole buňky: {pole}")
    if pole == "termin":
        return datum_text(bunka.termin) or ""
    return getattr(bunka, pole) or ""


def zkontroluj_kolizi(bunka, *, pole: str, puvodni: str | None) -> None:
    """Ověří, že v DB je pořád to, co prohlížeč zobrazoval.

    `puvodni=None` znamená „ukládej bez kontroly“ — použije se, až člověk
    v hlášce o kolizi potvrdí, že chce přepsat.
    """
    if puvodni is None:
        return
    aktualni = hodnota_textem(bunka, pole)
    if aktualni != puvodni:
        raise Konflikt(
            pole=pole,
            aktualni=aktualni,
            zmenil_id=getattr(bunka, "zmenil_id", None),
            zmeneno_at=getattr(bunka, "zmeneno_at", None),
        )


def zapis_pole(bunka, *, pole: str, hodnota: str | None, uzivatel_id: int | None) -> None:
    """Zapíše jedno pole buňky. Necommituje — to dělá endpoint.

    Neplatná hodnota vyhodí ValueError (endpoint z ní udělá 422). Rozepsaný
    stav se ale za neplatný NEPOVAŽUJE: prázdné pole je legitimní hodnota,
    protože při automatickém ukládání se v DB nutně objevují i nedokončené
    záznamy.
    """
    hodnota = hodnota if hodnota is not None else ""

    if pole == "stav":
        if hodnota not in STAVY:
            raise ValueError(f"Neplatný stav: {hodnota}")
        bunka.stav = hodnota or None
    elif pole == "termin":
        try:
            bunka.termin = parse_datum(hodnota)
        except ValueError:
            raise ValueError(f"Neplatné datum: {hodnota}")
    elif pole == "osoba":
        bunka.osoba = hodnota
    elif pole == "poznamka":
        bunka.poznamka = hodnota
    else:
        raise ValueError(f"Neznámé pole buňky: {pole}")

    bunka.upraveno_rucne = True
    oznac_zmenu(bunka, uzivatel_id)
