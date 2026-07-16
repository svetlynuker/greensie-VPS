"""Společné nastavení pytest testů backendu.

Výpočetní moduly (`peak_shaving`, `ppa_fve`) i seed jsou bez závislosti na
běžící DB – testy je importují přímo z balíčku `app`. Kořen backendu se přidá
na sys.path a `DATABASE_URL` dostane neškodný fallback (app.database vytváří
engine při importu, ale bez dotazu se nikdy nepřipojí).
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DATABASE_URL", "sqlite://")
