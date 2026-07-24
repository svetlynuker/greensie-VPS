"""Manuál – interaktivní znalostní báze appky přímo v UI.

Čte Markdown soubory ze složky `docs/znalostni-baze/` (jeden zdroj pravdy –
tytéž soubory se čtou i na GitHubu) a servíruje je jako HTML pro dlaždici
Manuál a kontextovou nápovědu „?". Obsah je vlastní (repo), ne uživatelský
vstup, takže se ve frontendu vkládá přes dangerouslySetInnerHTML.

Manuál je dostupný všem přihlášeným – nevyžaduje žádné zvláštní právo.
"""

import html as _html
import re
from pathlib import Path

import markdown
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.models import User
from app.auth.permissions import get_current_user

router = APIRouter(prefix="/manual", tags=["manual"])

# .../backend/app/manual/routes.py → parents[3] = kořen repa (kde je docs/)
ZNALOSTNI_BAZE = Path(__file__).resolve().parents[3] / "docs" / "znalostni-baze"

# Pevné pořadí a kategorie stránek pro sidebar. `id` = kotva pro deep-link
# (?stranka=<id>) i pro mapování kontextové nápovědy z jednotlivých modulů.
STRANKY = [
    ("uvod", "README.md", "Úvod"),
    ("prehled-projektu", "moduly/prehled-projektu.md", "Moduly"),
    ("prehled-financi", "moduly/prehled-financi.md", "Moduly"),
    ("prehled-zmen", "moduly/prehled-zmen.md", "Moduly"),
    ("nabidkovac", "moduly/nabidkovac.md", "Moduly"),
    ("nabidkovac-peak-shaving", "moduly/nabidkovac-peak-shaving.md", "Moduly"),
    ("nabidkovac-ppa-fve", "moduly/nabidkovac-ppa-fve.md", "Moduly"),
    ("konektor-raynet-gdrive", "moduly/konektor-raynet-gdrive.md", "Moduly"),
    ("logy", "moduly/logy.md", "Moduly"),
    ("admin-nastaveni", "moduly/admin-nastaveni.md", "Moduly"),
    ("prihlaseni-zmena-hesla", "moduly/prihlaseni-zmena-hesla.md", "Moduly"),
    ("spolecne-prvky", "moduly/spolecne-prvky.md", "Moduly"),
    ("server-architektura", "server/architektura-prostredi.md", "Server a provoz"),
    ("server-nasazeni", "server/nasazeni.md", "Server a provoz"),
    ("server-konfigurace", "server/konfigurace.md", "Server a provoz"),
    ("server-prava", "server/prava-a-skupiny.md", "Server a provoz"),
]

_H1 = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_TAGY = re.compile(r"<[^>]+>")


class StrankaOut(BaseModel):
    id: str
    titulek: str
    kategorie: str
    html: str
    text: str  # čistý text pro fulltextové hledání ve frontendu


class ManualOut(BaseModel):
    stranky: list[StrankaOut]


def _titulek(md_text: str, fallback: str) -> str:
    m = _H1.search(md_text)
    return m.group(1).strip() if m else fallback


def _render(md_text: str) -> str:
    md = markdown.Markdown(
        extensions=["tables", "fenced_code", "sane_lists", "attr_list", "toc"],
        output_format="html5",
    )
    return md.convert(md_text)


def _plain(html_text: str) -> str:
    """HTML → čistý text (bez značek, s dekódovanými entitami) pro hledání."""
    return _html.unescape(_TAGY.sub(" ", html_text))


def _nacti_stranky() -> list[StrankaOut]:
    stranky: list[StrankaOut] = []
    for sid, rel, kategorie in STRANKY:
        cesta = ZNALOSTNI_BAZE / rel
        if not cesta.exists():
            continue
        md_text = cesta.read_text(encoding="utf-8")
        html_text = _render(md_text)
        stranky.append(
            StrankaOut(
                id=sid,
                titulek=_titulek(md_text, sid),
                kategorie=kategorie,
                html=html_text,
                text=_plain(html_text),
            )
        )
    return stranky


@router.get("", response_model=ManualOut)
def nacti_manual(user: User = Depends(get_current_user)):
    """Vrátí všechny stránky manuálu (HTML + text) najednou.

    Frontend si je nacachuje, staví z nich navigaci a hledá v `text`.
    """
    stranky = _nacti_stranky()
    if not stranky:
        raise HTTPException(
            status_code=500,
            detail="Zdroj manuálu (docs/znalostni-baze) nebyl nalezen.",
        )
    return ManualOut(stranky=stranky)
