# SOSI Survey – informasjon til betatestere

**BETA – BRUKES PÅ EGET ANSVAR.** Dette er en frivillig test av en
eksperimentell QGIS-plugin. Ikke bruk den som eneste grunnlag for
myndighetsleveranser, byggesaker, grensefastsetting eller kritisk
landmåling. Intern «BESTÅTT» er ikke Kartverkets SOSI-kontroll.

## Kom i gang
1. Last ned den **kontrollerte plugin-ZIP-en** som deles av utgiveren.
2. Installer med [installasjonsguiden](INSTALLASJON.md).
3. Test helst med **konstruerte, syntetiske** SOSI-/CSV-filer.
4. Prøv import → feltkobling → kontroll → eksport av prøvefil.

## Hva ønsker vi å teste?
- Om pluginen starter i QGIS 3.44 uten feil, også med mørkt tema.
- Import av 2D/3D SOSI, BUEP, FLATE, hull, TEKST og SYMBOL.
- Feltmålinger fra forskjellige mottakere som CSV eller QGIS-lag.
- Forklaringer av OBJTYPE, kravfelter, avviksliste og oppsett.
- Om eksporterte prøvefiler kan leses og kontrolleres **uavhengig**.
- At feil, manglende data eller usikker geometri stoppes med tydelige meldinger.

## Slik rapporterer du en feil
Oppgi:
- QGIS-versjon og operativsystem.
- SOSI Survey-versjon (f.eks. 0.5.10).
- Trinnene du utførte.
- Hva du forventet, og hva som skjedde.
- Feilmeldingen, **etter at den er kontrollert for sensitiv informasjon**.

**Ikke del originale kunde- eller eiendomsfiler**, koordinatlister,
bygningsadresser, navn, GNSS-receiver-ID-er, råmålinger, rapporter,
NTRIP-tilganger eller skjermbilder der slike data synes. Konstruer
et nytt, ufarlig eksempel som gjenskaper feilen. Feillogger og
kontrollrapporter kan inneholde lokale filstier.

## Ansvarsfraskrivelse
Programvaren leveres «som den er» (AS IS), uten garanti.
Testere bruker den på eget ansvar. Utvikler og bidragsytere
fraskriver seg ansvar for feil, tap og skade kun i den utstrekning
GPLv3 §§ 15–17 og gjeldende rett tillater. Ufravikelig lovbestemt
ansvar består. Se DISCLAIMER.txt og LICENSE.
