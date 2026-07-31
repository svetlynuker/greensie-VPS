// Papír: pevné A4 stránky s volně umístěnými prvky.
//
// Jedna komponenta slouží editoru i tisku. Bez `editor` je z ní čistý
// renderer (náhled a PDF), s ním přibudou rámečky, úchyty a tažení. Díky tomu
// nemůže náhled lhát o výsledku – kreslí ho tentýž kód.

import { Fragment, useEffect, useLayoutEffect, useRef } from "react";

import Logo from "../Logo";
import PrvekObsah from "./PrvekObsah";
import TextPole from "./TextPole";
import { fmtDatum } from "../../nabidkovac";
import {
  A4_SIRKA,
  A4_VYSKA,
  OBSAH_DO,
  OBSAH_OD,
  OKRAJ_BOK,
  pretekaDolu,
} from "../../vystup/model";
import { UCHOPY } from "../../vystup/tazeni";

// Kontakt do zápatí – z hlavičkového papíru (varianta Bedřichovská); e-mail je
// oproti papíru novější, nabídky mají chodit na info@.
const FIRMA = {
  nazev: "GREENSIE",
  ulice: "Bedřichovská 2183/16",
  mesto: "182 00 Praha 8 – Libeň",
  telefon: "+420 222 703 031",
  email: "info@greensie.cz",
};

const mm = (v) => `${v}mm`;

/** Pás se značkou nahoře – opakuje se na každé stránce. */
function Pas({ zakaznik, pas }) {
  return (
    <div className="vy-pas" aria-hidden="true">
      <span className="vy-logo">
        <Logo vyska={34} title="Greensie" />
      </span>
      <span className="vy-pas-info">
        {pas?.text ? <span>{pas.text}</span> : null}
        {zakaznik?.nazev ? <span>{zakaznik.nazev}</span> : null}
        {zakaznik?.datum ? <span>{fmtDatum(zakaznik.datum)}</span> : null}
      </span>
    </div>
  );
}

function Zapati({ pas, cisloStranky, pocetStranek }) {
  return (
    <div className="vy-zapati" aria-hidden="true">
      <span className="vy-zapati-znacka">
        <Logo jen="znacka" vyska={22} />
      </span>
      <span className="vy-zapati-adresa">
        <b>{FIRMA.nazev}</b>
        <span>
          {FIRMA.ulice} · {FIRMA.mesto}
        </span>
      </span>
      <span className="vy-zapati-kontakt">
        {pas?.text ? <span>{pas.text}</span> : null}
        <span>{FIRMA.telefon}</span>
        <span>
          {FIRMA.email} · {cisloStranky}/{pocetStranek}
        </span>
      </span>
    </div>
  );
}

/**
 * Hlásí naměřenou výšku prvku zpátky do modelu.
 *
 * Výšku textu a kontejneru zná jenom prohlížeč, ale model ji potřebuje –
 * podle ní se pozná přetečení a k ní se přichytávají sousedi. Měří se po
 * vykreslení a zapisuje mimo historii, takže to není „úprava uživatele“.
 */
function useMereniVysky(ref, prvek, editor) {
  const nahlas = editor?.nahlasVysku;
  useLayoutEffect(() => {
    if (!nahlas || !prvek.auto_vyska || !ref.current) return undefined;
    const el = ref.current;
    const zmer = () => {
      const r = el.getBoundingClientRect();
      const stranka = el.closest("[data-stranka-id]");
      if (!stranka) return;
      const pomer = stranka.getBoundingClientRect().width / A4_SIRKA;
      if (pomer > 0) nahlas(prvek.id, r.height / pomer);
    };
    zmer();
    const pozorovatel = new ResizeObserver(zmer);
    pozorovatel.observe(el);
    return () => pozorovatel.disconnect();
  }, [ref, nahlas, prvek.id, prvek.auto_vyska]);
}

/** Obsah kontejneru: děti v mřížce o `styl.sloupce` sloupcích. */
function ObsahKontejneru({ prvek, data, tisk, editor, cisloStranky }) {
  const sloupce = Math.max(1, prvek.styl?.sloupce || 1);
  const deti = (prvek.deti || []).filter((d) => tisk === false || d.viditelny);

  // Kam prvek spadne, když ho teď pustím. Bez téhle značky by se pořadí
  // uvnitř kontejneru měnilo naslepo – tažený prvek se totiž během tažení
  // nikam neposouvá, jen zprůhlední.
  const cil = editor?.tazeni?.cil;
  const mistoVlozeni =
    cil?.typ === "kontejner" && cil.kontejnerId === prvek.id ? cil.index : null;

  return (
    <div
      className="vy-kontejner-deti"
      style={{
        gridTemplateColumns: `repeat(${sloupce}, 1fr)`,
        gap: mm(prvek.styl?.mezera ?? 4),
      }}
      data-kontejner-id={editor ? prvek.id : undefined}
    >
      {deti.map((dite, i) => (
        <Fragment key={dite.id}>
          {mistoVlozeni === i && <span className="vy-misto-vlozeni" aria-hidden="true" />}
          <Prvek
            prvek={dite}
            data={data}
            tisk={tisk}
            editor={editor}
            vKontejneru
            cisloStranky={cisloStranky}
          />
        </Fragment>
      ))}
      {mistoVlozeni !== null && mistoVlozeni >= deti.length && (
        <span className="vy-misto-vlozeni" aria-hidden="true" />
      )}
      {editor && !deti.length && (
        <div className="vy-kontejner-prazdny">Přetáhni sem prvek</div>
      )}
    </div>
  );
}

/** Styl rámečku a pozadí – společný pro prvky na papíře i v kontejneru. */
function stylPrvku(prvek) {
  const s = prvek.styl || {};
  return {
    background: s.pozadi || "transparent",
    border: s.sirka_ramecku
      ? `${s.sirka_ramecku}mm solid ${s.barva_ramecku || "#c9d3ce"}`
      : undefined,
    borderRadius: s.zaobleni ? mm(s.zaobleni) : undefined,
    padding: mm(s.odsazeni ?? 0),
    opacity: s.pruhlednost ?? 1,
  };
}

function Prvek({ prvek, data, tisk, editor, vKontejneru = false, cisloStranky }) {
  const ref = useRef(null);
  useMereniVysky(ref, prvek, vKontejneru ? null : editor);

  if (tisk && !prvek.viditelny) return null;

  const vybrany = editor?.vybranyId === prvek.id;
  const pise = editor?.editovanyId === prvek.id;
  const tazeny = editor?.tazeni?.prvekId === prvek.id;
  const cilKontejner =
    editor?.tazeni?.cil?.typ === "kontejner" &&
    editor.tazeni.cil.kontejnerId === prvek.id;

  // Umístění: na papíře absolutní souřadnice, v kontejneru tok mřížky.
  const poloha = vKontejneru
    ? { minHeight: prvek.auto_vyska ? undefined : mm(prvek.vyska) }
    : {
        position: "absolute",
        left: mm(prvek.x),
        top: mm(prvek.y),
        width: mm(prvek.sirka),
        height: prvek.auto_vyska ? "auto" : mm(prvek.vyska),
        minHeight: prvek.auto_vyska ? mm(5) : undefined,
        zIndex: prvek.z || 0,
      };

  const tridy = [
    "vy-prvek",
    `vy-prvek-${prvek.druh}`,
    vKontejneru ? "v-kontejneru" : "na-papire",
    !prvek.viditelny ? "skryty" : "",
    editor ? "editovatelny" : "",
    vybrany ? "vybrany" : "",
    pise ? "pise" : "",
    tazeny ? "tazeny" : "",
    cilKontejner ? "cil" : "",
    !tisk && !vKontejneru && pretekaDolu(prvek) ? "pretece" : "",
  ]
    .filter(Boolean)
    .join(" ");

  function naStisk(udalost) {
    if (!editor || udalost.button !== 0) return;
    udalost.stopPropagation();
    editor.vyber(prvek.id);
    if (pise) return; // uvnitř psaní patří myš textu
    const elementStranky = udalost.currentTarget.closest("[data-stranka-id]");
    editor.zacniPresun(udalost, prvek.id, elementStranky);
  }

  function naDvojklik(udalost) {
    if (!editor) return;
    udalost.stopPropagation();
    // Text a nadpis kontejneru se píšou přímo na papíře.
    if (prvek.druh === "text" || prvek.druh === "kontejner") {
      editor.otevriPsani(prvek.id);
    }
  }

  const obsah =
    prvek.druh === "kontejner" ? (
      <>
        {(prvek.html || pise) && (
          <TextPole
            prvek={prvek}
            editor={editor}
            pise={pise}
            tisk={tisk}
            trida="vy-kontejner-nadpis"
          />
        )}
        <ObsahKontejneru
          prvek={prvek}
          data={data}
          tisk={tisk}
          editor={editor}
          cisloStranky={cisloStranky}
        />
      </>
    ) : prvek.druh === "text" ? (
      <TextPole prvek={prvek} editor={editor} pise={pise} tisk={tisk} />
    ) : (
      <PrvekObsah prvek={prvek} data={data} tisk={tisk} cisloStranky={cisloStranky} />
    );

  return (
    <div
      ref={ref}
      className={tridy}
      style={{ ...poloha, ...stylPrvku(prvek) }}
      data-prvek-id={prvek.id}
      onPointerDown={naStisk}
      onDoubleClick={naDvojklik}
    >
      {obsah}
      {editor && vybrany && !prvek.zamceno && !vKontejneru && (
        <Uchyty prvekId={prvek.id} editor={editor} />
      )}
      {editor && vybrany && vKontejneru && <span className="vy-znacka-vyberu" />}
    </div>
  );
}

/** Osm úchytů kolem vybraného prvku pro změnu velikosti. */
function Uchyty({ prvekId, editor }) {
  return (
    <>
      {UCHOPY.map((uchop) => (
        <span
          key={uchop}
          className={`vy-uchyt vy-uchyt-${uchop}`}
          onPointerDown={(u) =>
            editor.zacniVelikost(u, prvekId, uchop, u.currentTarget.closest("[data-stranka-id]"))
          }
        />
      ))}
    </>
  );
}

/** Vodicí linky, které se objeví, když se prvek přichytí k sousedovi. */
function Voditka({ linky }) {
  if (!linky?.length) return null;
  return (
    <>
      {linky.map((l, i) => (
        <div
          key={i}
          className={`vy-voditko ${l.smer}`}
          style={l.smer === "svisle" ? { left: mm(l.pozice) } : { top: mm(l.pozice) }}
        />
      ))}
    </>
  );
}

function Stranka({ stranka, index, pocet, data, konfigurace, tisk, editor }) {
  const cislo = index + 1;
  const nahled =
    editor?.tazeni?.nahled?.strankaId === stranka.id ? editor.tazeni.nahled : null;
  const prvky = [...(stranka.prvky || [])].sort((a, b) => (a.z || 0) - (b.z || 0));

  return (
    <div
      className={"vy-stranka" + (tisk ? " tisk" : "")}
      style={{ width: mm(A4_SIRKA), height: mm(A4_VYSKA) }}
      data-stranka-id={editor ? stranka.id : undefined}
      onPointerDown={editor ? () => editor.vyber(null) : undefined}
    >
      {konfigurace.vodoznak?.zobrazit && (
        <div
          className="vy-vodoznak"
          style={{ opacity: konfigurace.vodoznak.pruhlednost ?? 0.07 }}
          aria-hidden="true"
        >
          <Logo jen="znacka" vyska={420} />
        </div>
      )}
      {konfigurace.hlavicka?.zobrazit && (
        <Pas zakaznik={data?.zakaznik} pas={konfigurace.hlavicka} />
      )}

      {editor && (
        <div className="vy-vodici-plocha" aria-hidden="true">
          <div
            className="vy-sazba"
            style={{
              left: mm(OKRAJ_BOK),
              top: mm(OBSAH_OD),
              width: mm(A4_SIRKA - 2 * OKRAJ_BOK),
              height: mm(OBSAH_DO - OBSAH_OD),
            }}
          />
        </div>
      )}

      {prvky.map((prvek) => (
        <Prvek
          key={prvek.id}
          prvek={prvek}
          data={data}
          tisk={tisk}
          editor={editor}
          cisloStranky={cislo}
        />
      ))}

      {nahled && (
        <div
          className="vy-nahled-pusteni"
          style={{
            left: mm(nahled.x),
            top: mm(nahled.y),
            width: mm(nahled.sirka),
            height: mm(nahled.vyska),
          }}
          aria-hidden="true"
        />
      )}
      {editor && <Voditka linky={editor.tazeni?.linky} />}

      {konfigurace.zapati?.zobrazit && (
        <Zapati pas={konfigurace.zapati} cisloStranky={cislo} pocetStranek={pocet} />
      )}
      {editor && <div className="vy-cislo-listu np">Stránka {cislo}</div>}
    </div>
  );
}

export default function Papir({ konfigurace, data, tisk = false, editor = null, zoom = 1 }) {
  const stranky = konfigurace?.stranky || [];

  // Během tažení nesmí kurzor vybírat text – jinak se z přetahování stane
  // označování odstavců.
  useEffect(() => {
    if (!editor?.tazeni) return undefined;
    document.body.classList.add("vy-tahame");
    return () => document.body.classList.remove("vy-tahame");
  }, [editor?.tazeni]);

  return (
    <div
      className={"vy-papir" + (tisk ? " tisk" : "")}
      style={tisk ? undefined : { "--vy-zoom": zoom }}
    >
      {stranky.map((stranka, i) => (
        /* Obal drží místo za zvětšenou stránku. `transform: scale` totiž
           nemění rozměr v rozvržení – bez obalu by se při zoomu 150 %
           stránky překrývaly a scrollbar by končil moc brzy. */
        <div
          key={stranka.id}
          className="vy-stranka-obal"
          style={
            tisk
              ? undefined
              : {
                  width: `calc(${A4_SIRKA}mm * ${zoom})`,
                  height: `calc(${A4_VYSKA}mm * ${zoom})`,
                }
          }
        >
          <Stranka
            stranka={stranka}
            index={i}
            pocet={stranky.length}
            data={data}
            konfigurace={konfigurace}
            tisk={tisk}
            editor={editor}
          />
        </div>
      ))}
    </div>
  );
}
