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

  // UI drobnosti
  sipka: <path d="M7 17 17 7M9 7h8v8" />,
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
