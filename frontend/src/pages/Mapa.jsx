import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import L from "leaflet";
import Layout from "../components/Layout";
import KpiPas from "../components/KpiPas";
import { crmMapa, logout, nactiMe } from "../api";
import "leaflet/dist/leaflet.css";
import "../styles/crm.css";

/**
 * Mapa zákazníků a projektů (CRM-20).
 *
 * Odpovídá na otázku „co máme v okolí, když už tam jedeme" — proto je na bodu
 * vidět, kolik u firmy běží případů a projektů, ne jen její jméno.
 *
 * ---- Odkud jsou souřadnice ----
 * Přednost má **provozovna** (odběrné místo), ne adresa firmy: FVE se staví na
 * provozovně, zatímco sídlo v rejstříku bývá fakturační. U každého bodu je
 * napsané, odkud se souřadnice vzaly, aby se podle mapy neplánovala cesta na
 * špatné místo.
 *
 * ---- Proč Leaflet a OpenStreetMap ----
 * Bez API klíče a bez účtu u poskytovatele map. Dlaždice se tahají z veřejných
 * serverů OSM přímo v prohlížeči uživatele; při osmi lidech je to hluboko pod
 * hranicí jejich pravidel používání.
 */

// Výchozí pohled: střed Česka tak, aby se do okna vešla celá republika.
const STRED_CR = [49.75, 15.5];
const ZOOM_CR = 7;

// Leaflet hledá obrázky špendlíků relativně k CSS, což se po sestavení rozbije.
// Vlastní ikona z inline SVG to řeší bez tahání souborů — a rovnou odliší
// klienta od leada barvou.
function ikona(barva) {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="26" height="34" viewBox="0 0 26 34">
      <path d="M13 0C5.8 0 0 5.8 0 13c0 9.7 13 21 13 21s13-11.3 13-21C26 5.8 20.2 0 13 0z" fill="${barva}"/>
      <circle cx="13" cy="13" r="5" fill="#fff"/>
    </svg>`;
  return L.icon({
    iconUrl: `data:image/svg+xml;base64,${btoa(unescape(encodeURIComponent(svg)))}`,
    iconSize: [26, 34],
    iconAnchor: [13, 34],
    popupAnchor: [0, -30],
  });
}

const IKONA_KLIENT = ikona("#2f855a");
const IKONA_LEAD = ikona("#b7791f");

export default function Mapa() {
  const navigate = useNavigate();
  const [me, setMe] = useState(null);
  const [body, setBody] = useState([]);
  const [chyba, setChyba] = useState(null);
  const [jenSPripady, setJenSPripady] = useState(false);

  useEffect(() => {
    nactiMe()
      .then(async (m) => {
        if (m.musi_zmenit_heslo) {
          navigate("/zmena-hesla");
          return;
        }
        if (!m.prava?.includes("zakaznici")) {
          navigate("/rozcestnik");
          return;
        }
        setMe(m);
        setBody(await crmMapa());
      })
      .catch((e) => {
        const msg = String(e.message);
        if (msg.includes("přihlášení") || msg.includes("uživatel")) {
          logout();
          navigate("/");
        } else {
          setChyba(msg);
        }
      });
  }, [navigate]);

  const videt = useMemo(
    () => (jenSPripady ? body.filter((b) => b.otevrenych_pripadu > 0) : body),
    [body, jenSPripady]
  );

  const kpi = useMemo(
    () => ({
      pocet: videt.length,
      pripadu: videt.reduce((a, b) => a + b.otevrenych_pripadu, 0),
      projektu: videt.reduce((a, b) => a + b.projektu, 0),
    }),
    [videt]
  );

  if (!me) return null;

  return (
    <Layout uzivatel={me.uzivatel}>
      <div className="crm-app siroky">
        <div className="crm-hlava">
          <div>
            <h1>Mapa</h1>
            <p className="crm-popis">
              Zákazníci se souřadnicemi. Špendlík sedí na <b>provozovně</b>, a když ji firma
              nemá vyplněnou, na adrese firmy — u každého bodu je napsáno, co platí.
            </p>
          </div>
          <span className="crm-mezera" />
          <label className="crm-zaskrtavaci">
            <input
              type="checkbox"
              checked={jenSPripady}
              onChange={(e) => setJenSPripady(e.target.checked)}
            />
            Jen s otevřeným případem
          </label>
        </div>

        {chyba && <div className="crm-chyba">{chyba}</div>}

        <KpiPas
          zobrazit={kpi.pocet > 0}
          filtrovano={jenSPripady}
          polozky={[
            { klic: "pocet", hodnota: kpi.pocet, label: "firem na mapě" },
            { klic: "pripady", hodnota: kpi.pripadu, label: "otevřených případů" },
            { klic: "projekty", hodnota: kpi.projektu, label: "projektů" },
          ]}
        />

        {body.length === 0 && !chyba ? (
          <div className="fm-card crm-blok">
            <p className="crm-tise">
              Zatím není co ukázat — žádná firma nemá vyplněné souřadnice. GPS se doplní
              u odběrného místa na kartě zákazníka, nebo se natáhne z ARESu při zakládání.
            </p>
          </div>
        ) : (
          <div className="crm-mapa">
            <MapContainer center={STRED_CR} zoom={ZOOM_CR} scrollWheelZoom style={{ height: "100%" }}>
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              {videt.map((b) => (
                <Marker
                  key={b.zakaznik_id}
                  position={[b.lat, b.lng]}
                  icon={b.typ === "klient" ? IKONA_KLIENT : IKONA_LEAD}
                >
                  <Popup>
                    <b>{b.nazev}</b>
                    <br />
                    {b.misto_nazev ? `${b.misto_nazev} · ` : ""}
                    {b.mesto}
                    <br />
                    <span className="crm-tise">souřadnice: {b.zdroj}</span>
                    <br />
                    {b.otevrenych_pripadu > 0 && <>{b.otevrenych_pripadu}× otevřený případ<br /></>}
                    {b.projektu > 0 && <>{b.projektu}× projekt<br /></>}
                    <button
                      className="fm-btn crm-btn-maly"
                      style={{ marginTop: 6 }}
                      onClick={() => navigate(`/zakaznici/detail/${b.zakaznik_id}`)}
                    >
                      Otevřít kartu →
                    </button>
                  </Popup>
                </Marker>
              ))}
            </MapContainer>
          </div>
        )}
      </div>
    </Layout>
  );
}
