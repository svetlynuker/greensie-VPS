import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Layout from "../components/Layout";
import { crmKontaktDetail, crmKontaktUpravZKarty, logout, nactiMe } from "../api";
import { fmtDatum, fmtDatumCas } from "../crm";
import "../styles/crm.css";

/**
 * Karta kontaktní osoby.
 *
 * Co tu SCHVÁLNĚ není: aktivity a úkoly. V datech visí na firmě nebo na
 * obchodním případu, ne na člověku, takže by karta jen opisovala kartu
 * zákazníka. Případy firmy jsou tu jako kontext („o čem s ním je řeč"),
 * e-mailová historie naopak patří přímo osobě – ta je navázaná na ni.
 */
export default function KontaktDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [me, setMe] = useState(null);
  const [k, setK] = useState(null);
  const [upravuje, setUpravuje] = useState(false);
  const [form, setForm] = useState(null);
  const [uklada, setUklada] = useState(false);
  const [chyba, setChyba] = useState(null);

  useEffect(() => {
    Promise.all([nactiMe(), crmKontaktDetail(id)])
      .then(([m, detail]) => {
        if (m.musi_zmenit_heslo) {
          navigate("/zmena-hesla");
          return;
        }
        if (!m.prava?.includes("zakaznici")) {
          navigate("/rozcestnik");
          return;
        }
        setMe(m);
        setK(detail);
      })
      .catch((e) => {
        const msg = String(e.message);
        if (msg.includes("přihlášení") || msg.includes("uživatel")) {
          logout();
          navigate("/");
        } else if (msg.includes("oprávnění")) {
          navigate("/rozcestnik");
        } else {
          setChyba(msg);
        }
      });
  }, [id, navigate]);

  function zacniUpravu() {
    setForm({
      jmeno: k.jmeno || "",
      funkce: k.funkce || "",
      email: k.email || "",
      telefon: k.telefon || "",
      hlavni: Boolean(k.hlavni),
      poznamka: k.poznamka || "",
    });
    setUpravuje(true);
    setChyba(null);
  }

  async function uloz() {
    if (!form.jmeno.trim()) return;
    setUklada(true);
    setChyba(null);
    try {
      setK(await crmKontaktUpravZKarty(id, form));
      setUpravuje(false);
    } catch (e) {
      setChyba(e.message);
    } finally {
      setUklada(false);
    }
  }

  if (chyba && !k) {
    return (
      <Layout uzivatel={me?.uzivatel}>
        <div style={{ padding: 24, color: "var(--st-crit)" }}>Chyba: {chyba}</div>
      </Layout>
    );
  }
  if (!me || !k) return null;

  return (
    <Layout uzivatel={me.uzivatel}>
      <div className="crm-app">
        <Link to="/kontakty" className="crm-zpet">
          ← Zpět na Kontaktní osoby
        </Link>

        <div className="crm-karta-hlava">
          <div style={{ minWidth: 0 }}>
            <h1>{k.jmeno}</h1>
            <div className="crm-karta-radek">
              {k.funkce || "bez funkce"}
              {" · "}
              <Link to={`/zakaznici/detail/${k.zakaznik_id}`} className="crm-odkaz">
                {k.zakaznik_nazev}
              </Link>
              {k.vlastnik_jmeno ? ` · vlastník firmy ${k.vlastnik_jmeno}` : ""}
            </div>
          </div>
          <span className="crm-mezera" />
          {k.hlavni && <span className="crm-znacka crm-barva-ok">hlavní kontakt</span>}
          <span
            className={`crm-znacka ${
              k.zakaznik_typ === "klient" ? "crm-barva-ok" : "crm-barva-info"
            }`}
          >
            {k.zakaznik_typ === "klient" ? "Klient" : "Lead"}
          </span>
          {k.muze_editovat && !upravuje && (
            <button className="fm-btn" onClick={zacniUpravu}>
              Upravit
            </button>
          )}
        </div>

        {chyba && <div className="crm-chyba">{chyba}</div>}

        <div className="crm-dva-sloupce">
          <div className="fm-card crm-blok">
            <h3>Údaje</h3>
            {upravuje ? (
              <>
                <div className="crm-mrizka">
                  <div>
                    <label className="crm-label">Jméno *</label>
                    <input
                      className="crm-pole"
                      value={form.jmeno}
                      onChange={(e) => setForm({ ...form, jmeno: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="crm-label">Funkce</label>
                    <input
                      className="crm-pole"
                      value={form.funkce}
                      onChange={(e) => setForm({ ...form, funkce: e.target.value })}
                      placeholder="jednatel, energetik…"
                    />
                  </div>
                  <div>
                    <label className="crm-label">Telefon</label>
                    <input
                      className="crm-pole"
                      value={form.telefon}
                      onChange={(e) => setForm({ ...form, telefon: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="crm-label">E-mail</label>
                    <input
                      className="crm-pole"
                      value={form.email}
                      onChange={(e) => setForm({ ...form, email: e.target.value })}
                    />
                  </div>
                </div>
                <label className="crm-label" style={{ marginTop: 8 }}>
                  Poznámka
                </label>
                <textarea
                  className="crm-pole"
                  rows={3}
                  value={form.poznamka}
                  onChange={(e) => setForm({ ...form, poznamka: e.target.value })}
                />
                <label className="crm-zaskrtavaci">
                  <input
                    type="checkbox"
                    checked={form.hlavni}
                    onChange={(e) => setForm({ ...form, hlavni: e.target.checked })}
                  />
                  Hlavní kontakt firmy
                </label>
                <div className="crm-blok-pata">
                  <button className="fm-btn" onClick={() => setUpravuje(false)} disabled={uklada}>
                    Zrušit
                  </button>
                  <span className="crm-mezera" />
                  <button
                    className="fm-btn fm-primary"
                    onClick={uloz}
                    disabled={uklada || !form.jmeno.trim()}
                  >
                    {uklada ? "Ukládám…" : "Uložit"}
                  </button>
                </div>
              </>
            ) : (
              <>
                <dl className="crm-udaje">
                  <dt>Jméno</dt>
                  <dd>{k.jmeno}</dd>
                  <dt>Funkce</dt>
                  <dd>{k.funkce || "—"}</dd>
                  <dt>Telefon</dt>
                  <dd>{k.telefon ? <a href={`tel:${k.telefon}`}>{k.telefon}</a> : "—"}</dd>
                  <dt>E-mail</dt>
                  <dd>{k.email ? <a href={`mailto:${k.email}`}>{k.email}</a> : "—"}</dd>
                  <dt>Vytvořeno</dt>
                  <dd>{fmtDatum(k.vytvoreno_at) || "—"}</dd>
                </dl>
                {k.poznamka && <p className="crm-poznamka">{k.poznamka}</p>}
              </>
            )}
          </div>

          <div className="crm-sloupec-bloky">
            <div className="fm-card crm-blok">
              <h3>Firma</h3>
              <dl className="crm-udaje">
                <dt>Název</dt>
                <dd>
                  <Link to={`/zakaznici/detail/${k.zakaznik_id}`} className="crm-odkaz">
                    {k.zakaznik_nazev}
                  </Link>
                </dd>
                <dt>Město</dt>
                <dd>{k.zakaznik_mesto || "—"}</dd>
                <dt>Telefon firmy</dt>
                <dd>{k.zakaznik_telefon || "—"}</dd>
                <dt>E-mail firmy</dt>
                <dd>{k.zakaznik_email || "—"}</dd>
              </dl>
            </div>

            <div className="fm-card crm-blok">
              <h3>Obchodní případy firmy</h3>
              {k.pripady.length === 0 ? (
                <p className="crm-tise">U firmy zatím není žádný obchodní případ.</p>
              ) : (
                <ul className="crm-kontakty">
                  {k.pripady.map((p) => (
                    <li key={p.id}>
                      <div style={{ minWidth: 0 }}>
                        <div className="crm-kontakt-jmeno">
                          <Link to={`/pripady/detail/${p.id}`} className="crm-odkaz">
                            {p.cislo || `případ #${p.id}`}
                          </Link>
                        </div>
                        <div className="crm-tise">
                          {[p.nazev, p.stav].filter(Boolean).join(" · ") || "—"}
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="fm-card crm-blok">
              <h3>E-mailová komunikace</h3>
              {k.emaily.length === 0 ? (
                <p className="crm-tise">
                  S touhle osobou zatím v appce neproběhla žádná e-mailová komunikace. Napojuje se
                  automaticky podle adresy — tedy jen když ji má osoba vyplněnou.
                </p>
              ) : (
                <ul className="crm-kontakty">
                  {k.emaily.map((e) => (
                    <li key={e.zprava_id}>
                      <div style={{ minWidth: 0 }}>
                        <div className="crm-kontakt-jmeno">{e.predmet}</div>
                        <div className="crm-tise">
                          {e.smer === "odchozi" ? "odesláno" : "přijato"}
                          {e.kdy ? ` · ${fmtDatumCas(e.kdy)}` : ""}
                          {e.od_adresa ? ` · ${e.od_adresa}` : ""}
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}
