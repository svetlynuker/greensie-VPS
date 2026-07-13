# Úkol: Kostra appky Greensie

V souboru docs/SPEC.md máš kompletní specifikaci firemní appky Greensie.
Prosím přečti si ho celý, než začneš cokoli dělat. V docs/ najdeš i soubor
"prehled projektu.txt" - existující funkční prototyp, ze kterého appka
vychází vizuálně a funkčně, podívej se i na něj.

V tomto kroku chci implementovat POUZE bod 1 z kapitoly 7 (Priorita
implementace) - tedy kostru appky:

- Landing page s přihlášením (JWT tokeny, hesla hashovaná)
- Rozcestník po přihlášení s dlaždicemi (česky pojmenované, ne "dashboard")
- Systém rolí: admin / zaměstnanec / vedení
- Dlaždice se zobrazují jen podle práv uživatele - pokud uživatel právo
  nemá, dlaždice se úplně skryje (ne zašedne)
- Zatím vytvoř 3 prázdné dlaždice/sekce podle kapitoly 2: "Přehled
  projektů", "Přehled financí", "Přehled změn" - ať jen po kliknutí
  zobrazí placeholder "Připravujeme", žádnou funkčnost zatím neimplementuj

NEIMPLEMENTUJ zatím Pohled 1, 2 ani 3 - to přijde v dalších krocích.

## Technické detaily

Backend: Python 3.11 + FastAPI, databáze PostgreSQL. Přihlašovací údaje
k databázi a API klíč k Freelu jsou v souboru .env (je v .gitignore,
do gitu nepůjde) - přečti si ho, ať víš, jaké proměnné máš k dispozici,
ale nikdy jeho obsah nikam nevypisuj ani needituj přímo.

Frontend: React.

Struktura složek, kterou chci dodržet:

```
backend/app/ - main.py, database.py, auth/ (models.py, routes.py, permissions.py)
frontend/src/ - pages/ (Login.jsx, Rozcestnik.jsx), components/ (Tile.jsx, Layout.jsx), App.jsx
```

## Postup

Nejdřív mi ukaž plán souborů, které vytvoříš, a POČKEJ na mé potvrzení,
než začneš cokoliv vytvářet. Po dokončení mi vysvětli krok za krokem,
jak appku poprvé nainstalovat a spustit (jsem programátorský začátečník,
vysvětli mi to podrobně).
