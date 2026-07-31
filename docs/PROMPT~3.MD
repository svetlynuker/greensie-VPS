# Prompt pro Claude Code – doplnění závislostí do deploy/update.sh

## Kontext / problém

Při implementaci peak shaving (PR #6, import XLS profilu) přibyly nové Python
balíčky (`xlrd`, `openpyxl`) do `requirements.txt`. `deploy/update.sh` ale
nedělá `pip install`, takže se musely doinstalovat ručně přímo do venv na
serveru, aby backend po `git pull` + restartu nespadl na `ImportError`.

Stejné riziko hrozí u frontendu, pokud nějaký PR přidá nový npm balíček (ověř,
jestli `update.sh` aktuálně dělá `npm install` před `npm run build`, nebo jen
`npm run build`).

## Úkol

1. Otevři `deploy/update.sh` a zjisti aktuální kroky.
2. Doplň do skriptu:
   - Aktivaci venv backendu a `pip install -r requirements.txt` (do stejného
     venv, který používá `greensie-backend` systemd služba) – před restartem
     backendu.
   - Pokud tam `npm install` chybí, doplň ho před `npm run build` (frontend).
3. Ověř, že skript zůstává idempotentní a bezpečný i při opakovaném spuštění
   (instalace balíčků, které už jsou nainstalované, nesmí nic rozbít).
4. Přidej krátký komentář do skriptu, proč tam tyhle kroky jsou (ať to příště
   někdo nesmaže jako "zbytečné").
5. Otestuj reálným spuštěním `sudo bash deploy/update.sh` na serveru a potvrď,
   že proběhne bez chyb a appka po něm normálně běží (backend i frontend).

## Co NEDĚLAT

- Neměň nic na CI/CD mimo tenhle skript – appka je zatím bez CI, nasazuje se
  ručně, to zůstává.
- Nezaváděj Docker ani jiný způsob nasazení – jen doplň chybějící instalační
  kroky do stávajícího `update.sh`.
