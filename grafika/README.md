# Grafika Greensie

Firemní logotypy a hlavičkové papíry. Dřív ležely jen na serveru mimo git, takže
se o ně dalo přijít — proto jsou tady.

## Loga

Sada má vodorovné i svislé provedení, každé ve třech podkladech:

| Přípona | Podklad | K čemu |
|---|---|---|
| **a** | průhledný | web, tisk na bílou — **tohle se používá** |
| b | bílý | když je potřeba logo „vyříznout" z barevného pozadí |
| c | černý | tmavé podklady, kde nevadí černý rám |

| Číslo | Provedení | Barevnost |
|---|---|---|
| **2** | vodorovné (značka vlevo, text vpravo) | značka zelená, text černý |
| 4 | vodorovné | celé zelené |
| 6 | svislé (značka nad textem) | značka zelená, text černý |
| 8 | svislé | celé zelené |

Varianty s claimem *(jiná číselná řada)* tu schválně nejsou — v appce se claim
nepoužívá.

### Co používá appka

**`svg/2a.svg`** — vodorovné, bez claimu, průhledné. Jeho kopie je i v
`frontend/src/assets/logo-greensie.svg` a z ní je vygenerovaná komponenta
`frontend/src/components/Logo.jsx`.

Proč právě tohle: značka má v souboru `fill="#79c44f"`, ale **text logotypu žádnou
barvu nemá**. Text proto v appce obarvujeme přes `currentColor` — na tmavém panelu
je světlý, na bílém papíře tmavý — a značka si drží firemní zelenou. Jeden soubor
tedy vystačí na všechna místa a nepotřebujeme variantu `b`/`c` s vypáleným
pozadím.

Když se logo změní, přegeneruj komponentu z nového SVG (skript je jednorázový,
stačí vzít path se `fill="#79c44f"` jako značku a ostatní jako text).

### Dvě zelené, ať je to jasné

- **`#79c44f`** je zelená z logotypu. V appce je jako token `--brand-logo` a
  používá ji **jen značka**. Na bílém podkladu má kontrast 2,14 : 1, takže bílý
  text ani ikona na ní nejsou čitelné.
- **`#2f9e44`** je zelená rozhraní (`--brand`) — tlačítka, aktivní položky,
  zvýraznění. Na bílém má 3,45 : 1, což pro ikony a tlačítka s bílým textem stačí.

Nesjednocuj je do jedné. Světlá by rozbila čitelnost rozhraní, tmavá by nebyla
věrná logu.

## Hlavičkové papíry

Wordové šablony ve třech variantách adresy. Hlavička i zápatí v nich nejsou text,
ale **obrázky** — proto jsou pásky vytažené zvlášť, aby se daly použít i jinde:

| Soubor | Co je na něm |
|---|---|
| `pas-hlavicka-bedrichovska.jpg` | logo + Bedřichovská 2183/16, 182 00 Praha 8 – Libeň |
| `pas-hlavicka-na-okraji.jpg` | logo + Na okraji 381/41, Praha 6 – Veleslavín |
| `pas-zapati-mesto.jpg` | zelený pás se siluetou města (dekorace) |

Kontakt z bedřichovské varianty je v zápatí nabídky pro zákazníka
(`frontend/src/components/NabidkaVystup.jsx`, konstanta `FIRMA`). Když se adresa
změní, uprav ji tam.

Zápatí nabídky je dnes textové. Zelený pás se siluetou města by se do něj dal
přidat jako dekorace, ale je to raster — na tisk by chtěl vektorovou verzi.
