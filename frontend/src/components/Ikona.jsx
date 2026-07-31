// Sdílené inline SVG ikony (stroke = currentColor, přebírají barvu z CSS).
// Drženo bez externí knihovny — projekt má záměrně nulové UI závislosti.

const CESTY = {
  // moduly (dlaždice rozcestníku)
  projekty: (
    <>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M3 9h18M9 9v11M15 9v11" />
    </>
  ),
  finance: <path d="M3 3v18h18M7 15l3-4 3 3 4-6" />,
  zmeny: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 3" />
    </>
  ),
  nabidkovac: <path d="M13 2 4 14h7l-1 8 9-12h-7l1-8z" />,
  // ---- druhy aktivit v kalendáři (drží se předlohy: checkbox, šálek,
  // kalendář, telefon, obálka) ----
  ukol: (
    <>
      <rect x="4" y="4" width="16" height="16" rx="2.5" />
      <path d="M8.5 12.5l2.5 2.5 4.5-5" />
    </>
  ),
  schuzka: (
    <>
      <path d="M4 8h11v6a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4V8z" />
      <path d="M15 9.5h2.2a2.3 2.3 0 0 1 0 4.6H15" />
      <path d="M3.5 21h12" />
    </>
  ),
  telefon: (
    <path d="M7 3.5c1 0 1.6.4 1.9 1.3l.8 2.2c.2.7 0 1.3-.6 1.7l-1 .7c.8 1.9 2.3 3.4 4.2 4.2l.7-1c.4-.6 1-.8 1.7-.6l2.2.8c.9.3 1.3.9 1.3 1.9v1.8c0 1.2-1 2.1-2.2 2A15.5 15.5 0 0 1 3.7 5.7C3.6 4.5 4.5 3.5 5.7 3.5H7z" />
  ),
  dopis: (
    <>
      <rect x="3" y="5.5" width="18" height="13" rx="2" />
      <path d="M3.6 7l8.4 6 8.4-6" />
    </>
  ),
  poznamka: (
    <>
      <path d="M5 3.5h9.5L19 8v12.5H5z" />
      <path d="M14 3.5V8h5M8 12h8M8 15.5h8M8 18h5" />
    </>
  ),
  // Kalendář — list s vyznačenými dny. Záměrně jiná než `zmeny` (hodiny),
  // aby se v nabídce nepletly.
  kalendar: (
    <>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M3 10h18M8 3v4M16 3v4" />
      <path d="M7.5 14h2M11 14h2M14.5 14h2M7.5 17.5h2M11 17.5h2" />
    </>
  ),
  zakaznici: (
    <>
      <circle cx="9" cy="8" r="3.2" />
      <path d="M3 20c0-3.3 2.7-5.4 6-5.4s6 2.1 6 5.4" />
      <path d="M16 5.2a3.2 3.2 0 0 1 0 5.9M18.5 20c0-2.3-.9-4-2.5-5" />
    </>
  ),
  objednavky: (
    <>
      <path d="M6 3h9l4 4v14H6z" />
      <path d="M15 3v4h4M9 12h7M9 16h5" />
    </>
  ),
  realizace: (
    <>
      <path d="M3 21h18M6 21V10l6-5 6 5v11" />
      <path d="M10 21v-6h4v6" />
    </>
  ),
  pripady: (
    <>
      <rect x="3" y="7" width="18" height="13" rx="2" />
      <path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M3 12h18" />
    </>
  ),
  admin: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-2.7 1.1V21a2 2 0 0 1-4 0v-.1A1.6 1.6 0 0 0 6.6 19l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.6 1.6 0 0 0 3 13.6H3a2 2 0 0 1 0-4h.1A1.6 1.6 0 0 0 4.6 7l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H9a1.6 1.6 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.6 1.6 0 0 0 2.7 1.1l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a1.6 1.6 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z" />
    </>
  ),
  logy: (
    <>
      <rect x="4" y="3" width="16" height="18" rx="2" />
      <path d="M8 8h8M8 12h8M8 16h5" />
    </>
  ),
  konektor: (
    <>
      <path d="M9 12a3 3 0 0 1 3-3h3a3 3 0 0 1 0 6h-1" />
      <path d="M15 12a3 3 0 0 1-3 3H9a3 3 0 0 1 0-6h1" />
    </>
  ),

  manual: (
    <>
      <path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z" />
      <path d="M8 7h7M8 11h7" />
    </>
  ),

  // rozcestník = domů (úvodní souhrn), katalog technologií
  domu: <path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-4v-6H9v6H5a1 1 0 0 1-1-1z" />,
  katalog: (
    <>
      <rect x="3" y="4" width="7" height="7" rx="1.5" />
      <rect x="14" y="4" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </>
  ),

  // UI drobnosti
  sipka: <path d="M7 17 17 7M9 7h8v8" />,
  chevron: <path d="m6 9 6 6 6-6" />,
  // zúžení / rozšíření levého panelu
  panel: (
    <>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M9 4v16" />
      <path d="m13.5 10 2 2-2 2" />
    </>
  ),
  hledat: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m16.5 16.5 4 4" />
    </>
  ),
  klic: (
    <>
      <circle cx="8" cy="15" r="4" />
      <path d="M11 12 20 3M17 3h3v3" />
    </>
  ),
  odhlasit: (
    <>
      <path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3" />
      <path d="M11 8 7 12l4 4M7 12h9" />
    </>
  ),
  pismo: <path d="M4 19 10 5l6 14M6.5 14h7M17 19l3-7 3 7M18.2 16.6h3.6" />,
  napoveda: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M9.2 9.2a2.8 2.8 0 0 1 5.4 1c0 1.9-2.6 2.3-2.6 4" />
      <path d="M12 17.5h.01" />
    </>
  ),
  zamek: (
    <>
      <rect x="5" y="11" width="14" height="9" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </>
  ),
  zvonecek: (
    <>
      <path d="M18 9a6 6 0 1 0-12 0c0 5-2 6-2 6h16s-2-1-2-6" />
      <path d="M10.3 20a2 2 0 0 0 3.4 0" />
    </>
  ),
  obalka: (
    <>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3.5 7 8.5 6 8.5-6" />
    </>
  ),
  slunce: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </>
  ),
  mesic: <path d="M21 12.8A8 8 0 1 1 11.2 3a6.2 6.2 0 0 0 9.8 9.8z" />,
  oko: (
    <>
      <path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6-10-6-10-6z" />
      <circle cx="12" cy="12" r="2.6" />
    </>
  ),
  logo: (
    <>
      <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4" />
      <circle cx="12" cy="12" r="3.4" />
    </>
  ),
};

export default function Ikona({ jmeno, velikost = 16 }) {
  const cesty = CESTY[jmeno];
  if (!cesty) return null;
  return (
    <svg
      viewBox="0 0 24 24"
      width={velikost}
      height={velikost}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {cesty}
    </svg>
  );
}
