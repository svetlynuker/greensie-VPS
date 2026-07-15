# Popisy modulů

Složka pro **technické popisy vyrobených modulů a funkcí** appky Greensie –
pro archivaci, dohledatelnost rozhodnutí a onboarding.

## K čemu to je
Když se dokončí nějaká ucelená část (modul, výpočet, integrace), sepíše se sem
souhrn: co dělá, jaká je výpočtová/business logika, parametry a jejich hodnoty,
datový model, API, frontend, nasazení a otevřené body/předpoklady k ověření.
Cíl: aby šlo modul pochopit a udržovat bez pročítání celého kódu a historie.

## Konvence
- Jeden soubor na modul, název podle modulu (kebab-case), např. `peak-shaving.md`.
- Uváděj konkrétní čísla/vzorce a odkazy na klíčové soubory v kódu.
- Sekci „Otevřené body / předpoklady“ drž aktuální – co je nepotvrzené nebo modelové.
- Historii větších změn (PR) klidně veď v tabulce na konci.

## Obsah
- [`peak-shaving.md`](./peak-shaving.md) – peak shaving kalkulátor (sazby distributorů, ekonomika 2026/2027, Koeficient AKU, grafy, návratnosti).
- [`ppa-fve.md`](./ppa-fve.md) – PPA pro FVE (simulace výroby, spárování se spotřebou, ekonomika klienta i investora, ekonomický návrh velikosti, % pokrytí spotřeby).
