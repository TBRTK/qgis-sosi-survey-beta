# SOSI Survey – QGIS-plugin (eksperimentell beta)

**BETA – BRUKES PÅ EGET ANSVAR.** Dette er en uoffisiell QGIS-plugin
for import, feltkontroll og prøveeksport av SOSI. Den er ikke sertifisert
eller godkjent av Kartverket, QGIS eller noen kommune.

## Last ned versjon 0.5.10

- **[Last ned installasjons-ZIP](releases/sosi_survey-0.5.10.zip)** – velg «Download raw» på GitHub. Bruk denne filen i QGIS.
- **[Se hele kildekoden](sosi_survey/)** – 18 Python-filer, profiler og dokumentasjon.
- **[Installasjon steg for steg](INSTALLASJON.md)** – for nybegynnere.

[Se introduksjonsvideoen](https://youtu.be/IsYCNBQ8hkk?si=oaQAC-hcu8RcjLrd).

Anbefalt testmiljø er QGIS 3.44. Funksjonene er fortsatt eksperimentelle.
GitHubs «Code → Download ZIP» inneholder hele repositoryet og er **ikke**
pluginens installasjonsfil. Pluginen er ikke publisert i QGIS sin offisielle
utvidelseskatalog.

## Hva kan pluginen gjøre?

- Lese og kontrollere en del SOSI-objekter i 2D og 3D.
- Bevare SOSI-geometri ved kontrollerte eksportkopier.
- Importere feltmålinger fra ulike mottakere via CSV/TXT eller QGIS-lag.
- Koble og rette SOSI-egenskaper, med hjelpetekster og feilliste.
- Prøveeksportere SOSI med en intern rapport, **ikke** offisiell
  godkjenning.
- Bygge lokale, sporbare bygningsomriss fra manuelt valgte hushjørner.

Enkelte fagprofiler er uferdige. Funksjoner og API-er kan endres uten varsel.
Geodetisk og byggesaksfaglig kontroll må utføres separat.

## Viktig om sikkerhet og personvern

Behandle originale måledata og kundedokumenter lokalt. Ikke publiser
SOSI-filer, punkter, råmålinger, koordinater, eiendomsnummer, personnavn,
NTRIP-data, lokale filstier eller skjermbilder fra reelle oppdrag.
Se **[Informasjon til betatestere](TESTGRUPPE.md)**.

## Bruk på eget ansvar

Programvaren leveres **«som den er» (AS IS), uten garanti**.
Utvikler og bidragsytere fraskriver seg ansvar for feil, tap og skade
bare i den utstrekning GPLv3 §§ 15–17 og gjeldende rett tillater.
Lovbestemt ansvar som ikke lovlig kan fraskrives, består.
Les [DISCLAIMER.txt](DISCLAIMER.txt) og [LICENSE](LICENSE) før bruk.

## Lisens og opphav

GPL-3.0-or-later. Programmet ble utviklet med bistand fra
AI-verktøy; se NOTICE og kildenes attribusjoner. Frivillig støtte
er tilgjengelig gjennom pluginens eksisterende lenke.

## Support

If this project has been useful to you and you would like to support further testing, documentation, and development, you can buy me a coffee:

[☕ Buy me a coffee](https://buymeacoffee.com/tb_rtk)

Support is completely optional and is greatly appreciated.

