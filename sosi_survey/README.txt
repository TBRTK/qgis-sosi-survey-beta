SOSI SURVEY 0.5.10 – OFFENTLIG KILDEKODE

Dette er en kontrollert kildekodepakke bygget fra den
nøyaktige plugin-allowlisten. Pakken inneholder bare QGIS-kildekode,
GPL-lisens, ansvarsfraskrivelse og nybegynner-/testerveiledninger.
Ingen privat .git-historikk, GitHub Actions-logger, interne bygge-
skript, private testfiler eller virkelige feltmålinger følger med.
Kildekoden er publisert på
https://github.com/TBRTK/qgis-sosi-survey-beta.
Den private utviklingshistorikken er ikke inkludert.
Mottakerspesifikke data må aldri legges i det offentlige repoet.

SOSI SURVEY 0.5.10 – OFFENTLIG BETA

BETA – BRUKES PÅ EGET ANSVAR. Programvaren leveres «som den er»
(AS IS), uten garanti. Utvikler og bidragsytere fraskriver seg ansvar
for feil, datatap, tap og skade kun så langt gjeldende rett og GPLv3
§§ 15–17 tillater. Lovbestemt ansvar som ikke kan fraskrives, består.
Intern «BESTÅTT» er ikke full SOSI-kontroll eller mottakergodkjenning.
Les DISCLAIMER.txt og LICENSE før bruk.

NYBEGYNNERE: Start med INSTALLASJON.md. TESTERE: Se TESTGRUPPE.md.
Videre publisering skal kontrolleres for sensitiv informasjon i
kildekode, Git-historikk, Actions-logger, eksempler og installasjons-ZIP.
Feilrapporter må anonymiseres: Ikke del originalmålinger, koordinater,
eiendomsnummer, lokale filstier eller skjermbilder med personopplysninger.
Den vedlagte testpakken inneholder bare vurderte, syntetiske testeksempler.

SOSI SURVEY 0.5.9 – IKON PÅ QGIS-VERKTØYLINJEN

SOSI Survey har nå et egenutviklet, skalerbart SVG-ikon synlig i QGIS sin verktøylinje og i pluginadministratoren. Klikk åpner samme SOSI Survey-dialog som menyvalget. Ikon-handlingen fjernes korrekt når pluginen deaktiveres. Ingen SOSI-data eller eksportregler er endret.

SOSI SURVEY 0.5.8 – STEGVIS LAYOUT

Ny femstegs arbeidsflyt: Start, Datagrunnlag, SOSI-felt, Kontroll og Eksport.
Velg én importvei først, vis bare relevant handling i steg 2, og bruk sammenklappede avanserte metadata. Feltkobling og redigering er samlet i steg 3. Kontroll og eksport er adskilt, og eksportknappen krever bestått intern kontroll. Eksisterende SOSI-parser, eksport, kildedata og personvernkontroller beholdes. Dette er testutkast og ikke ekstern SOSI-godkjenning.

SOSI SURVEY 0.5.7 – VISNINGSFEIL I MØRKT QGIS-TEMA

Rettet feil der side 2 ("Før SOSI-eksport") i veiviseren ble hvit og
tekstforklaringen forsvant i QGIS med mørkt tema på Windows. Begge
veivisersider har nå eksplisitt lesbar, mørk tekst på hvit bakgrunn
for hjelpetekst og feltetiketter. Resten av QGIS-temaet påvirkes ikke.
SOSI-data, parsere, feltimport og eksportregler er uendret.
Dette er en eksperimentell testutgave; intern kontroll erstatter ikke
Kartverkets SOSI-kontroll eller mottakergodkjenning.

SOSI SURVEY 0.5.6 – BYGNINGSOMRISS FRA INNMÅLTE HUSHJØRNER

NYTT: Egen veiviser lar deg markere 3–120 feltmålte hushjørner i QGIS,
hente valgte punkter, kontrollere og endre hjørnerekkefølgen manuelt, og
velge om punktene gjelder ytterkant grunnmur, fasadeliv, takkant eller annet.
Lukket LineString er standard. Polygon kan brukes som lokal
dokumentasjonsgeometri, men SOSI-polygonleveranse krever en separat,
faglig bekreftet profil med boundary_objtype.

Brukeren velger 2D eller bekreftet 3D med høydegrunnlag. Ingen punkt sorteres
automatisk etter kode/navn, ingen ukjente Z-verdier beregnes, og ingen
instrumentkoder konverteres til FKB/SOSI-OBJTYPE. Sjekker dupliserte hjørner,
selvkryssing, lukking og sammentreff etter valgt SOSI-koordinatoppløsning.
Ekte source_ID, source_code, source_description og source_row fra CSV/GPKG/
annet QGIS-punktlag, samt originalattributter og XYZ/høyder, beholdes
i en separat, lokal GeoPackage. Ingen originalmåling redigeres.

Ny separat "Bygning – innmålt plassering" SOSI-profil er et UTSKAST og krever
eksplisitt OBJTYPE, målemetode og faglig kontroll. For ferdig bygning er
innmålte grunnmurhjørner ikke automatisk tilstrekkelig til å levere et korrekt
FKB-Bygning-objekt. FKB-Bygning 5.1.1 skiller mellom Grunnmur, Fasadeliv,
Takkant og Bygning; FKB Grunnmur er særlig brukt ved oppføring.
Kommunens byggesaksleveranse må avklares separat med faktisk vedtak.
SOSI Survey utfører ikke byggesaks-/FKB-godkjenning.

SOSI SURVEY 0.5.5 – MOTTAKERUAVHENGIG FELTDATAIMPORT

Feltmålinger kan importeres fra kolonnebasert CSV/TXT eller velges fra
eksisterende QGIS Point/PointZ-vektorlag. Ingen bestemte instrumentmerker,
feltkodetabeller eller proprietære prosjektfiler er påkrevd.

CSV-veiviseren foreslår, men krever kontroll av, Easting/Northing, Elevation,
ID, Code og Description. Flere skilletegn og tegnsett støttes. Brukeren må
bekrefte EUREF89/UTM 31–36, meter og riktig høydegrunnlag. Det utføres
ingen datum-/høydetransformasjon og ingen Z-verdi gjettes.

Kilde-CSV beholdes uendret. En ny GeoPackage arbeidskopi får alle originale
kolonneverdier, ID, kode, beskrivelse, kilderad, kolonnenavn-kart og SHA256
for kildefilen. SOSI-profilfelt legges til som tomme felt slik at de kan
fylles manuelt eller knyttes til kilden. Emlid/Trimble/Leica/Topcon eller
andre koder blir ALDRI automatisk tolket som SOSI OBJTYPE.
Etter import brukes eksisterende SOSI Survey-fane 2–4 for feltkobling,
kvalitetskontroll, prøveeksport og rapport. 2D/3D må ikke blandes uten
egen eksplisitt oppgave og kontroll. Eldre registreringslogikk beholdes.
Mulig sammensetting av hushjørner til bygningsomriss utvikles senere og
gjøres ikke automatisk i denne versjonen.

SOSI SURVEY 0.5.4 – KLIKKBARE SOSI-KODELISTELENKER

For nye SOSI-arbeidslag viser QGIS-objektskjemaet nå klikkbare,
offisielle lenker fra OBJTYPE og REGFORM, både ved feltene i
"Registrer objekt" og i "Hjelp og koder". Referanser:
Geonorge objektregister (SOSI-objekttyper og historisk
RbFormålOmråde), RegformBrukFormål-kodeliste for PBL 1985 og
ny RpArealformål-kodeliste for PBL 2008. Lenken for nyere planer
er et oppslag; gjeldende prøveprofil støtter IKKE bytte fra
REGFORM til RPAREALFORMÅL eller nyere SOSI-produktspesifikasjon.
Ingen koder eller attributter settes automatisk. Eksporter prøvefil,
kontroller i SOSI-vis/SOSI-kontroll med riktig katalog/DEF og
følg mottakers krav før levering.

SOSI SURVEY 0.5.3 – HJELP DIREKTE I QGIS OBJEKTATTRIBUTTER

Nyregistrerte arbeidslag fra SOSI-veiviseren får et eget QGIS-objektskjema
med fanene "Registrer objekt" og "Hjelp og koder". De opprinnelige SOSI-
feltnavnene OBJTYPE, REGFORM og VERTNIV beholdes i datakilden, mens GUI-et
viser forklarende norske feltetiketter og korte hjelpetekster ved hvert felt.

For arealplanprofilen får VERTNIV et valg av kodene 1–5 med forklarende
tekst. Tallkoden lagres som streng i QGIS-feltet. Det settes ingen
automatisk verdi. OBJTYPE-eksempelet RbFormålOmråde og REGFORM-eksempelet
111 er uttrykkelig kun for eldre reguleringsplaner; nyere planer krever
riktig gjeldende produktspesifikasjon og objektkatalog.
Feltveiledningen fyller aldri ut verdier eller opphever SOSI-kontroll.

Eksisterende importerte SOSI-lag, bevarende eksport og SOSI-objekter
påvirkes ikke. Arbeidslag er i minnet og må eventuelt lagres til GPKG.

SOSI SURVEY 0.5.2 – FORSØK MED NYE SOSI-FLATER OG VEIVISER (QGIS 3.44/4)

Ny veiviser oppretter tomt, redigerbart QGIS-minnelag for PUNKT,
KURVE eller rett FLATE i 2D/3D med feltene fra valgt prøveprofil.
Objekttyper, kvalitetskoder, høyder og mottakerkrav må fylles inn
av brukeren. Prosjekt-CRS må være EUREF89 UTM sone 31–36.
Arbeidslaget må lagres i GeoPackage for varig lagring.

Ved eksport av nye rette Polygon/PolygonZ-felter opprettes SOSI
.FLATE med ..REF til egne .KURVE-objekter. Felles, nøyaktig
sammenfallende kanter deles mellom naboflater med positive/negative
referanser. Hull støttes. Korte kanter som kollapser ved avrunding,
blandet 2D/3D, og delvis overlappende grenser stoppes.
Mottakerprofilen må oppgi boundary_objtype. Arealplanprofilen er
fremdeles et uoffisielt prøveoppsett, ikke en godkjent planprofil.
Bevarende eksport fra original SOSI er uendret.
Full SOSI-produktkontroll med riktig definisjonsfil er fortsatt
nødvendig før levering.

SOSI SURVEY 0.5.1 – EKSPERIMENTELL TEKST-/SYMBOLVISNING (QGIS 3.44/4)

Nye, skrivebeskyttede visningslag viser posisjonen til .TEKST og .SYMBOL.
TEKST etiketteres fra STRENG; SYMBOL vises kun som en posisjonsmarkør,
ikke original karttegnsymbolikk. Første koordinat brukes som visningsanker;
de komplette originale gruppeblokkene bevares ved bevarende eksport.
Ukjent presentasjonssyntaks får ikke oppdiktede koordinater; blokken bevares,
men vises ikke som posisjonsobjekt. Velg ALLE objekter (feltkontroll) for
bevarende SOSI-eksport. Presentation/visningslag kan ikke eksporteres separat.
SOSI-kontroll og mottakergodkjenning gjenstår.

SOSI SURVEY 0.4.5 – UTKAST FOR QGIS 4.0

Programvaren leveres «som den er» (AS IS), uten garanti. Ansvarsfraskrivelse
og ansvarsbegrensning gjelder i det omfang GPLv3 §§15–17 og gjeldende rett
tillater. Se LICENSE.

NYTT I 0.4.5 – GNSS FRA ULIKE MOTTAKERE
Hjelpen beskriver nå produsentuavhengige innmålinger. Tillegget bruker
QGIS-vektorlag; ingen bestemt GNSS-mottaker er påkrevd. Ingen nye
proprietære filformater eller automatiske høydekonverteringer er lagt til.

NYTT I 0.4.4 – HELE FILEN OG AUTOMATISK GJENINNLESING
1. Alle objekter i den faktiske eksportfilen kontrolleres, også når du bare
   retter et del-lag eller et utvalg. Manglende profilfelt utenfor utvalget
   stopper eksporten. Bruk ALLE objekter (feltkontroll) for samlet retting.
2. Den skrevne filen leses tilbake fra disk. Objektantall, ID/rekkefølge,
   geometri med XYZ, buer, ringer/hull, referanser og feltverdier kontrolleres.
   Filen verifiseres i en midlertidig fil før det nye filnavnet opprettes.
   Eksisterende filer erstattes ikke. Intern gjeninnlesing er ikke en
   uavhengig SOSI-kontroll og bruker samme parser som importen.
3. Filhodet vises fra originalen: versjon, CRS, høydegrunnlag, origo,
   planenhet, høydeenhet, tegnsett, produsent/eier og objektkatalog.
   Innstillingene låses ved bevarende eksport; ingen transformasjon skjer.
4. Kontrollrapporten og en lesbar .endringer.txt viser kontrollert omfang,
   konkrete feltendringer og SHA256 for original og eksport. Begge rapporter
   lagres ved siden av SOSI-filen. Linjeskift og UTF-8-BOM kan normaliseres;
   bevarte geometri-/referanseblokker og filhode sammenlignes linjevis.

Importer eldre minnelag på nytt etter oppgraderingen: originalens kontrollsum
registreres nå ved import. Dette kan ikke rekonstrueres trygt fra eldre lag.
Full ekstern SOSI-kontroll og godkjente mottakerprofiler gjenstår.

NYTT I 0.4.3 – MOTTAKERGRUNNLAG
BKK, Eviny, Statnett og Elvia finnes som separate profilutkast. Knappen
«Profilgrunnlag» viser kilder, manglende krav og arbeidskontroller. Ingen av
profilene er leveransegodkjent. Uavklarte krav vises også i kontrollrapporten.
Elvia-profilen gjelder begrenset kvalitetskoding for nye trasearbeider;
offentlig instruks beskriver Shape/GeoNIS. SOSI-leveranse må avtales.
Se SOSI_KONTROLL_UNDERSOKELSE.txt for anbefalt integrasjon med Kartverkets
kontrollprogram, dokumenterte kilder og gjenstående avklaringer. Full ekstern
SOSI-kontroll er undersøkt, men er ikke integrert i denne versjonen.

NAVNEBYTTE I 0.4.2
Pluginen heter nå SOSI Survey, og repositoriet heter qgis-sosi-survey.
Python-pakken og ZIP-filen bruker navnet sosi_survey. Ved oppgradering fra
0.4.1 eller eldre: deaktiver den gamle SOSI Innmåling-pluginen før du
installerer SOSI Survey, slik at du unngår to aktive kopier. Importer
arbeidsfilene på nytt med den nye pluginen; eldre minnelag oppdateres ikke.

LISENS OG FRIVILLIG STØTTE
Prosjektkoden distribueres som GPL-3.0-or-later. Se LICENSE.
QGIS/PyQt/GDAL/FYBA er eksterne avhengigheter og følger sine egne lisenser.
Buy me a coffee: https://buymeacoffee.com/tb_rtk
Støtte er frivillig og endrer ikke lisens eller tilgang til funksjonene.

NYTT I 0.4.2 – BUER, FLATER OG DELT GEOMETRI
Bevarende import støtter nå BUEP som ekte CircularStringZ i QGIS og FLATE som
CurvePolygonZ. Flater bygges fra KURVE/BUEP, signed REF, ytre ring og hull.
Et sammenhengende hull kan også referere en annen FLATE uten egne hull.
Representasjonspunktet kan være NØ eller NØH og beholdes uendret i SOSI-filen.
Grensekurver og buer må ha NØH. Ingen manglende høyder gjettes.

Ved blandet geometri velges «ALLE objekter (feltkontroll)» automatisk.
Dette er en felttabell uten kartgeometri; egne kartlag viser kurver og flater.
Bruk tabellen i trinn 2–4 for å rette og kontrollere samtlige objekter samlet.
Objektkolonnen viser SOSI-type og originalt serienummer. Feltretting i et
enkelt geometrilag er også mulig. Fra 0.4.4 kontrolleres hele eksportfilen.
Eksporten inneholder ALLTID hele originaldokumentet. Andre grupper og alle
refererte grenser beholdes uendret, også ved utvalg av bare enkelte objekter.
Dette erstatter 0.3-regelen om separat lagvis eksport.

Verifisering: geometriens WKB, inkludert kurvetype/ringer/Z, sammenlignes før
eksport. Koordinat- og referanseblokker skrives uendret fra originalen.
Importen avviser blant annet manglende referanser, sykliske referanser, åpne
ringer, XYZ-brudd mellom grensekurver, ugyldige polygoner og kollineære BUEP.
KLOTOIDE, SIRKELP, eldre radiusbasert BUE, frie geometriredigeringer og andre
SOSI-konstruksjoner støttes fortsatt ikke. Dette er ikke full SOSI-kontroll.
Nye buer/flater tegnet direkte i QGIS kan ikke eksporteres med denne funksjonen;
støtten gjelder feltretting i SOSI som er importert med bevarende import.
Importer eldre arbeidskopier på nytt etter oppdateringen.

TIDLIGERE 0.3.0 – 3D OG BEVARENDE EKSPORT (geometribegrensninger utvidet ovenfor)
Importknappen leser nå selv rette PUNKT/KURVE med NØH og ETRS89/UTM sone
31–36. XYZ beregnes med ORIGO-NØ, ENHET og ENHET-H; ENHET brukes til høyde
hvis egen ENHET-H mangler. Negative høyder og nullhøyder beholdes.
Filer med manglende Z, buer, flater, referansegeometri, lokale transformasjoner
eller tvetydig struktur stoppes. Ingen automatisk overgang til 2D skjer.
Gamle allerede importerte 2D-lag må importeres på nytt med importknappen.

Flyt: importer -> bekreft høydegrunnlag -> koble felt -> lag eksportkopi ->
rett/fyll manglende felt -> kontroller -> eksporter til et nytt filnavn.
For disse importlagene brukes bevarende eksport: koordinatblokkene, filhodet,
tegnsett, SOSI-versjon og øvrige egenskaper beholdes fra originalen. Bare
endrede profilfelt oppdateres. Eksporten oppgraderer ikke gammel SOSI-versjon.
Den tidligere regelen om separat lagvis eksport er erstattet: hele filen
eksporteres samlet, også når bare et del-lag har fått rettet feltverdier.
Koordinatoppløsning/tegnsett og filhodefelt er låst i denne flyten; de opprinnelige
verdiene dokumenteres i kontrollrapporten. Ingen geometriredigering eller
koordinat-/høydetransformasjon støttes. Profilutkast og delkontroll gjelder fortsatt.
Importlagene er arbeidskopier i minnet. Eksporter før prosjektet lukkes.

TIDLIGERE 0.2.0 (erstattet av 3D-importen ovenfor)
Importer SOSI-fil på første fane åpner alle lesbare del-lag skrivebeskyttet.
Filendelsene .sos og .sosi støttes. Ingen SOSI-versjoner sperres av pluginen;
faktisk lesestøtte avhenger av QGIS/GDAL/FYBA og filens innhold. Ingen garanti
for alle historiske SOSI-varianter. Enkle syntetiske prøver med versjonshode
3.4, 4.0, 4.5 og 5.0 er testet; dette er ikke komplette versjonsprøver.
Import er 2D: leseren utelater Z og bevarer ikke full SOSI-struktur. Importerte
lag er for kartvisning/egenskaper og må ikke brukes til en ny 3D-leveranse.
Original SOSI beholdes. FYBA kan opprette indeksfiler ved siden av originalen.
Eksporten krever fortsatt Z og stopper 2D-data. Import er ikke fagkontroll.
Feltnavn fra GDAL kobles automatisk til de tilsvarende prøveprofilfeltene.
Ved utfyllingsområdet vises nå forklaring for valgt felt, datoformat, enhet,
kodegrunnlag og om feltet er påkrevd. Koder og nøyaktighet må dokumenteres;
pluginen gjetter ingen verdier ut fra mottakerens merke eller modell.

Dato: 18.10.2026

INSTALLASJON
1. Åpne QGIS 4.0.0.
2. Velg Programtillegg > Administrer og installer programtillegg > Installer fra ZIP.
3. Velg sosi_survey-0.4.5.zip fra denne mappen, installer og aktiver.
4. Åpne Programtillegg > SOSI Survey > kontroller og eksporter.
   Eksperimentelle tillegg kan kreve at visning av slike tillegg er aktivert.

HVA DETTE ER
Et kjørbart utkast for innmålte punkter og rette linjestrenger innen
bygg/anlegg, VA og el, uavhengig av GNSS-mottaker. Bevarende SOSI-import
støtter i tillegg de avgrensede buene og flatene beskrevet ovenfor.
Tillegget leser QGIS-vektorlag. Det kommuniserer ikke med antenner, tolker ikke
rå GNSS-observasjoner, og omformer ikke enkeltpunkter til ledningslinjer.

Arbeidsflyten er: velg lag og profil > koble felt > fyll og rett eksportkopi >
kontroller > skriv en SOSI 5.0-prøvefil og tilhørende JSON-kontrollrapport.

BRUK MED GNSS-EKSPORT FRA ULIKE MOTTAKERE
Importer din eksport som et QGIS-lag med korrekt øst/nord og Z i meter.
CSV/TXT kan leses med QGIS sin tekstimport med riktig skilletegn og
kolonnevalg; GeoPackage kan åpnes direkte. Bevarende SOSI-import brukes
for eksisterende SOSI-filer. Tillegget leser ikke JOB/DBX, proprietære
mottakerprosjekter eller RINEX direkte. Formatstøtte i QGIS avhenger
av installerte datalesere. Samme filtype garanterer ikke like enheter,
akseorden, høydetype eller kvalitetsfelt. Kontroller dette før eksport.
Bruk GeoPackage som arbeidsformat. Dersom CSV-importen gir 2D-geometri,
må du opprette 3D-geometri med korrekt høydefelt før denne versjonen kan
eksportere. En attributtkolonne med høyde blir ikke automatisk til Z.
Ikke velg en ellipsoidisk GNSS-høyde som NN2000 uten riktig transformasjon.
Ingen omprojisering, geoidemodell eller vertikal transformasjon utføres her.
Støttede koordinatsystemer: EUREF89 UTM sone 31–36 (EPSG:25831–25836).
Andre systemer, for eksempel NTM, må forberedes separat i en arbeidskopi.

PRØV UTEN EGNE DATA
Åpne eksempler/demo_survey.gpkg i QGIS og velg laget demo_punkter eller
demo_linjer. Dette er utelukkende syntetiske testdata. Testpunkt/Testlinje er
testnavn og dokumenterer ingen godkjent objekttype i en fagstandard.
Velg prøveprofilen, høydegrunnlag NN2000 og bekreft det for disse testdataene.
Feltnavnene kobles automatisk der navnene stemmer nøyaktig.

UTFYLLING OG KONTROLL
- Fellesverdi i trinn 2 brukes bare hvis kildeverdien er tom/null.
- I trinn 3 kan hver verdi redigeres direkte i tabellen.
- «Fyll tomme celler» fyller bare tomme celler, eventuelt i markerte rader.
- Eksisterende verdier blir ikke overskrevet av masseutfyllingen.
- Originaldata endres ikke. Verdiene lagres i prøvefilen og kontrollrapporten.
- Lukking av vinduet beholder kopien i samme QGIS-økt. Ny kopi, profilbytte,
  lagbytte eller avslutning av QGIS forkaster kopien. Lagre rapporten først.
- Endrede feltkoblinger og valget «bare valgte» gjelder først ved ny kopi.
- Klikk en feil eller velg «marker alle» for å finne berørte objekter i kartet.
- Eksport kjører kontrollen på nytt og blokkeres hvis det finnes feil.
- Eksisterende leveransefiler og rapporter erstattes ikke. Bruk et nytt navn.

HVA DELKONTROLLEN DEKKER
Påkrevde verdier i valgt profil, datatyper, gyldige kalenderdatoer, tekstlengder,
eventuelle profilkodelister og tallgrenser; støttet geometri, endelige
koordinater, påkrevd Z, sammenfall etter avrunding, koordinatsystem,
bekreftet høydegrunnlag, tegnsett og nødvendige opplysninger i dette filhodet.
Feil har objekt-ID og feltnavn. Rapporten inneholder faktisk eksportkopi,
profil, feltkoblinger, kontrollresultat og SHA-256 for den eksporterte filen.

HVA SOM IKKE ER GODKJENT/FERDIG
Dette er ikke Kartverkets SOSI-kontroll. Ingen av de medfølgende profilene er
godkjent etter en full fagstandard eller en bestemt mottakers krav.
Bygg/anlegg-, VA- og el-profilene har samme minimale prøvefelter. De er egne
startpunkter, ikke ferdige fagprofiler. Påkrevde prøvefelt er OBJTYPE,
DATAFANGSTDATO, KVALITET.MÅLEMETODE og KVALITET.NØYAKTIGHET.
Dette er et bevisst prøveoppsett, ikke universelle obligatoriske SOSI-felt.
Tradisjonell numerisk MÅLEMETODE brukes i prøven. Nyere produktspesifikasjoner
kan bruke DATAFANGSTMETODE med tekstkoder; disse må modelleres i riktig profil.

Det finnes foreløpig ingen verifisert kodeliste for objekttyper/målemetoder i
profilene. En ukjent eller faglig feil objekttype kan derfor passere som tekst.
VA kan kreve blant annet funksjon, materiale, dimensjon og tilkoblinger, og el
kan kreve egne anleggsegenskaper. Dette må spesifiseres av mottakeren.
Profiler kan utvides med required, type, enum, max_length, min og max.
Objektavhengige fagregler, ledningsnettverkskontroll og eksternt SOSI-kontroll-
kall er ikke implementert. Refererte flater har avgrenset geometrikontroll,
som lukking i XYZ og gyldige ringer, men ikke full faglig topologikontroll.

Ingen generelle feltverdier eller kvalitetskoder settes ut fra mottakerens navn.
RTK-status og instrumentets estimerte presisjon beviser ikke alene korrekt
SOSI-målemetode eller standardavvik. Kvalitetens nøyaktighetsfelt i prøven er cm.

FØR REELL LEVERING
Vi trenger mottakerens innmålingsinstruks og helst en godkjent eksempel-SOSI
for å lage reelle profiler. Angi korrekt OBJEKTKATALOG og katalogversjon.
Prøvefil må kjøres i SOSI-vis/SOSI-kontroll med riktig fagoppsett og testes av
mottaker. Høydene må også verifiseres i et uavhengig 3D-kompatibelt verktøy.

KOMPATIBILITET FUNNET I LOKAL TEST
QGIS: 4.0.0-Norrköping. GDAL: 3.12.2. Windows, Qt6.
Lokal GDAL/SOSI avviste UTF-8-utgaven av syntetisk prøvefil, mens samme innhold
i ISO8859-10 kunne leses. ISO8859-10 er derfor standardvalg. UTF-8 er valgbart
med en egen advarsel. Tegn som ikke kan kodes avvises; de erstattes ikke.
GDALs SOSI-leser leser XY, men bygger 2D-geometri og utelater Z ved innlesing.
Dette er bekreftet med test og kildekode. Z blir skrevet til SOSI-filens NØH
og testes i filinnholdet, men er ikke uavhengig verifisert gjennom GDAL.
QGIS-innlesing alene er derfor ikke høydekontroll.
Standard oppløsning er 1 cm. Ved 1 mm brukes et automatisk lokalt origo i
hele kilometer for å bevare presisjon uten å overskride heltallsgrensen.
Koordinater utenfor 32-bits heltallsgrense etter dette avvises.

UTVIKLING
sosi_survey/core.py: regler og filskriver uten QGIS-avhengighet.
sosi_survey/adapter.py: QGIS-geometri/attributter til eksportkopi.
sosi_survey/plugin.py: Qt6-vindu, utfylling, kontrollrapport og eksport.
sosi_survey/audit.py: hele filen, gjeninnlesing og endringsrapport.
sosi_survey/profiles/: deklarative JSON-profiler; ingen kode evalueres.
tests/test_core.py: regel- og filtester.
tests/qgis_integration.py: tester mot installert QGIS 4.0 med syntetiske data.
tests/test_audit_qgis.py: skjulte feil, filhode, bevaring og manipulerte filer.
build_release.py: lager installasjons-ZIP og profilsjablonger.

KILDER
SOSI-formatrealisering 5.0:
https://standarder.geonorge.no/sosi/del-1-generell-del/realisering-i-sosi-format/5.0/realisering-i-sosi-format-50-sosi-generell-del.pdf
QGIS 4.0 API:
https://api.qgis.org/api/4.0/classQgsVectorLayer.html
GDAL SOSI:
https://gdal.org/en/stable/drivers/vector/sosi.html
GDAL-kilde (punkt/linje bygges uten Z):
https://github.com/OSGeo/gdal/blob/v3.12.2/ogr/ogrsf_frmts/sosi/ogrsosidatasource.cpp
Kartverkets OpenFYBA:
https://github.com/kartverket/fyba
FKB generell del (blant annet forskjell fra tradisjonell målemetode):
https://dokument.geonorge.no/produktspesifikasjoner/fkb-generell-del/Versjon%205.1/index.html

PUBLISHING AND PRIVACY
Use RELEASE_TEMPLATE.md for all GitHub releases. See docs/PUBLISHING.md for mandatory source, history, synthetic-fixture and ZIP checks before uploading.

## Support

If this project has been useful to you and you would like to support further testing, documentation, and development, you can buy me a coffee:

[☕ Buy me a coffee](https://buymeacoffee.com/tb_rtk)

Support is completely optional and is greatly appreciated.

## License

See [LICENSE](LICENSE).
