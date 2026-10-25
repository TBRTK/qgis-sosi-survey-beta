# SPDX-License-Identifier: GPL-3.0-or-later
"""Five-stage layout; QGIS 3.44/Qt5 and 4/Qt6 native controls only.

This module only moves UI widgets. SOSI parsing, validation and file
writing remain in the original, separately tested plugin code.
"""
from pathlib import Path

from qgis.PyQt.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QFormLayout, QFrame, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QRadioButton, QScrollArea,
    QTabWidget, QTableWidget, QTextBrowser, QVBoxLayout, QWidget,
)
from qgis.core import QgsVectorLayer
from qgis.gui import QgsMapLayerComboBox
from .workflow_steps import SOURCE_CHOICES

PROFILE_DIR = Path(__file__).parent / "profiles"


def note(message):
    label = QLabel(message)
    label.setWordWrap(True)
    return label


def section(title):
    group = QGroupBox(title)
    group.setLayout(QVBoxLayout())
    return group


def build_ui(d, iface, text_selectable, header_stretch, select_rows, no_edit):
    """Populate all old widget fields plus guided navigation."""
    outer = QVBoxLayout(d)
    outer.addWidget(note(
        "SOSI Survey – BETA. BRUK PÅ EGET ANSVAR. "
        "Intern delkontroll er ikke Kartverkets SOSI-kontroll. "
        "Brukeren må kontrollere alle data før levering. "
        "Se DISCLAIMER.txt for garanti- og ansvarsbegrensning."))
    d.tabs = QTabWidget()
    outer.addWidget(d.tabs, 1)

    # START: one choice, one next action.
    start_page = QWidget()
    start = QVBoxLayout(start_page)
    start.addWidget(note("Hva ønsker du å gjøre? Velg ett startpunkt."))
    group = section("Velg arbeidsmåte")
    d.source_group = QButtonGroup(d)
    d.source_group.setExclusive(True)
    d.source_buttons = {}
    for index, (key, description) in enumerate(SOURCE_CHOICES.items()):
        radio = QRadioButton(description["title"])
        radio.setToolTip(description["description"])
        d.source_buttons[key] = radio
        d.source_group.addButton(radio, index)
        group.layout().addWidget(radio)
        radio.toggled.connect(d.source_choice_changed)
    start.addWidget(group)
    d.source_help = note("")
    start.addWidget(d.source_help)
    begin = QPushButton("Neste: datagrunnlag →")
    begin.clicked.connect(d.next_step)
    start.addWidget(begin)
    start.addStretch(1)
    d.tabs.addTab(start_page, "1. Start")

    # DATA: only one source-action button; advanced metadata is collapsed.
    data_page = QWidget()
    data_layout = QVBoxLayout(data_page)
    scroll = QScrollArea()
    scroll.setFrameShape(getattr(QFrame, "Shape", QFrame).NoFrame)
    scroll.setWidgetResizable(True)
    data_body = QWidget()
    data = QVBoxLayout(data_body)
    data.setSpacing(11)
    source_group = section("Velg eller importer datagrunnlaget")
    d.source_instruction = note("")
    source_group.layout().addWidget(d.source_instruction)
    d.source_action = QPushButton("Åpne SOSI-fil …")
    d.source_action.clicked.connect(d.perform_source_action)
    source_group.layout().addWidget(d.source_action)
    d.building_outline_button = QPushButton(
        "Lag bygningsomriss fra markerte hushjørner …")
    d.building_outline_button.clicked.connect(d.create_building_outline)
    d.building_outline_button.setVisible(False)
    source_group.layout().addWidget(d.building_outline_button)
    d.import_info = note("")
    source_group.layout().addWidget(d.import_info)
    d.layer = QgsMapLayerComboBox()
    if isinstance(iface.activeLayer(), QgsVectorLayer):
        d.layer.setLayer(iface.activeLayer())
    source_form = QFormLayout()
    source_form.addRow("QGIS-lag", d.layer)
    source_group.layout().addLayout(source_form)
    d.data_summary = note("Ingen aktivt valgt datagrunnlag.")
    source_group.layout().addWidget(d.data_summary)
    d.selected = QCheckBox(
        "Bare markerte objekter (ved SOSI-import kontrolleres hele filen)")
    source_group.layout().addWidget(d.selected)
    data.addWidget(source_group)

    profile_group = section("Velg SOSI-leveranseprofil")
    combo_row = QHBoxLayout()
    d.profile_combo = QComboBox()
    combo_row.addWidget(d.profile_combo, 1)
    basis = QPushButton("Profilgrunnlag …")
    basis.clicked.connect(d.show_profile_basis)
    combo_row.addWidget(basis)
    load = QPushButton("Åpne profil …")
    load.clicked.connect(d.load_custom_profile)
    combo_row.addWidget(load)
    profile_group.layout().addLayout(combo_row)
    d.profile_description = note("")
    profile_group.layout().addWidget(d.profile_description)
    d.required_fields_label = note("")
    profile_group.layout().addWidget(d.required_fields_label)
    data.addWidget(profile_group)

    coords = section("Kontroller koordinater og høyder")
    cf = QFormLayout()
    d.crs_info = note("Velg et QGIS-lag for koordinatopplysninger.")
    cf.addRow("Koordinatsystem", d.crs_info)
    d.height = QComboBox()
    d.height.addItems([
        "Velg høydegrunnlag", "NN2000", "NN54", "ELLIP", "LOKAL"])
    cf.addRow("Høydegrunnlag", d.height)
    coords.layout().addLayout(cf)
    d.height_confirmed = QCheckBox(
        "Jeg har kontrollert at Z-verdiene er i dette høydegrunnlaget")
    coords.layout().addWidget(d.height_confirmed)
    d.height.currentIndexChanged.connect(
        lambda: d.height_confirmed.setChecked(False))
    data.addWidget(coords)

    d.advanced_toggle = QCheckBox(
        "Vis avanserte eksportinnstillinger og metadata")
    data.addWidget(d.advanced_toggle)
    d.advanced_panel = QGroupBox("Avanserte innstillinger")
    af = QFormLayout(d.advanced_panel)
    d.unit = QComboBox()
    for label, number in (
        ("1 cm", 0.01), ("1 mm", 0.001), ("10 cm", 0.1), ("1 m", 1.0)):
        d.unit.addItem(label, number)
    af.addRow("Koordinatoppløsning", d.unit)
    d.encoding = QComboBox()
    d.encoding.addItems(["ISO8859-10", "UTF-8"])
    af.addRow("Tegnsett", d.encoding)
    d.producer, d.owner = QLineEdit(), QLineEdit()
    d.catalogue, d.catalogue_version = QLineEdit(), QLineEdit()
    af.addRow("Produsent", d.producer)
    af.addRow("Dataeier", d.owner)
    af.addRow("Objektkatalogens kortnavn", d.catalogue)
    af.addRow("Objektkatalogens versjon", d.catalogue_version)
    d.header_info = note("")
    d.header_info.setTextInteractionFlags(text_selectable)
    af.addRow("SOSI-filhode", d.header_info)
    af.addRow(note(
        "Ingen automatisk koordinat- eller høydetransformasjon utføres. "
        "Alle koder og mottakerkrav må vurderes mot riktig spesifikasjon."))
    d.advanced_panel.setVisible(False)
    d.advanced_toggle.toggled.connect(d.advanced_panel.setVisible)
    data.addWidget(d.advanced_panel)
    data.addStretch(1)
    scroll.setWidget(data_body)
    data_layout.addWidget(scroll)
    d.tabs.addTab(data_page, "2. Datagrunnlag")

    # SOSI FIELDS: mapping and editing are two subtabs, one main stage.
    fields_page = QWidget()
    fields_layout = QVBoxLayout(fields_page)
    fields_layout.addWidget(note(
        "Koble kolonner til SOSI-egenskaper, og fyll inn manglende verdier. "
        "Målekoder fra mottakeren er ikke automatisk SOSI-objekttyper."))
    d.field_tabs = QTabWidget()
    fields_layout.addWidget(d.field_tabs, 1)
    mapping_page = QWidget()
    mapping_layout = QVBoxLayout(mapping_page)
    mapping_layout.addWidget(note(
        "Fellesverdi brukes kun hvis kildefeltet mangler en verdi. "
        "* = obligatorisk i valgt profil."))
    d.mapping = QTableWidget(0, 4)
    d.mapping.setHorizontalHeaderLabels([
        "SOSI-felt", "Krav/type", "Kildefelt", "Fellesverdi ved tomt felt"])
    d.mapping.horizontalHeader().setSectionResizeMode(header_stretch)
    mapping_layout.addWidget(d.mapping, 1)
    d.prepare_button = QPushButton(
        "Opprett eksportkopi → Fyll inn og rett")
    d.prepare_button.clicked.connect(d.prepare)
    mapping_layout.addWidget(d.prepare_button)
    mapping_layout.addWidget(note(
        "Ny eksportkopi erstatter rettelser i den forrige eksportkopien, "
        "men endrer ikke kildelaget."))
    d.field_tabs.addTab(mapping_page, "A. Koble kildefelt")

    edit_page = QWidget()
    edit = QVBoxLayout(edit_page)
    edit.addWidget(note(
        "Endre bare eksportkopien. Klikk en rad for å markere objektet "
        "i kartet. Røde celler må rettes før eksport."))
    d.values = QTableWidget()
    d.values.setSelectionBehavior(select_rows)
    d.values.cellClicked.connect(d.select_record)
    d.values.itemChanged.connect(d.values_changed)
    edit.addWidget(d.values, 1)
    fill_row = QHBoxLayout()
    d.fill_field = QComboBox()
    d.fill_value = QLineEdit()
    d.fill_value.setPlaceholderText("Verdi")
    d.fill_selected = QCheckBox("Bare markerte rader")
    fill = QPushButton("Fyll tomme celler")
    fill.clicked.connect(d.fill_empty)
    for item in (d.fill_field, d.fill_value, d.fill_selected, fill):
        fill_row.addWidget(item)
    edit.addLayout(fill_row)
    d.fill_help = note("")
    d.fill_help.setTextInteractionFlags(text_selectable)
    edit.addWidget(d.fill_help)
    d.fill_field.currentIndexChanged.connect(d.update_fill_help)
    check = QPushButton("Kontroller eksportkopien →")
    check.clicked.connect(d.check)
    edit.addWidget(check)
    d.field_tabs.addTab(edit_page, "B. Fyll inn og rett")
    d.field_tabs.setTabEnabled(1, False)
    d.tabs.addTab(fields_page, "3. SOSI-felt")

    # CONTROL: existing control table, unchanged verification behavior.
    check_page = QWidget()
    check_layout = QVBoxLayout(check_page)
    d.summary = note("Ingen kontroll kjørt.")
    check_layout.addWidget(d.summary)
    d.report = QTableWidget(0, 5)
    d.report.setHorizontalHeaderLabels([
        "Nivå", "Objekt-ID", "Felt", "Regel", "Melding"])
    d.report.setEditTriggers(no_edit)
    d.report.horizontalHeader().setSectionResizeMode(4, header_stretch)
    d.report.cellClicked.connect(d.select_issue)
    check_layout.addWidget(d.report, 1)
    d.change_summary = QTextBrowser()
    d.change_summary.setMaximumHeight(145)
    d.change_summary.setPlaceholderText(
        "Endringsrapport etter bestått kontroll.")
    check_layout.addWidget(d.change_summary)
    control_buttons = QHBoxLayout()
    recheck = QPushButton("Kjør kontroll på nytt")
    recheck.clicked.connect(d.check)
    control_buttons.addWidget(recheck)
    select_errors = QPushButton("Marker objekter med feil")
    select_errors.clicked.connect(d.select_errors)
    control_buttons.addWidget(select_errors)
    check_layout.addLayout(control_buttons)
    d.tabs.addTab(check_page, "4. Kontroll")

    # EXPORT: no mixing of export actions into error tables.
    final_page = QWidget()
    final = QVBoxLayout(final_page)
    final.addWidget(note(
        "Prøveeksport og rapport. Bestått intern kontroll betyr ikke "
        "godkjent faglig SOSI-leveranse."))
    d.export_state = note(
        "Opprett eksportkopi og kjør intern kontroll før eksport.")
    final.addWidget(d.export_state)
    export_buttons = QHBoxLayout()
    d.save_report_button = QPushButton("Lagre kontrollrapport …")
    d.save_report_button.clicked.connect(d.save_report)
    export_buttons.addWidget(d.save_report_button)
    d.export_button = QPushButton("Eksporter SOSI-prøvefil …")
    d.export_button.clicked.connect(d.export)
    export_buttons.addWidget(d.export_button)
    final.addLayout(export_buttons)
    final.addWidget(note(
        "Kontroller prøvefilen eksternt med riktig SOSI-produktspesifikasjon "
        "og mottakerkrav. Originalfiler overskrives ikke."))
    final.addStretch(1)
    d.tabs.addTab(final_page, "5. Eksport")

    d.status = note("Velg startpunkt. Originaldata beholdes.")
    outer.addWidget(d.status)
    nav = QHBoxLayout()
    d.progress = QLabel("Steg 1 av 5")
    nav.addWidget(d.progress)
    nav.addStretch(1)
    d.back_button = QPushButton("← Tilbake")
    d.back_button.clicked.connect(d.previous_step)
    nav.addWidget(d.back_button)
    d.next_button = QPushButton("Neste →")
    d.next_button.clicked.connect(d.next_step)
    nav.addWidget(d.next_button)
    outer.addLayout(nav)
    support = QLabel(
        '<a href="https://buymeacoffee.com/tb_rtk">Buy me a coffee – '
        'støtt utviklingen</a> (frivillig)')
    support.setOpenExternalLinks(True)
    outer.addWidget(support)
    close = QPushButton("Lukk")
    close.clicked.connect(d.close)
    outer.addWidget(close)

    for path in sorted(PROFILE_DIR.glob("*.json"), key=lambda p: (
            p.name != "bygg_anlegg.json", p.name)):
        d.add_profile(path)
    d.profile_combo.currentIndexChanged.connect(d.profile_changed)
    d.layer.layerChanged.connect(d.layer_changed)
    d.tabs.currentChanged.connect(d.on_step_changed)
    d.profile_changed()
    d.layer_changed()
    d.source_buttons["sosi"].setChecked(True)
    d.source_choice_changed()
    d._layout_ready = True
    d.refresh_navigation()
