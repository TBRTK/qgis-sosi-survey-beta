# SPDX-License-Identifier: GPL-3.0-or-later
"""Qt5/Qt6 dialog for a restricted, reviewable export workflow."""
import json
import os
from pathlib import Path
import tempfile
from copy import deepcopy
from dataclasses import asdict

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QAction, QColor, QBrush, QIcon
from qgis.PyQt.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QHeaderView, QAbstractItemView, QTextBrowser,
)
from qgis.core import QgsVectorLayer, QgsProject, QgsWkbTypes
from qgis.gui import QgsMapLayerComboBox
from .adapter import collect
from .core import Settings, Issue, blank, render, validate, validate_profile
from .importer import read_sosi
from .roundtrip import render_preserved, header_details
from .audit import complete_records, verify_bytes, write_verified, change_report, changes
from .workflow_steps import SOURCE_CHOICES, enabled_steps, next_step as route_next, export_is_ready
from .ui_layout import build_ui


PROFILE_DIR = Path(__file__).parent / "profiles"

# Qt 5 (QGIS 3.44 LTR) and Qt 6 (QGIS 4) expose enums differently.
TEXT_SELECTABLE = getattr(Qt, "TextInteractionFlag", Qt).TextSelectableByMouse
ITEM_EDITABLE = getattr(Qt, "ItemFlag", Qt).ItemIsEditable
HEADER_STRETCH = getattr(QHeaderView, "ResizeMode", QHeaderView).Stretch
SELECT_ROWS = getattr(QAbstractItemView, "SelectionBehavior", QAbstractItemView).SelectRows
NO_EDIT = getattr(QAbstractItemView, "EditTrigger", QAbstractItemView).NoEditTriggers
MESSAGE_YES = getattr(QMessageBox, "StandardButton", QMessageBox).Yes
MESSAGE_NO = getattr(QMessageBox, "StandardButton", QMessageBox).No


def atomic_new_text(path, text, encoding="utf-8"):
    """Do not replace an existing delivery or leave partial files on failure."""
    path = Path(path)
    fd, temp = tempfile.mkstemp(prefix=".sosi_", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="\n") as handle:
            handle.write(text)
        # Hard link gives exclusive destination creation on supported local FS.
        # On Windows rename also fails if destination already exists.
        if os.name == "nt":
            os.rename(temp, path)
        else:
            os.link(temp, path)
            os.unlink(temp)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


class SosiPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self._beta_notice_accepted = False

    def initGui(self):
        icon_path = Path(__file__).parent / "icon.svg"
        self.action = QAction(QIcon(str(icon_path)),
                              "SOSI Survey – importer, kontroller og eksporter",
                              self.iface.mainWindow())
        self.action.setToolTip("Åpne SOSI Survey")
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu("SOSI Survey", self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        self.iface.removePluginMenu("SOSI Survey", self.action)
        self.iface.removeToolBarIcon(self.action)
        if self.dialog:
            self.dialog.close()
            self.dialog.deleteLater()
        self.action.deleteLater()

    def run(self):
        # One explicit warning per QGIS session. This is an information and
        # consent-to-continue step, not an attempt to limit statutory rights.
        if not self._beta_notice_accepted:
            answer = QMessageBox.question(
                self.iface.mainWindow(),
                "SOSI Survey BETA – bruk på eget ansvar",
                "SOSI Survey er et eksperimentelt verktøy. Bruk på eget ansvar.\n\n"
                "Import, SOSI-data, koordinater, koder og eksport kan inneholde feil. "
                "Intern «BESTÅTT» er ikke offisiell SOSI-kontroll.\n\n"
                "Du er ansvarlig for å kontrollere data mot originalmålinger, "
                "riktig produktspesifikasjon og mottakerens krav før levering.\n\n"
                "Programvaren leveres AS IS uten garanti. Utvikleren og "
                "bidragsytere fraskriver seg ansvar for feil, tap og skade "
                "bare så langt GPLv3 §§ 15–17 og gjeldende rett tillater. "
                "Se DISCLAIMER.txt for full tekst.\n\n"
                "Har du lest dette og ønsker å fortsette med testversjonen?",
                MESSAGE_YES | MESSAGE_NO, MESSAGE_NO)
            if answer != MESSAGE_YES:
                return
            self._beta_notice_accepted = True
        if self.dialog is None:
            self.dialog = ExportDialog(self.iface)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()


class ExportDialog(QDialog):
    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.setWindowTitle("SOSI Survey – utviklingsversjon for QGIS 3.44/4")
        self.resize(1150, 760)
        self.records = []
        self.issues = []
        self.snapshot_layer = None
        self.snapshot_document = None
        self.last_audit = None
        self.baseline_records = []
        self._value_texts = {}
        self.profile = None
        self.profiles = []
        self._layout_ready = False
        build_ui(self, iface, TEXT_SELECTABLE, HEADER_STRETCH, SELECT_ROWS, NO_EDIT)
        return
        outer = QVBoxLayout(self)
        notice = QLabel("UTKAST • SOSI i 2D/3D • Innebygd delkontroll, ikke Kartverkets SOSI-kontroll.\n"
                        "Verdier du fyller inn nedenfor gjelder eksportkopien. Kildelaget endres ikke.")
        notice.setWordWrap(True)
        outer.addWidget(notice)
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs)
        setup = QDialog()
        form = QFormLayout(setup)
        self.new_layer_button = QPushButton("Veiviser – opprett nytt SOSI-arbeidslag …")
        self.new_layer_button.clicked.connect(self.create_sosi_work_layer)
        form.addRow(self.new_layer_button)
        self.import_field_button = QPushButton("1. Importer feltmålinger fra CSV – valgfri mottaker …")
        self.import_field_button.clicked.connect(self.import_field_csv)
        form.addRow(self.import_field_button)
        self.use_layer_button = QPushButton("2. Bruk eksisterende QGIS-punktlag …")
        self.use_layer_button.clicked.connect(self.use_existing_field_layer)
        form.addRow(self.use_layer_button)
        field_help = QLabel("Alle feltmålinger beholdes i et separat GeoPackage. "
                            "ID, Code og Description kopieres til egne attributter; "
                            "feltkoder oversettes aldri automatisk til SOSI-OBJTYPE.")
        field_help.setWordWrap(True)
        form.addRow(field_help)
        self.building_outline_button = QPushButton(
            "3. Bygg bygningsomriss av markerte hushjørner …")
        self.building_outline_button.clicked.connect(self.create_building_outline)
        form.addRow(self.building_outline_button)
        self.import_button = QPushButton("Importer SOSI-fil …")
        self.import_button.clicked.connect(self.import_sosi)
        form.addRow(self.import_button)
        self.import_info = QLabel("Import av PUNKT, KURVE, BUEP og FLATE i 2D/3D, med referanser/hull. TEKST/SYMBOL vises som posisjoner. Origo og høydeenheter leses fra filhodet.\n"
                                  "Høyder, koordinatoppløsning og øvrige egenskaper bevares ved eksport. Ikke støttede filer stoppes. Originalfilen beholdes.")
        self.import_info.setWordWrap(True)
        form.addRow(self.import_info)
        self.layer = QgsMapLayerComboBox()
        if isinstance(iface.activeLayer(), QgsVectorLayer):
            self.layer.setLayer(iface.activeLayer())
        form.addRow("QGIS-lag", self.layer)
        self.selected = QCheckBox("Bare valgte objekter i eksportkopien (SOSI-import: hele filen kontrolleres og eksporteres)")
        form.addRow(self.selected)
        self.profile_combo = QComboBox()
        profile_row = QHBoxLayout()
        profile_row.addWidget(self.profile_combo)
        add_profile = QPushButton("Åpne profil …")
        add_profile.clicked.connect(self.load_custom_profile)
        profile_row.addWidget(add_profile)
        profile_basis = QPushButton("Profilgrunnlag …")
        profile_basis.clicked.connect(self.show_profile_basis)
        profile_row.addWidget(profile_basis)
        form.addRow("Leveranseprofil", profile_row)
        self.profile_description = QLabel()
        self.profile_description.setWordWrap(True)
        form.addRow(self.profile_description)
        self.required_fields_label = QLabel()
        self.required_fields_label.setWordWrap(True)
        form.addRow("Felt som kreves av profilen", self.required_fields_label)
        self.height = QComboBox()
        self.height.addItems(["Velg høydegrunnlag", "NN2000", "NN54", "ELLIP", "LOKAL"])
        form.addRow("Høydegrunnlag for Z", self.height)
        self.height_confirmed = QCheckBox("Jeg har kontrollert at Z-verdiene er i valgt høydegrunnlag")
        form.addRow(self.height_confirmed)
        self.height.currentIndexChanged.connect(lambda: self.height_confirmed.setChecked(False))
        self.unit = QComboBox()
        for label, value in (("1 cm", 0.01), ("1 mm", 0.001), ("10 cm", 0.1), ("1 m", 1.0)):
            self.unit.addItem(label, value)
        form.addRow("Koordinatoppløsning", self.unit)
        self.encoding = QComboBox()
        self.encoding.addItems(["ISO8859-10", "UTF-8"])
        form.addRow("Tegnsett (lokalt testet: ISO8859-10)", self.encoding)
        self.producer, self.owner = QLineEdit(), QLineEdit()
        self.catalogue, self.catalogue_version = QLineEdit(), QLineEdit()
        form.addRow("Produsent", self.producer)
        form.addRow("Dataeier", self.owner)
        form.addRow("Objektkatalogens kortnavn", self.catalogue)
        form.addRow("Objektkatalogens versjon", self.catalogue_version)
        self.header_info = QLabel()
        self.header_info.setWordWrap(True)
        self.header_info.setTextInteractionFlags(TEXT_SELECTABLE)
        form.addRow("Originalt SOSI-filhode", self.header_info)
        form.addRow(QLabel("Ingen koordinat- eller høydetransformasjon utføres. Laget må allerede ha korrekt CRS og Z.\n"
                            "GNSS-data kan komme fra ulike mottakere. Kontroller koordinatsystem, Z og høydegrunnlag. SOSI-objekttype og kvalitetskoder velges ut fra leveransen."))
        self.tabs.addTab(setup, "1. Lag og leveranse")
        mapping_page = QDialog()
        mapping_layout = QVBoxLayout(mapping_page)
        mapping_layout.addWidget(QLabel("Koble kildefelt. Fellesverdi brukes bare når kildeverdien mangler. * = påkrevd av valgt profil."))
        self.mapping = QTableWidget(0, 4)
        self.mapping.setHorizontalHeaderLabels(["SOSI-felt", "Krav/type", "Kildefelt", "Fellesverdi ved tomt felt"])
        self.mapping.horizontalHeader().setSectionResizeMode(HEADER_STRETCH)
        mapping_layout.addWidget(self.mapping)
        prepare = QPushButton("Lag ny eksportkopi fra laget →")
        prepare.clicked.connect(self.prepare)
        mapping_layout.addWidget(prepare)
        mapping_layout.addWidget(QLabel("Ny eksportkopi erstatter eventuelle rettelser i forrige eksportkopi. Ingen verdier gjettes fra instrumentnavnet."))
        self.tabs.addTab(mapping_page, "2. Koble felt")
        edit_page = QDialog()
        edit_layout = QVBoxLayout(edit_page)
        edit_layout.addWidget(QLabel("Rediger verdier direkte. Klikk en rad for å markere objektet i kartet. Røde celler har feil."))
        self.values = QTableWidget()
        self.values.setSelectionBehavior(SELECT_ROWS)
        self.values.cellClicked.connect(self.select_record)
        self.values.itemChanged.connect(self.values_changed)
        edit_layout.addWidget(self.values)
        fill_row = QHBoxLayout()
        self.fill_field = QComboBox()
        self.fill_value = QLineEdit()
        self.fill_value.setPlaceholderText("Verdi for valgt felt")
        self.fill_selected = QCheckBox("Bare markerte rader")
        fill = QPushButton("Fyll tomme celler")
        fill.clicked.connect(self.fill_empty)
        for widget in (self.fill_field, self.fill_value, self.fill_selected, fill):
            fill_row.addWidget(widget)
        edit_layout.addLayout(fill_row)
        self.fill_help = QLabel()
        self.fill_help.setWordWrap(True)
        self.fill_help.setTextInteractionFlags(TEXT_SELECTABLE)
        edit_layout.addWidget(self.fill_help)
        self.fill_field.currentIndexChanged.connect(self.update_fill_help)
        check = QPushButton("Kontroller eksportkopien →")
        check.clicked.connect(self.check)
        edit_layout.addWidget(check)
        self.tabs.addTab(edit_page, "3. Fyll inn og rett")
        report_page = QDialog()
        report_layout = QVBoxLayout(report_page)
        self.summary = QLabel("Ingen kontroll kjørt.")
        self.summary.setWordWrap(True)
        report_layout.addWidget(self.summary)
        self.report = QTableWidget(0, 5)
        self.report.setHorizontalHeaderLabels(["Nivå", "Objekt-ID", "Felt", "Regel", "Melding"])
        self.report.setEditTriggers(NO_EDIT)
        self.report.horizontalHeader().setSectionResizeMode(4, HEADER_STRETCH)
        self.report.cellClicked.connect(self.select_issue)
        report_layout.addWidget(self.report)
        self.change_summary = QTextBrowser()
        self.change_summary.setMaximumHeight(150)
        self.change_summary.setPlaceholderText("Endringsrapport vises etter kontroll uten feil.")
        report_layout.addWidget(self.change_summary)
        buttons = QHBoxLayout()
        for text, handler in (("Marker alle objekter med feil", self.select_errors),
                              ("Lagre kontrollrapport …", self.save_report),
                              ("Eksporter prøvefil …", self.export)):
            button = QPushButton(text)
            button.clicked.connect(handler)
            buttons.addWidget(button)
        report_layout.addLayout(buttons)
        self.tabs.addTab(report_page, "4. Kontroll og eksport")
        self.status = QLabel("Velg lag, profil og feltkoblinger. Originaldata beholdes.")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)
        support = QLabel('<a href="https://buymeacoffee.com/tb_rtk">Buy me a coffee – støtt utviklingen</a> (frivillig)')
        support.setOpenExternalLinks(True)
        outer.addWidget(support)
        close = QPushButton("Lukk")
        close.clicked.connect(self.close)
        outer.addWidget(close)
        for path in sorted(PROFILE_DIR.glob("*.json"), key=lambda p: (p.name != "bygg_anlegg.json", p.name)):
            self.add_profile(path)
        self.profile_combo.currentIndexChanged.connect(self.profile_changed)
        self.layer.layerChanged.connect(self.layer_changed)
        self.profile_changed()
        self.layer_changed()

    def selected_source(self):
        return next((key for key, radio in self.source_buttons.items()
                     if radio.isChecked()), 'sosi')

    def source_choice_changed(self, *_):
        if not hasattr(self, 'source_buttons'):
            return
        kind = self.selected_source()
        entry = SOURCE_CHOICES[kind]
        self.source_help.setText(entry['description'])
        self.source_instruction.setText(entry['description'])
        self.source_action.setText(entry['action'])
        self.building_outline_button.setVisible(kind in ('csv', 'existing'))
        if getattr(self, '_layout_ready', False):
            self.refresh_navigation()

    def perform_source_action(self):
        kind = self.selected_source()
        handlers = {'sosi': self.import_sosi, 'csv': self.import_field_csv,
                    'existing': self.use_existing_field_layer,
                    'new': self.create_sosi_work_layer}
        handlers[kind]()

    def _has_layer(self):
        layer = self.layer.currentLayer()
        return isinstance(layer, QgsVectorLayer) and layer.isValid()

    def _audit_ready(self):
        return export_is_ready(self.issues, self.last_audit)

    def refresh_navigation(self):
        if not getattr(self, '_layout_ready', False):
            return
        available = enabled_steps(has_layer=self._has_layer(),
                                  has_copy=self.snapshot_layer is not None,
                                  audit_ok=self._audit_ready())
        for index, allowed in enumerate(available):
            self.tabs.setTabEnabled(index, allowed)
        position = self.tabs.currentIndex()
        self.progress.setText(f'Steg {position + 1} av 5')
        self.back_button.setEnabled(position > 0)
        self.next_button.setEnabled(position < 4 and available[position + 1])
        self.export_button.setEnabled(self._audit_ready())
        self.save_report_button.setEnabled(self.snapshot_layer is not None)
        if self._has_layer():
            layer = self.layer.currentLayer()
            dimension = '3D' if QgsWkbTypes.hasZ(layer.wkbType()) else '2D'
            self.data_summary.setText(
                f'{layer.name()} • {layer.featureCount()} objekter • {dimension} • '
                f'{layer.crs().authid()}')
            self.crs_info.setText(layer.crs().authid())
        else:
            self.data_summary.setText('Velg eller importer et gyldig lag.')
            self.crs_info.setText('Ukjent')
        self.export_state.setText(
            'Intern gjeninnlesing bestått. Klar for prøveeksport; '
            'ekstern SOSI-kontroll gjenstår.'
            if self._audit_ready() else
            'Eksport er sperret til intern kontroll er bestått.')

    def on_step_changed(self, *_):
        self.refresh_navigation()

    def previous_step(self):
        if self.tabs.currentIndex() > 0:
            self.tabs.setCurrentIndex(self.tabs.currentIndex() - 1)

    def next_step(self):
        index = self.tabs.currentIndex()
        try:
            position = route_next(index, has_layer=self._has_layer(),
                                  has_copy=self.snapshot_layer is not None,
                                  audit_ok=self._audit_ready())
            self.tabs.setCurrentIndex(position)
        except ValueError as error:
            self.error(error)

    @staticmethod
    def fixed_item(text):
        item = QTableWidgetItem(str(text))
        item.setFlags(item.flags() & ~ITEM_EDITABLE)
        return item

    def error(self, error):
        QMessageBox.warning(self, "SOSI Survey", str(error))

    def create_sosi_work_layer(self):
        if not self.profile:
            self.error("Velg en SOSI-leveranseprofil før du oppretter nye data.")
            return
        try:
            from .new_data_wizard import create_new_sosi_layer
            layer = create_new_sosi_layer(self, self.profile)
            if layer is None:
                return
            self.layer.setLayer(layer)
            self.layer_changed()
            if hasattr(self.iface, 'setActiveLayer'):
                self.iface.setActiveLayer(layer)
            self.tabs.setCurrentIndex(2)
            self.status.setText("Nytt redigerbart arbeidslag er opprettet. Tegn objektene i kartet, "
                                "fyll inn korrekte egenskaper og fortsett til fane 2. "
                                "Lagre minnelaget i GeoPackage hvis du vil beholde det.")
        except Exception as error:
            self.error(error)

    def import_field_csv(self):
        if not self.profile:
            self.error("Velg leveranseprofil før du importerer feltmålinger.")
            return
        try:
            from .field_import_qgis import run_csv_import
            layer = run_csv_import(self, self.profile)
            if layer is None:
                return
            self.layer.setLayer(layer)
            self.layer_changed()
            height = layer.customProperty('sosi_survey/source_height_reference', '')
            if height:
                index = self.height.findText(height)
                if index >= 0:
                    self.height.setCurrentIndex(index)
            self.height_confirmed.setChecked(False)
            if hasattr(self.iface, 'setActiveLayer'):
                self.iface.setActiveLayer(layer)
            self.status.setText(
                f"Importert {layer.featureCount()} feltpunkter til GeoPackage. "
                "Original CSV er uendret. Sjekk SOSI-feltkobling i fane 2, "
                "fyll inn manglende SOSI-egenskaper i fane 3, og kontroller "
                "før eksport. Ingen automatisk tolkning av mottakerens koder.")
            self.tabs.setCurrentIndex(1)
        except (OSError, UnicodeError, ValueError, RuntimeError) as error:
            self.error(error)

    def use_existing_field_layer(self):
        try:
            from .field_import_qgis import check_existing_point_layer
            layer = self.iface.activeLayer() if hasattr(self.iface, 'activeLayer') else None
            if layer is None:
                layer = self.layer.currentLayer()
            layer = check_existing_point_layer(layer)
            self.layer.setLayer(layer)
            self.layer_changed()
            self.tabs.setCurrentIndex(1)
            self.status.setText(
                "Eksisterende punktlag valgt uten å endre kildedata. "
                "Koble felt i fane 2. Bekreft høydegrunnlaget ved 3D "
                "og velg SOSI-objekttype etter leveransekrav.")
        except ValueError as error:
            self.error(error)

    def create_building_outline(self):
        try:
            profile_index = next(
                (index for index, entry in enumerate(self.profiles)
                 if entry.get('id') == 'bygning_plassering_utkast'), None)
            if profile_index is None:
                raise ValueError('Bygningsprofilen mangler i SOSI Survey-installasjonen.')
            from .building_outline_qgis import run_building_outline
            preferred = self.iface.activeLayer() if hasattr(
                self.iface, 'activeLayer') else self.layer.currentLayer()
            layer = run_building_outline(
                self, preferred, self.profiles[profile_index], self.unit.currentData())
            if layer is None:
                return
            self.profile_combo.setCurrentIndex(profile_index)
            self.layer.setLayer(layer)
            self.layer_changed()
            if hasattr(self.iface, 'setActiveLayer'):
                self.iface.setActiveLayer(layer)
            self.tabs.setCurrentIndex(1)
            self.status.setText(
                "Bygningsomriss lagret som GeoPackage med opprinnelige punkt-ID-er, "
                "rekkefølge, målekoder, beskrivelser og eventuelle høyder. "
                "OBJTYPE er bevisst tom. Velg riktig SOSI-objekttype og "
                "mottakerkrav før eksport. Polygon kan ikke eksporteres med "
                "denne profilens manglende grenseobjekttype.")
        except (OSError, ValueError, RuntimeError) as error:
            self.error(error)

    def import_sosi(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importer SOSI – alle versjoner forsøkes", "", "SOSI (*.sos *.sosi *.SOS *.SOSI);;Alle filer (*)")
        if not path:
            return
        try:
            layers, version = read_sosi(path)
            QgsProject.instance().addMapLayers(layers)
            self.layer.setLayer(layers[0])
            self.layer_changed()
            self.import_info.setText(f"Importert SOSI {version}: {len(layers)} del-lag med originale 2D/3D-dimensjoner.\n"
                                     "Rett felt i eksportkopien. Bevarende eksport bruker originalens koordinater, høyder, tegnsett og SOSI-versjon. "
                                     "Hele originalfilen eksporteres, med uendrede grensekurver og referanser. Ved blandet geometri: bruk ALLE objekter (feltkontroll) for å rette hele filen samlet. "
                                     "Kontrollen gjelder hele eksportfilen, også objekter utenfor valgt del-lag/utvalg. Arbeidskopien ligger i minnet; eksporter før QGIS lukkes. TEKST/SYMBOL vises som posisjoner og etiketter, ikke med original karttegnstandard. Import er ikke fagkontroll.")
            self.status.setText(f"Importert {Path(path).name}. Originalfilen er beholdt. Versjon: {version}.")
            QMessageBox.information(self, "SOSI importert", self.import_info.text())
        except Exception as error:
            self.error(error)

    def update_fill_help(self, *_):
        path = self.fill_field.currentData()
        if not self.profile or not path:
            self.fill_help.setText("Velg felt for å se hva som skal fylles inn.")
            return
        rule = next(r for r in self.profile['fields'] if r['path'] == path)
        help_text = {
            'OBJTYPE': 'Skriv objekttypens nøyaktige navn fra mottakerens objektkatalog, for eksempel typen for målt kum eller kabel. Mottakerens merke eller modell angir ingen objekttype. Ikke gjett kode eller navn.',
            'DATAFANGSTDATO': 'Datoen objektet faktisk ble målt, som ÅÅÅÅ-MM-DD, for eksempel 2026-10-18. Ikke bruk eksportdato hvis målingen ble gjort en annen dag.',
            'KVALITET.MÅLEMETODE': 'Heltallskode for målemetoden fra gjeldende SOSI-/mottakerkodeliste. Velg etter faktisk målemetode; instrumentmodellen alene avgjør ikke koden.',
            'KVALITET.NØYAKTIGHET': 'Dokumentert nøyaktighet i plan, i hele centimeter. Eksempel: 2 betyr 2 cm. Bruk prosjektets krav og måledokumentasjon; ikke antall desimaler i koordinatene.',
            'KVALITET.H-MÅLEMETODE': 'Heltallskode for hvordan høyden ble bestemt, fra mottakerens kodeliste. Høydegrunnlag som NN2000 velges på første fane og er ikke en målemetodekode.',
            'KVALITET.H-NØYAKTIGHET': 'Dokumentert høydenøyaktighet i hele centimeter. Eksempel: 3 betyr 3 cm. Fyll bare felles verdi når den gjelder alle aktuelle målinger.',
            'KVALITET.SYNBARHET': 'Kode for hva som faktisk var synlig ved innmåling. Følg mottakerens kodeliste; ikke gjett ut fra instrument eller høydeverdier.',
        }
        details = rule.get('help') or help_text.get(path) or rule.get('description') or f"Fyll inn {rule.get('label', path)} etter valgt leveranseprofil."
        constraints = ('Påkrevd av valgt profil. ' if rule.get('required') else 'Valgfritt i valgt profil. ') + f"Datatype: {rule['type']}."
        if 'enum' in rule:
            constraints += ' Tillatte verdier: ' + ', '.join(map(str, rule['enum'])) + '.'
        self.fill_help.setText(f"{path}: {details}\n{constraints} Bare tomme celler fylles; eksisterende verdier beholdes. Endringen gjelder eksportkopien. Kjør kontroll etterpå.")

    def add_profile(self, path):
        profile = validate_profile(json.loads(Path(path).read_text(encoding="utf-8-sig")))
        self.profiles.append(profile)
        self.profile_combo.addItem(profile.get("name", Path(path).stem))

    def show_profile_basis(self):
        if not self.profile:
            return
        profile = self.profile
        lines = [profile.get('name', ''), '', profile.get('description', ''),
                 '', 'Status: ' + profile.get('delivery_status', 'Foreløpig prøveprofil.'),
                 '', 'Feltkrav i profilen er bare reglene som er implementert. De er ikke en full leveransespesifikasjon.']
        for heading, key in [('Kildegrunnlag', 'sources'), ('Må avklares før levering', 'unresolved'),
                             ('Arbeidskontroll utenfor feltvalideringen', 'manual_checks')]:
            lines += ['', heading]
            for entry in profile.get(key, []):
                if isinstance(entry, dict):
                    lines += [entry.get('title', ''), entry.get('url', ''), entry.get('note', '')]
                else:
                    lines.append(str(entry))
        lines += ['', 'Full SOSI-kontroll er ikke integrert. Bruk riktig produktspesifikasjon og definisjonsfiler i Kartverkets kontrollprogram.']
        dialog = QDialog(self)
        dialog.setWindowTitle('Profilgrunnlag og gjenstående krav')
        dialog.resize(850, 600)
        layout = QVBoxLayout(dialog)
        browser = QTextBrowser()
        browser.setPlainText('\n'.join(lines))
        layout.addWidget(browser)
        close = QPushButton('Lukk')
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()

    def load_custom_profile(self):
        path, _ = QFileDialog.getOpenFileName(self, "Åpne deklarativ eksportprofil", "", "JSON (*.json)")
        if path:
            try:
                self.add_profile(path)
                self.profile_combo.setCurrentIndex(len(self.profiles) - 1)
            except Exception as error:
                self.error(error)

    def discard_copy(self):
        self.records, self.issues, self.snapshot_layer = [], [], None
        self.snapshot_document, self.last_audit, self.baseline_records = None, None, []
        self.values.setRowCount(0)
        if hasattr(self, 'field_tabs'):
            self.field_tabs.setTabEnabled(1, False)
        self.report.setRowCount(0)
        self.change_summary.clear()
        self.summary.setText("Ingen kontroll kjørt for gjeldende oppsett.")
        self.refresh_navigation()

    def layer_changed(self, *_):
        self.discard_copy()
        self.build_mappings()
        self.height_confirmed.setChecked(False)
        layer = self.layer.currentLayer()
        payload = layer.customProperty('sosi_survey/roundtrip', '') if layer else ''
        for widget in (self.height, self.unit, self.encoding, self.producer, self.owner, self.catalogue, self.catalogue_version):
            widget.setEnabled(not bool(payload))
            widget.setToolTip('Bevarende eksport bruker filhodet og koordinatenhetene fra originalen.' if payload else '')
        if payload:
            document = json.loads(payload)
            details = header_details(document)
            for combo, value, is_data in ((self.height, details['height'], False),
                                          (self.encoding, details['encoding'], False),
                                          (self.unit, details['unit'], True)):
                index = combo.findData(value) if is_data else combo.findText(value)
                if index < 0:
                    combo.addItem(f"{value:g} m (original)" if is_data else value, value)
                    index = combo.count() - 1
                combo.setCurrentIndex(index)
            for widget, key in ((self.producer,'producer'),(self.owner,'owner'),
                                (self.catalogue,'catalogue'),(self.catalogue_version,'catalogue_version')):
                widget.setText(details[key])
            self.header_info.setText(f"SOSI {details['version']} • {details['crs']} • {details['height'] or 'høydegrunnlag mangler'}\n"
                                     f"Planenhet {details['unit']:g} m • høydeenhet {details['h_unit']:g} m • origo NØ {details['origin_ne']} • {details['encoding']}\n"
                                     "Filhodet bevares. Bekreft at høydegrunnlaget stemmer med målingene.")
        else:
            self.header_info.setText('Ingen bevart SOSI-original. Eksport bruker innstillingene ovenfor.')
        self.refresh_navigation()

    def profile_changed(self, *_):
        if not self.profiles:
            return
        self.discard_copy()
        self.profile = self.profiles[self.profile_combo.currentIndex()]
        self.profile_description.setText(self.profile.get("description", "Foreløpig profil."))
        fields = [rule.get('label', rule['path']) for rule in self.profile['fields'] if rule.get('required')]
        self.required_fields_label.setText(
            (', '.join(fields) if fields else 'Ingen') +
            '. Dette er bare krav i valgt prøveprofil, ikke en full SOSI-produktkontroll.')
        self.build_mappings()

    def build_mappings(self):
        if not self.profile:
            return
        layer = self.layer.currentLayer()
        fields = [f.name() for f in layer.fields()] if isinstance(layer, QgsVectorLayer) else []
        self.mapping.setRowCount(len(self.profile["fields"]))
        self.fill_field.clear()
        for row, rule in enumerate(self.profile["fields"]):
            path = rule["path"]
            self.mapping.setItem(row, 0, self.fixed_item(path))
            self.mapping.setItem(row, 1, self.fixed_item(("* " if rule.get("required") else "") + rule["type"]))
            combo = QComboBox()
            combo.addItem("— ingen —", "")
            for field in fields:
                combo.addItem(field, field)
            candidates = {path.casefold(), path.replace(".", "_").casefold()}
            aliases = {'OBJTYPE': 'objekttypenavn', 'DATAFANGSTDATO': 'datafangstdato',
                       'KVALITET.MÅLEMETODE': 'målemetode', 'KVALITET.NØYAKTIGHET': 'nøyaktighet',
                       'KVALITET.H-MÅLEMETODE': 'målemetodeHøyde', 'KVALITET.H-NØYAKTIGHET': 'nøyaktighetHøyde'}
            candidates.add(aliases.get(path, '').casefold())
            matched = next((f for f in fields if f.casefold() in candidates), None)
            if matched:
                combo.setCurrentIndex(fields.index(matched) + 1)
            self.mapping.setCellWidget(row, 2, combo)
            self.mapping.setItem(row, 3, QTableWidgetItem(""))
            self.fill_field.addItem(path, path)
        self.update_fill_help()

    def mappings(self):
        return {rule["path"]: {"field": self.mapping.cellWidget(row, 2).currentData(),
                                "fallback": self.mapping.item(row, 3).text()}
                for row, rule in enumerate(self.profile["fields"])}

    def prepare(self):
        try:
            if self.records:
                answer = QMessageBox.question(self, "Ny eksportkopi", "Erstatt eksportkopien og eventuelle rettelser med data fra laget?",
                                              MESSAGE_YES | MESSAGE_NO,
                                              MESSAGE_NO)
                if answer != MESSAGE_YES:
                    return
            layer = self.layer.currentLayer()
            records = collect(layer, self.profile, self.mappings(), self.selected.isChecked())
            if not records:
                raise ValueError('Ingen objekter i eksportkopien. Velg objekter eller slå av Bare valgte objekter.')
            self.records = records
            self.baseline_records = deepcopy(records)
            self.snapshot_layer = layer
            payload = layer.customProperty('sosi_survey/roundtrip', '')
            self.snapshot_document = json.loads(payload) if payload else None
            self.snapshot_original_file = layer.customProperty('sosi_survey/source_path', '')
            self.last_audit = None
            self.snapshot_crs = layer.crs().authid()
            self.snapshot_source = layer.source()
            self.snapshot_mappings = self.mappings()
            self.snapshot_selected = self.selected.isChecked()
            self.values.setColumnCount(len(self.profile["fields"]) + 1)
            self.values.setHorizontalHeaderLabels(["Objekt-ID"] + [r["path"] for r in self.profile["fields"]])
            self.values.setRowCount(len(records))
            for row, record in enumerate(records):
                source_payload = layer.customProperty('sosi_survey/roundtrip', '')
                source_id = json.loads(source_payload).get('feature_map', {}).get(str(record.fid)) if source_payload else None
                self.values.setItem(row, 0, self.fixed_item(f'{record.kind} :{source_id}' if source_id is not None else record.fid))
                for col, rule in enumerate(self.profile["fields"], 1):
                    value = record.values.get(rule["path"])
                    self.values.setItem(row, col, QTableWidgetItem("" if value is None else str(value)))
            self.values.resizeColumnsToContents()
            self._value_texts = self.value_texts()
            self.issues = []
            self.report.setRowCount(0)
            self.summary.setText("Ny eksportkopi. Kjør kontroll.")
            self.status.setText(f"Eksportkopi: {len(records)} objekter, {self.snapshot_crs}. Endringer gjelder bare kopien.")
            self.field_tabs.setTabEnabled(1, True)
            self.field_tabs.setCurrentIndex(1)
            self.tabs.setCurrentIndex(2)
            self.refresh_navigation()
        except Exception as error:
            self.error(error)

    def settings(self):
        if self.snapshot_document:
            details = header_details(self.snapshot_document)
            return Settings(details['crs'], details['height'], details['unit'], details['producer'],
                            details['owner'], details['catalogue'], details['catalogue_version'],
                            self.height_confirmed.isChecked(), details['encoding'])
        return Settings(self.snapshot_crs, self.height.currentText(), self.unit.currentData(),
                        self.producer.text(), self.owner.text(), self.catalogue.text(),
                        self.catalogue_version.text(), self.height_confirmed.isChecked(), self.encoding.currentText())

    def value_texts(self):
        return {(row,col): self.values.item(row,col).text() if self.values.item(row,col) else ''
                for row in range(self.values.rowCount()) for col in range(1,self.values.columnCount())}

    def values_changed(self, item):
        key = (item.row(), item.column())
        if item.column() > 0 and item.text() != self._value_texts.get(key):
            self._value_texts[key] = item.text()
            self.last_audit = None
            self.change_summary.clear()
            self.summary.setText('Verdier er endret. Kjør kontroll på nytt; eksport kontrollerer alltid på nytt.')
            self.refresh_navigation()

    def all_records(self):
        return complete_records(self.snapshot_document, self.records) if self.snapshot_document else self.records

    def verify_data(self, data):
        audit = verify_bytes(data, self.profile, self.settings(), self.all_records(), self.snapshot_document)
        if not self.snapshot_document:
            before, after = deepcopy(self.baseline_records), deepcopy(self.records)
            for index, (a,b) in enumerate(zip(before,after), 1):
                a.fid = b.fid = index
            audit['changes'] = changes(before,after,self.profile)
        return audit

    def sync_values(self):
        for row, record in enumerate(self.records):
            for col, rule in enumerate(self.profile["fields"], 1):
                record.values[rule["path"]] = self.values.item(row, col).text()

    def fill_empty(self):
        col = self.fill_field.currentIndex() + 1
        value = self.fill_value.text()
        if not value.strip():
            self.error("Skriv verdien som skal brukes i tomme celler.")
            return
        selected_rows = {index.row() for index in self.values.selectionModel().selectedRows()}
        count = 0
        for row in range(self.values.rowCount()):
            if self.fill_selected.isChecked() and row not in selected_rows:
                continue
            item = self.values.item(row, col)
            if blank(item.text()):
                item.setText(value)
                count += 1
        self.status.setText(f"Fylte {count} tomme celler i eksportkopien. Kjør kontroll på nytt.")

    def check(self, *_):
        if self.snapshot_layer is None:
            self.error("Lag eksportkopien i trinn 2 først.")
            return False
        try:
            self.sync_values()
            self.last_audit = None
            records = self.all_records()
            self.issues = validate(records, self.profile, self.settings(), preserved=bool(self.snapshot_document))
            if not any(i.severity == 'FEIL' for i in self.issues):
                try:
                    text, codec = self.export_text()
                    self.last_audit = self.verify_data(text.encode(codec))
                    self.last_audit['disk_readback_verified'] = False
                except Exception as error:
                    self.issues.append(Issue('FEIL', 'GJENINNLESING', str(error)))
            self.report.setRowCount(len(self.issues))
            for row, issue in enumerate(self.issues):
                for col, text in enumerate((issue.severity, "" if issue.fid is None else issue.fid,
                                             issue.attribute, issue.code, issue.message)):
                    self.report.setItem(row, col, self.fixed_item(text))
            invalid = {(i.fid, i.attribute) for i in self.issues if i.severity == "FEIL"}
            for row, record in enumerate(self.records):
                for col, rule in enumerate(self.profile["fields"], 1):
                    item = self.values.item(row, col)
                    serial = int(self.snapshot_document['feature_map'][str(record.fid)]) if self.snapshot_document else record.fid
                    if (serial, rule["path"]) in invalid:
                        item.setBackground(QColor("#ffcccc"))
                        item.setForeground(QColor("#111111"))
                    else:
                        item.setBackground(QBrush())
                        item.setForeground(QBrush())
            count = sum(i.severity == "FEIL" for i in self.issues)
            self.summary.setText(f"Hele eksportfilen: {len(records)} objekter • {count} feil • {len(self.issues) - count} advarsler. Eksportkopi: {len(self.records)} objekter.\n"
                                 "Delkontroll: påkrevde felt, typer, profilkoder, koordinater og støttet geometri.\n"
                                 "Ved feil utenfor eksportkopien: velg ALLE objekter og lag ny eksportkopi.\n"
                                 "Full fagstandard, riktig klassifisering, fysisk målekvalitet og mottakergodkjenning gjenstår.")
            self.change_summary.setPlainText(change_report(self.last_audit) if self.last_audit else 'Eksport blokkert. Rett alle feil i hele filen og kontroller på nytt.')
            self.tabs.setCurrentIndex(3)
            self.refresh_navigation()
            return count == 0
        except Exception as error:
            self.error(error)
            return False

    def select_record(self, row, *_):
        if self.snapshot_layer is not None and row < len(self.records):
            self.snapshot_layer.selectByIds([self.records[row].fid])

    def select_issue(self, row, *_):
        if self.snapshot_layer is not None and row < len(self.issues):
            fid = self.issues[row].fid
            if self.snapshot_document and fid is not None:
                fid = next((int(key) for key,value in self.snapshot_document['feature_map'].items() if int(value) == fid), None)
                if fid is None:
                    self.status.setText('Feilen gjelder et objekt utenfor valgt del-lag. Velg ALLE objekter og lag ny eksportkopi for å rette det.')
            if fid is not None:
                self.snapshot_layer.selectByIds([fid])
                for record_row, record in enumerate(self.records):
                    if record.fid == fid:
                        self.values.selectRow(record_row)
                        self.values.scrollToItem(self.values.item(record_row, 0))
                        break

    def select_errors(self):
        if self.snapshot_layer is not None:
            ids = {i.fid for i in self.issues if i.fid is not None and i.severity == 'FEIL'}
            if self.snapshot_document:
                ids = {int(key) for key,value in self.snapshot_document['feature_map'].items() if int(value) in ids}
            self.snapshot_layer.selectByIds(list(ids))

    def report_data(self):
        layer = self.snapshot_layer
        origin = None
        if layer is not None and layer.customProperty('sosi_survey/field_import', False):
            origin = {
                'source_sha256': layer.customProperty('sosi_survey/source_sha256', ''),
                'source_crs': layer.customProperty('sosi_survey/source_crs', ''),
                'height_reference': layer.customProperty('sosi_survey/source_height_reference', ''),
                'column_map': json.loads(layer.customProperty('sosi_survey/source_columns', '{}')),
                'selected_points': [],
            }
            for record in self.records:
                feature = layer.getFeature(record.fid)
                if feature.isValid():
                    origin['selected_points'].append({
                        'qgis_fid': record.fid,
                        'source_id': feature['source_id'],
                        'source_row': feature['source_row'],
                        'source_code': feature['source_code'],
                    })
        return {"plugin_version": "0.5.10", "scope": "Hele eksportfilen; intern delkontroll, ikke Kartverkets SOSI-kontroll",
                "source": self.snapshot_source, "selection_only": self.snapshot_selected,
                "profile": self.profile, "settings": asdict(self.settings()),
                "mappings": self.snapshot_mappings, "issues": [asdict(i) for i in self.issues],
                "edited_objects": len(self.records),
                "exported_objects": self.last_audit['objects_checked'] if self.last_audit else len(self.all_records()),
                "readback": self.last_audit, "field_import": origin,
                "records": [asdict(r) for r in self.all_records()]}

    def export_text(self):
        if self.snapshot_document:
            document = self.snapshot_document
            return render_preserved(document, self.records, self.profile, self.settings()), document['codec']
        return render(self.records, self.profile, self.settings()), 'iso8859-10' if self.settings().encoding == 'ISO8859-10' else 'utf-8'

    def save_report(self):
        self.check()
        if self.snapshot_layer is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Lagre kontrollrapport med eksportverdier", "kontroll.json", "JSON (*.json)")
        if path:
            try:
                atomic_new_text(path, json.dumps(self.report_data(), ensure_ascii=False, indent=2))
            except Exception as error:
                self.error(error)

    def export(self):
        if not self.check():
            return
        answer = QMessageBox.question(self, "Eksporter prøvefil",
                                      "BETA – BRUK PÅ EGET ANSVAR.\n"
                                      "Intern delkontroll har ingen feil, men kan ikke garantere "
                                      "gyldig eller korrekt SOSI-leveranse.\n"
                                      "Du er selv ansvarlig for full fagkontroll, riktig "
                                      "SOSI-produktspesifikasjon og mottakerkrav. "
                                      "Utvikler fraskriver seg ansvar bare så langt gjeldende "
                                      "lov og GPLv3 §§ 15–17 tillater.\n\n"
                                      "Vil du eksportere prøvefil med kontrollrapport?",
                                      MESSAGE_YES | MESSAGE_NO,
                                      MESSAGE_NO)
        if answer != MESSAGE_YES:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Ny SOSI-prøvefil (eksisterende filer erstattes ikke)", "survey_utkast.sos", "SOSI (*.sos)")
        if not path:
            return
        if not path.lower().endswith(".sos"):
            path += ".sos"
        report_path = path + ".kontroll.json"
        changes_path = path + '.endringer.txt'
        if any(Path(p).exists() for p in (path, report_path, changes_path)):
            self.error("Fil eller kontrollrapport finnes allerede. Velg et nytt navn.")
            return
        try:
            text, codec = self.export_text()
            self.last_audit = write_verified(path, text.encode(codec), self.verify_data)
            report = self.report_data()
            report['sosi_sha256'] = self.last_audit['export_sha256']
            report['coordinate_export'] = self.last_audit['geometry_mode']
            report['original_file'] = self.snapshot_original_file
            if self.snapshot_document:
                report['preserved_source'] = header_details(self.snapshot_document)
            try:
                atomic_new_text(changes_path, change_report(self.last_audit))
                atomic_new_text(report_path, json.dumps(report, ensure_ascii=False, indent=2))
            except Exception as error:
                self.error(f"SOSI-filen ble skrevet til {path}, men rapporten kunne ikke lagres: {error}")
                return
            self.change_summary.setPlainText(change_report(self.last_audit))
            self.status.setText(f"Gjeninnlesing fra disk bestått. Skrev prøvefil, kontrollrapport og endringsrapport: {path}")
            QMessageBox.information(self, "Prøvefil skrevet og gjeninnlest", f"{path}\n{report_path}\n{changes_path}\n\nGeometri og felt er kontrollert etter skriving. Kontroller videre i SOSI-vis/SOSI-kontroll med riktig fagoppsett.")
        except Exception as error:
            self.error(error)
