// Prázdný basePath = relativní volání (/api/...). V produkci to Caddy
// nasměruje na backend, ve vývoji si nastav proxy nebo plnou adresu.
const API_BASE = "/api";
const TOKEN_KEY = "greensie_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function logout() {
  localStorage.removeItem(TOKEN_KEY);
}

export async function login(email, heslo) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, heslo }),
  });
  if (!res.ok) {
    throw new Error("Nesprávný e-mail nebo heslo");
  }
  const data = await res.json();
  setToken(data.access_token);
}

export async function nactiMe() {
  const token = getToken();
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new Error("Nepodařilo se načíst uživatele");
  }
  return res.json();
}

export function zmenHeslo(nove_heslo) {
  return zavolej("/auth/heslo", { method: "PUT", body: JSON.stringify({ nove_heslo }) });
}

// ---- Matice (Přehled projektů) ----
async function zavolej(cesta, moznosti = {}) {
  const token = getToken();
  const res = await fetch(`${API_BASE}${cesta}`, {
    ...moznosti,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(moznosti.headers || {}),
    },
  });
  if (!res.ok) {
    let detail = `Chyba ${res.status}`;
    try {
      const chyba = await res.json();
      if (chyba.detail) detail = chyba.detail;
    } catch {
      // ponech výchozí hlášku
    }
    throw new Error(detail);
  }
  return res.json();
}

export function nactiMatici() {
  return zavolej("/matice");
}

export function ulozBunku(data) {
  return zavolej("/matice/bunka", { method: "PUT", body: JSON.stringify(data) });
}

export function pridejProjekt(data) {
  return zavolej("/matice/projekt", { method: "POST", body: JSON.stringify(data) });
}

export function pridejSloupec(data) {
  return zavolej("/matice/sloupec", { method: "POST", body: JSON.stringify(data) });
}

export function nacistZFreela(rezim) {
  return zavolej("/matice/freelo/nacist", { method: "POST", body: JSON.stringify({ rezim }) });
}

export function ulozBarvy(data) {
  return zavolej("/matice/barvy", { method: "PUT", body: JSON.stringify(data) });
}

export function nastavZobrazeniProjektu(id, skryty) {
  return zavolej(`/matice/projekt/${id}/zobrazeni`, {
    method: "PUT",
    body: JSON.stringify({ skryty }),
  });
}

// ---- Uživatelská nastavení (pohledy + vzhled, uložená v DB) ----
export function nactiNastaveni() {
  return zavolej("/nastaveni");
}

export function ulozNastaveni(klic, hodnota) {
  return zavolej(`/nastaveni/${klic}`, {
    method: "PUT",
    body: JSON.stringify({ hodnota }),
  });
}

// ---- Admin nastavení (správa uživatelů, skupin a práv) ----
export function adminCiselniky() {
  return zavolej("/admin/ciselniky");
}

export function adminUzivatele() {
  return zavolej("/admin/uzivatele");
}

export function adminPridejUzivatele(data) {
  return zavolej("/admin/uzivatele", { method: "POST", body: JSON.stringify(data) });
}

export function adminUpravUzivatele(id, data) {
  return zavolej(`/admin/uzivatele/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function adminSmazUzivatele(id) {
  return zavolej(`/admin/uzivatele/${id}`, { method: "DELETE" });
}

// nove_heslo = null → server vygeneruje náhodné; jinak nastaví zadané
export function adminResetHesla(id, nove_heslo) {
  return zavolej(`/admin/uzivatele/${id}/reset-hesla`, {
    method: "POST",
    body: JSON.stringify({ nove_heslo: nove_heslo || null }),
  });
}

export function adminSkupiny() {
  return zavolej("/admin/skupiny");
}

export function adminPridejSkupinu(data) {
  return zavolej("/admin/skupiny", { method: "POST", body: JSON.stringify(data) });
}

export function adminUpravSkupinu(id, data) {
  return zavolej(`/admin/skupiny/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function adminSmazSkupinu(id) {
  return zavolej(`/admin/skupiny/${id}`, { method: "DELETE" });
}
