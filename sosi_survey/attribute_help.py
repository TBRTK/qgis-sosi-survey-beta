# SPDX-License-Identifier: GPL-3.0-or-later
"""Field help in QGIS feature forms for SOSI Survey draft layers.

Aliases never change the actual SOSI field names or automatically select
codes. Guidance is not a replacement for the product specification/DEF.
QGIS imports are deferred to permit independent, synthetic unit tests.
"""

from html import escape

VERTICAL_LEVELS = (
    ("1 – Under grunnen (tunnel)", "1"),
    ("2 – På grunnen / vannoverflaten", "2"),
    ("3 – Over grunnen (for eksempel bru)", "3"),
    ("4 – På bunnen (sjø / innsjø)", "4"),
    ("5 – I vannsøylen", "5"),
)

_PLAN_GUIDANCE = {
    "OBJTYPE": (
        "Objekttype",
        "Hva slags kartobjekt tegner du? Skriv SOSI-objekttypens eksakte navn.",
        "Eksempel i en eldre reguleringsplan: RbFormålOmråde for en formålsflate. "
        "En nyere plan eller et annet objekt kan kreve et annet navn. "
        "Kontroller mot riktig objektkatalog. Ikke skriv arealformålskoden her.",
    ),
    "REGFORM": (
        "Reguleringsformål",
        "Tallkode som beskriver hva arealet er regulert til; ikke et areal i m².",
        "Eksempel i eldre reguleringsplan etter PBL 1985: 111 betyr "
        "frittliggende småhusbebyggelse. Kodene kan være andre i nyere "
        "planer. Bruk planens faktiske produktspesifikasjon/kodeliste.",
    ),
    "VERTNIV": (
        "Vertikalnivå",
        "Velg hvilket nivå planen gjelder, ikke terrenghøyde i meter.",
        "1 = under bakken, 2 = på bakken/vannoverflaten, "
        "3 = over bakken, 4 = på sjø-/innsjøbunnen, 5 = i vannsøylen. "
        "Velg bare det som gjelder objektet.",
    ),
}

_GENERIC_GUIDANCE = {
    "OBJTYPE": (
        "Objekttype",
        "Bruk det eksakte SOSI-objekttypenavnet fra mottakerens objektkatalog.",
        "Objekttypen beskriver hva som er målt eller tegnet. "
        "Ikke utled typen automatisk fra instrumentmodellen eller geometrien.",
    ),
    "DATAFANGSTDATO": (
        "Dato for innmåling",
        "Når ble objektet faktisk målt? Bruk YYYY-MM-DD eller YYYYMMDD.",
        "Ikke bruk eksportdatoen dersom målingen ble gjort en annen dag.",
    ),
    "KVALITET.MÅLEMETODE": (
        "Målemetode (kode)",
        "Kode for faktisk målemetode fra mottakerens SOSI-kodeliste.",
        "RTK-status og instrumentmodell avgjør ikke alene riktig SOSI-kode.",
    ),
    "KVALITET.NØYAKTIGHET": (
        "Nøyaktighet i plan (cm)",
        "Oppgi dokumentert nøyaktighet i centimeter, ikke meter.",
        "Eksempel: 2 betyr 2 cm. Må verifiseres mot måledokumentasjonen.",
    ),
    "KVALITET.H-MÅLEMETODE": (
        "Høydemålemetode (kode)",
        "Kode for metoden høyden er bestemt med.",
        "Dette er ikke høydegrunnlaget NN2000 eller ellipsoidisk høyde.",
    ),
    "KVALITET.H-NØYAKTIGHET": (
        "Høydenøyaktighet (cm)",
        "Dokumentert høydenøyaktighet i hele centimeter.",
        "Eksempel: 3 betyr 3 cm. Ikke utled dette fra antall Z-desimaler.",
    ),
}

# These are verified, static external references. Never construct an arbitrary
# browser URL from user-editable OBJTYPE/REGFORM values or external profiles.
# The two laws use different SOSI properties and are NOT interchangeable.
PLAN_FIELD_LINKS = {
    "OBJTYPE": (
        ("Søk alle objekttyper i Geonorge", "https://objektkatalog.geonorge.no/"),
        ("RbFormålOmråde – eksempel for eldre plan (PBL 1985)",
         "https://objektkatalog.geonorge.no/Objekttype/Index/EAID_B0FF5618_9E84_4d6c_904E_4AFAEEBC579A"),
        ("RpArealformålOmråde – eksempel for nyere plan (PBL 2008)",
         "https://objektkatalog.geonorge.no/Objekttype/Index/EAID_85CF8D32_7889_4e7a_BA29_E4611C22D211"),
    ),
    "REGFORM": (
        ("Finn REGFORM-kode – eldre reguleringsplan (PBL 1985)",
         "https://objektkatalog.geonorge.no/Objekttype/Index/EAID_298CA673_410E_48e5_9271_F2A2CD5D944E"),
        ("Nyere reguleringsplan: RpArealformål-koder (annet SOSI-felt)",
         "https://register.geonorge.no/sosi-kodelister/plan/5.0/rparealform%C3%A5l"),
    ),
}
SOURCE_LINKS = (
    ("VERTNIV: kodeliste for vertikalnivå",
     "https://objektkatalog.geonorge.no/Objekttype/Index/EAID_EB566F38_5186_4395_AE43_8F5A2EC038F8"),
    ("Historisk planproduktspesifikasjon – Reguleringsplaner",
     "https://www.regjeringen.no/globalassets/upload/md/vedlegg/planlegging/geografisk20informasjon/plan_produktspek_del_32_reguleringsplaner_20100702.pdf"),
)


def field_source_links(profile, path):
    """Give direct, authoritative references only for recognized plan fields."""
    if not is_area_plan(profile):
        return ()
    return PLAN_FIELD_LINKS.get(path, ())


def link_markup(links):
    """Return QLabel-compatible HTML with external links, never code execution.

    QgsAttributeEditorTextElement uses QgsTextWidgetWrapper in QGIS 3.44.
    The latter creates QLabel with setOpenExternalLinks(True).
    """
    items = []
    for label, url in links:
        if not (url.startswith("https://objektkatalog.geonorge.no/")
                or url.startswith("https://register.geonorge.no/")
                or url.startswith("https://www.regjeringen.no/")):
            raise ValueError("Kun godkjente Geonorge- og offentlige kilder kan lenkes.")
        items.append('<a href="' + escape(url, quote=True) + '">'
                     + escape(label, quote=True) + '</a>')
    return " | ".join(items)


def is_area_plan(profile):
    """Never infer regulatory codes from one field name alone."""
    return "arealplan" in str(profile.get("id", "")).casefold()


def _safe_text(text):
    """Prevent custom profile hints from becoming QGIS/HTML expressions."""
    return (str(text).replace("[%", "[ %").replace("%]", "% ]")
            .replace("<", "‹").replace(">", "›"))


def field_guidance(rule, profile):
    """Return display alias, concise hint and detailed explanation."""
    path = rule["path"]
    data = (_PLAN_GUIDANCE if is_area_plan(profile)
            else _GENERIC_GUIDANCE).get(path)
    if data is None:
        data = (rule.get("label", path),
                rule.get("help") or rule.get("description")
                or "Fyll inn verdien etter gjeldende produktspesifikasjon.",
                "Kontroller opplysninger mot mottakerens objektkatalog. "
                "Ingen verdi gjettes.")
    label, short, details = (_safe_text(item) for item in data)
    label += " (" + path + ")"
    if rule.get("required"):
        label += " *"
    if rule.get("enum"):
        details += " Profilens tillatte verdier: " + ", ".join(
            _safe_text(v) for v in rule["enum"]) + "."
    return dict(alias=label, inline=short, details=details,
                path=path, required=bool(rule.get("required")))


def helper_summary(profile):
    lines = [
        "Fyll inn verdiene, og kontroller dem før SOSI-eksport.",
        "* = obligatorisk i valgt profil. Ingen kode fylles automatisk.",
    ]
    if not profile.get("approved", False):
        lines.append("Dette er et profilutkast; intern kontroll er ikke offisiell SOSI-kontroll.")
    return "\n".join(lines)


def _add_text(parent, name, content):
    from qgis.core import QgsAttributeEditorTextElement
    element = QgsAttributeEditorTextElement(name, parent)
    element.setText(content)
    element.setShowLabel(False)
    parent.addChildElement(element)
    return element


def configure_draft_attribute_form(layer, profile):
    """Configure the native feature attribute popup for a new SOSI layer.

    The layer must originate from our new-data wizard. Imported SOSI layers
    remain untouched. The actual field names used for export never change.
    """
    from qgis.core import (
        QgsAttributeEditorContainer, QgsAttributeEditorField,
        QgsEditorWidgetSetup, Qgis,
    )

    rules = list(profile["fields"])
    for rule in rules:
        index = layer.fields().indexFromName(rule["path"])
        if index < 0:
            raise ValueError("Arbeidslaget mangler SOSI-feltet " + rule["path"])
        guide = field_guidance(rule, profile)
        layer.setFieldAlias(index, guide["alias"])
        if is_area_plan(profile) and rule["path"] == "VERTNIV":
            # ValueMap stores the exact SOSI code as a string (field is text).
            # Do not assign a default or guess a value from the geometry.
            layer.setEditorWidgetSetup(
                index, QgsEditorWidgetSetup(
                    "ValueMap", {"map": [{title: code} for title, code
                                        in VERTICAL_LEVELS]}))

    config = layer.editFormConfig()
    config.clearTabs()
    config.setLayout(Qgis.AttributeFormLayout.DragAndDrop)

    entry_tab = QgsAttributeEditorContainer("Registrer objekt", None)
    entry_tab.setType(Qgis.AttributeEditorContainerType.Tab)
    _add_text(entry_tab, "introduksjon", helper_summary(profile))
    for rule in rules:
        idx = layer.fields().indexFromName(rule["path"])
        guide = field_guidance(rule, profile)
        entry_tab.addChildElement(QgsAttributeEditorField(rule["path"], idx, entry_tab))
        _add_text(entry_tab, "hjelp_" + str(idx), "Hjelp: " + guide["inline"])
        sources = field_source_links(profile, rule["path"])
        if sources:
            # Links appear immediately below OBJTYPE/REGFORM while editing.
            _add_text(entry_tab, "kilder_" + str(idx), link_markup(sources))
    config.addTab(entry_tab)

    help_tab = QgsAttributeEditorContainer("Hjelp og koder", None)
    help_tab.setType(Qgis.AttributeEditorContainerType.Tab)
    if is_area_plan(profile):
        _add_text(help_tab, "planmerknad",
                  "VIKTIG: Denne prøveprofilen gjelder REGFORM i eldre planer "
                  "(PBL 1985). Nyere planer (PBL 2008) bruker blant annet "
                  "RPAREALFORMÅL og et annet objektskjema. Ikke skriv inn "
                  "nyere RpArealformål-koder i REGFORM; velg riktig "
                  "produktspesifikasjon før leveranse.")
    for rule in rules:
        guide = field_guidance(rule, profile)
        _add_text(help_tab, "felt_" + rule["path"].replace(".", "_"),
                  guide["alias"] + "\n" + guide["inline"] + "\n" + guide["details"])
        sources = field_source_links(profile, rule["path"])
        if sources:
            _add_text(help_tab, "oppslag_" + rule["path"].replace(".", "_"),
                      "Offisielle oppslag: " + link_markup(sources))
    if is_area_plan(profile):
        _add_text(help_tab, "vertikalnivakoder",
                  "VERTNIV-koder:\n" + "\n".join(label for label, _ in VERTICAL_LEVELS))
        _add_text(help_tab, "andre_kilder",
                  "Andre fagkilder: " + link_markup(SOURCE_LINKS))
    _add_text(help_tab, "forbehold",
              "En faglig gyldig SOSI-leveranse krever korrekt objektkatalog, "
              "produktspesifikasjon og uavhengig SOSI-kontroll.")
    config.addTab(help_tab)
    layer.setEditFormConfig(config)
    return layer
