"""Klient Freelo API v1.

Čtení projektů a úkolů + zápis STAVU úkolu (dokončit / znovu aktivovat).
Zápis se používá pro obousměrnou synchronizaci stavu: když se stav změní
v tabulce, appka ho promítne i do Freela. Ostatní pole appka do Freela nezapisuje.

Ověření: HTTP Basic (e-mail + API klíč) + povinná hlavička User-Agent.
Proměnné z .env: FREELO_EMAIL, FREELO_API_KEY.
"""

import os

import requests

BASE = "https://api.freelo.io/v1"
USER_AGENT = "Greensie app (daniel.lupinek@greensie.cz)"
TIMEOUT = 30


def _auth():
    email = os.environ["FREELO_EMAIL"]
    key = os.environ["FREELO_API_KEY"]
    return (email, key)


def _get(path, params=None):
    resp = requests.get(
        f"{BASE}/{path}",
        auth=_auth(),
        headers={"User-Agent": USER_AGENT},
        params=params,
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and "error" in data:
        raise RuntimeError(f"Freelo API chyba: {data['error']}")
    return data


def _post(path):
    """POST bez těla (finish/activate). Vrátí případné JSON, jinak None."""
    resp = requests.post(
        f"{BASE}/{path}",
        auth=_auth(),
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    try:
        data = resp.json()
    except ValueError:
        return None
    if isinstance(data, dict) and "error" in data:
        raise RuntimeError(f"Freelo API chyba: {data['error']}")
    return data


def dokonci_ukol(task_id):
    """Označí úkol ve Freelu jako dokončený (POST /task/{id}/finish)."""
    _post(f"task/{task_id}/finish")


def aktivuj_ukol(task_id):
    """Znovu aktivuje (rozpracuje) úkol ve Freelu (POST /task/{id}/activate)."""
    _post(f"task/{task_id}/activate")


def nacti_aktivni_projekty():
    """Vrátí aktivní projekty: [{freelo_id, nazev, url}]."""
    projekty = []
    page = 0
    while True:
        d = _get("all-projects", {"page": page})
        davka = (d.get("data") or {}).get("projects", [])
        if not davka:
            break
        for p in davka:
            stav = (p.get("state") or {}).get("state")
            if stav != "active":
                continue
            projekty.append(
                {
                    "freelo_id": p["id"],
                    "nazev": p["name"],
                    "url": f"https://app.freelo.io/project/{p['id']}",
                }
            )
        if len(davka) < d.get("per_page", len(davka)) or d.get("count", 0) >= d.get("total", 0):
            break
        page += 1
    return projekty


def _den(datum_cas):
    if not datum_cas:
        return None
    return str(datum_cas)[:10]  # "2026-03-18 00:00:00" -> "2026-03-18"


def nacti_ukoly(projekt_freelo_ids):
    """Vrátí úkoly aktivních projektů namapované na naši matici.

    [{projekt_freelo_id, faze, ukol_nazev, label, stav, termin, osoba, url, freelo_task_id}]
    """
    if not projekt_freelo_ids:
        return []

    ukoly = []
    page = 0
    while True:
        params = [("page", page)]
        params += [("projects_ids[]", pid) for pid in projekt_freelo_ids]
        d = _get("all-tasks", params=params)
        davka = (d.get("data") or {}).get("tasks", [])
        if not davka:
            break
        for t in davka:
            tasklist = t.get("tasklist") or {}
            faze = tasklist.get("name") or ""
            nazev = t.get("name") or ""
            label = f"{faze} - {nazev}" if faze else nazev
            stav = "done" if (t.get("state") or {}).get("state") == "finished" else "todo"
            worker = t.get("worker") or {}
            projekt = t.get("project") or {}
            ukoly.append(
                {
                    "projekt_freelo_id": projekt.get("id"),
                    "faze": faze,
                    "ukol_nazev": nazev,
                    "label": label,
                    "stav": stav,
                    "termin": _den(t.get("due_date")),
                    "osoba": worker.get("name") or "",
                    "url": f"https://app.freelo.io/task/{t['id']}",
                    "freelo_task_id": t["id"],
                }
            )
        total = d.get("total", 0)
        per_page = d.get("per_page") or len(davka)
        if (page + 1) * per_page >= total or len(davka) < per_page:
            break
        page += 1
    return ukoly
