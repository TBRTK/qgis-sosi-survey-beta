# SOSI Survey – enkel installasjonsguide (for nybegynnere)

**BETA – BRUKES PÅ EGET ANSVAR.** SOSI Survey er ikke offisielt godkjent
av Kartverket eller QGIS. Intern kontroll erstatter ikke faglig SOSI-kontroll.
Les DISCLAIMER.txt før bruk. Prøv først med syntetiske testdata.

## Du trenger

- QGIS 3.44, for eksempel 3.44.7 (anbefalt for første test).
- **[sosi_survey-0.5.10.zip](releases/sosi_survey-0.5.10.zip)**.
  Klikk «Download raw» på GitHub og lagre filen uten å pakke den ut.
- Ingen GitHub-konto er nødvendig for å laste ned den offentlige ZIP-filen.

QGIS: https://qgis.org/download/. Støtte for QGIS 4 er ikke ferdig verifisert.

## Installer i QGIS – steg for steg

1. Last ned **sosi_survey-0.5.10.zip** fra lenken ovenfor.
   Ikke bruk GitHubs «Code → Download ZIP».
2. La plugin-ZIP-filen være pakket.
3. Start QGIS og velg **Utvidelser → Administrer og installer utvidelser**.
4. Velg **Installer fra ZIP** til venstre.
5. Trykk **Bla gjennom** og velg filen `sosi_survey-0.5.10.zip`.
6. Trykk **Installer utvidelse**. Godkjenn varselet bare dersom du stoler på utgiveren.
7. Under **Installerte**: Aktiver **SOSI Survey – utkast** og start eventuelt QGIS på nytt.

## Slik åpner du pluginen

- Klikk **SOSI Survey-ikonet** i QGIS-verktøylinjen, eller
- Velg **Utvidelser → SOSI Survey → SOSI Survey**.
- Finner du ikke ikonet? Se **Vis → Verktøylinjer → Utvidelser**.
- Ved første oppstart kommer en **BETA-/ansvarsadvarsel**.
  Les den. Fortsett bare hvis du ønsker å teste på eget ansvar.

## Første test – med en ufarlig eksempelkopi

1. **1. Start:** Velg *Åpne eksisterende SOSI-fil* eller
   *Importer feltmålinger fra CSV/TXT*.
2. **2. Datagrunnlag:** Velg en **syntetisk testfil** eller et separat
   testlag i QGIS. Kontroller EPSG, enheter og høydegrunnlag.
3. **3. SOSI-felt:** Koble riktige kildefelt og fyll inn nødvendige
   attributter. Bruk hjelpeteksten – ikke gjett `OBJTYPE` eller kvalitet.
4. **4. Kontroll:** Kjør intern kontroll. Rett **FEIL** før neste steg.
   **ADVARSEL** kan gjelde foreløpig profil og manglende ekstern kontroll.
5. **5. Eksport:** Eksporter en **SOSI-prøvefil** og kontrollrapport.
   Du må selv kontrollere filen i et uavhengig SOSI-kontrollprogram før
   eventuelt mottak/levering.

**Viktig:** Pluginen er ikke ment som godkjent leveranseløsning for
kommunale byggesaker, matrikkel eller FKB før korrekt spesifikasjon,
innmåling og uavhengig kontroll er dokumentert.

## Hvis installasjonen ikke virker

- **Pluginen finnes ikke:** Se *Installerte*, og kryss av for aktivering.
- **Mangler ikon:** Prøv å åpne pluginen fra **Utvidelser**-menyen.
- **Feil etter oppdatering:** Deaktiver eller avinstaller den gamle
  SOSI Survey-versjonen via pluginadministratoren, installer ny ZIP,
  og start QGIS på nytt. Lagre egne QGIS-prosjekter først.
- **Importfeil:** Sjekk at riktig fil er valgt og at prosjektets
  koordinatsystem er dokumentert. Ikke anta at alle SOSI-dialekter støttes.
- **Kontrollfeil:** Les kolonnen *Melding*. Eksporter ikke en fil
  som har feil bare for å teste mottakersystemet.

## Hvordan melde tilbake til testgruppen

Oppgi QGIS-versjon, SOSI Survey-versjon, hvilken knapp/funksjon du testet,
hva du forventet, og hva som faktisk skjedde. Ikke del originale
SOSI-filer, CSV-feltmålinger, personopplysninger, matrikkel-/eiendomsdata,
filstier eller urensede skjermbilder. Bruk egne konstruerte testeksempler.

## Ansvar og lisens

**Bruk på eget ansvar.** Programvaren leveres «som den er» (AS IS) uten
garanti. Utvikler og bidragsytere fraskriver seg ansvar bare innenfor
GPLv3 §§ 15–17 og gjeldende rett. Lovbestemt ansvar som ikke kan
fraskrives, er ikke utelukket. Se DISCLAIMER.txt og LICENSE.
