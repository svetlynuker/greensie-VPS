const API_BASE = "http://localhost:8000";
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
