# SPDX-License-Identifier: GPL-3.0-or-later
"""Receiver-neutral CSV to GeoPackage field import for QGIS 3.44 and 4.

Private observations stay local. Every raw source attribute, source code, ID,
height-reference declaration and source hash is retained in the working GPKG.
"""
from pathlib import Path
import json

from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QTextBrowser, QVBoxLayout,
)
from qgis.core import (
    QgsFeature, QgsField, QgsGeometry, QgsPoint, QgsPointXY, QgsProject,
    QgsVectorFileWriter, QgsVectorLayer, QgsWkbTypes,
)
from .field_data import (
    ALLOWED_CRS, FieldMapping, make_points, read_delimited,
    source_field_names, suggest_columns,
)


class FieldCsvImportDialog(QDialog):
    def __init__(self, parent, csv_path, project_crs):
        super().__init__(parent)
        self.setWindowTitle('Feltimport – CSV fra valgfri mottaker')
        self.resize(780, 650)
        self.csv_path = str(csv_path)
        self.dataset = None
        self.mapping = None
        layout = QVBoxLayout(self)
        heading = QLabel(
            'Produsentuavhengig CSV-import. Alle kildens kolonner beholdes. '
            'Forslag til feltkobling skal bekreftes. Feltkode er ikke automatisk SOSI-OBJTYPE.')
        heading.setWordWrap(True)
        layout.addWidget(heading)
        fmt = QHBoxLayout()
        self.encoding = QComboBox()
        for name, value in (
            ('UTF-8 (med/uten BOM)', 'utf-8-sig'),
            ('ISO 8859-10', 'iso-8859-10'),
            ('Windows ANSI (cp1252)', 'cp1252'),
        ):
            self.encoding.addItem(name, value)
        self.delimiter = QComboBox()
        for name, value in (
            ('Automatisk', 'auto'), ('Komma ,', ','), ('Semikolon ;', ';'), ('Tabulator', '\t'),
        ):
            self.delimiter.addItem(name, value)
        button = QPushButton('Les / oppdater')
        button.clicked.connect(self.refresh)
        fmt.addWidget(QLabel('Tegnsett'))
        fmt.addWidget(self.encoding)
        fmt.addWidget(QLabel('Skilletegn'))
        fmt.addWidget(self.delimiter)
        fmt.addWidget(button)
        layout.addLayout(fmt)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        form = QFormLayout()
        self.selectors = {}
        for key, label in (
            ('easting', 'Øst X *'), ('northing', 'Nord Y *'),
            ('elevation', 'Høyde Z'), ('point_id', 'Punkt-ID / navn'),
            ('code', 'Feltkode'), ('description', 'Beskrivelse'),
        ):
            combo = QComboBox()
            self.selectors[key] = combo
            form.addRow(label, combo)
        self.crs = QComboBox()
        self.crs.addItem('Velg kildekoordinatsystem', '')
        for code in ALLOWED_CRS:
            self.crs.addItem(code + ' – EUREF89 UTM', code)
        if project_crs in ALLOWED_CRS:
            self.crs.setCurrentIndex(self.crs.findData(project_crs))
        form.addRow('Kilde-CRS *', self.crs)
        self.heights = QComboBox()
        for label, code in (
            ('Velg høydegrunnlag (ved Z)', ''),
            ('NN2000', 'NN2000'), ('NN54', 'NN54'),
            ('Ellipsoidisk GNSS-høyde', 'ELLIP'), ('Lokal høyde', 'LOKAL'),
        ):
            self.heights.addItem(label, code)
        form.addRow('Kildehøyde', self.heights)
        layout.addLayout(form)
        self.preview = QTextBrowser()
        self.preview.setMaximumHeight(145)
        layout.addWidget(self.preview)
        self.reviewed = QCheckBox(
            'Jeg har kontrollert Øst/Nord, CRS, koordinatenhet (meter) og eventuelt høydegrunnlag.')
        layout.addWidget(self.reviewed)
        flags = getattr(QDialogButtonBox, 'StandardButton', QDialogButtonBox)
        buttons = QDialogButtonBox(flags.Ok | flags.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        for combo in list(self.selectors.values()) + [self.crs, self.heights]:
            combo.currentIndexChanged.connect(lambda *_: self.reviewed.setChecked(False))
        # Any CSV format change requires a new read and a new operator review.
        self.encoding.currentIndexChanged.connect(self.refresh)
        self.delimiter.currentIndexChanged.connect(self.refresh)
        self.refresh()

    def refresh(self, *_):
        self.dataset = None
        self.reviewed.setChecked(False)
        try:
            data = read_delimited(
                self.csv_path, self.encoding.currentData(), self.delimiter.currentData())
        except (OSError, UnicodeError, ValueError) as error:
            self.status.setText('Kunne ikke lese filen: ' + str(error))
            self.preview.clear()
            return
        self.dataset = data
        self.status.setText(
            f'{data.filename}: {len(data.rows)} målerader og {len(data.headers)} kildekolonner.')
        guesses = suggest_columns(data.headers)
        for key, combo in self.selectors.items():
            combo.blockSignals(True)
            combo.clear()
            combo.addItem('Velg kolonne' if key in ('easting', 'northing')
                          else 'Ikke oppgitt / ikke brukt', None)
            for header in data.headers:
                combo.addItem(header, header)
            if guesses[key]:
                combo.setCurrentIndex(combo.findData(guesses[key]))
            combo.blockSignals(False)
        preview_rows = []
        for i, row in enumerate(data.rows[:4], 2):
            preview_rows.append(
                f'Rad {i}: ' + ' | '.join(f'{key}={value}' for key, value in row.items()))
        self.preview.setPlainText('\n'.join(preview_rows))

    def accept(self):
        if self.dataset is None:
            QMessageBox.warning(self, 'Feltimport', 'Velg en lesbar tekstfil først.')
            return
        selected = {name: combo.currentData()
                    for name, combo in self.selectors.items()}
        mapping = FieldMapping(
            **selected, crs=self.crs.currentData(),
            height_reference=self.heights.currentData() or None,
            reviewed=self.reviewed.isChecked())
        try:
            make_points(self.dataset, mapping)
        except ValueError as error:
            QMessageBox.warning(self, 'Kontroller kildefeltene', str(error))
            return
        self.mapping = mapping
        super().accept()


def make_point_layer(dataset, mapping, profile):
    """Construct a QGIS point layer with all CSV attributes and SOSI blank fields."""
    points = make_points(dataset, mapping)
    profile_names = [rule['path'] for rule in profile['fields']]
    names_by_header = source_field_names(dataset.headers, profile_names)
    uri = ('PointZ' if mapping.elevation else 'Point') + '?crs=' + mapping.crs
    layer = QgsVectorLayer(uri, 'Feltpunkter – kontrollert import', 'memory')
    if not layer.isValid():
        raise ValueError('QGIS kunne ikke opprette punktlaget.')
    provenance_fields = (
        'source_id', 'source_code', 'source_description', 'source_row',
        'source_file_sha256', 'source_columns_json', 'source_crs',
        'source_height_reference',
    )
    names = profile_names + list(provenance_fields) + list(names_by_header.values())
    if len({name.casefold() for name in names}) != len(names):
        raise ValueError('Kildekolonnene kolliderer med SOSI-/sporingsfelter.')
    provider = layer.dataProvider()
    fields = [QgsField(name, QVariant.Int if name == 'source_row' else QVariant.String)
              for name in names]
    if not provider.addAttributes(fields):
        raise ValueError('Kunne ikke opprette attributtfelter i QGIS.')
    layer.updateFields()
    original_headers = json.dumps(names_by_header, ensure_ascii=False, sort_keys=True)
    buffer = []
    for point in points:
        feature = QgsFeature(layer.fields())
        attributes = (
            ['' for _ in profile_names] +
            [point.point_id, point.code, point.description, point.source_row,
             dataset.sha256, original_headers, mapping.crs, mapping.height_reference or ''] +
            [point.raw[header] for header in dataset.headers]
        )
        feature.setAttributes(attributes)
        if point.elevation is None:
            feature.setGeometry(QgsGeometry.fromPointXY(
                QgsPointXY(point.easting, point.northing)))
        else:
            feature.setGeometry(QgsGeometry(QgsPoint(
                point.easting, point.northing, point.elevation)))
        buffer.append(feature)
        if len(buffer) >= 1000:
            if not provider.addFeatures(buffer)[0]:
                raise ValueError('Kunne ikke legge til alle feltpunktene i QGIS.')
            buffer.clear()
    if buffer and not provider.addFeatures(buffer)[0]:
        raise ValueError('Kunne ikke legge til alle feltpunktene i QGIS.')
    layer.updateExtents()
    if layer.featureCount() != len(points):
        raise ValueError('QGIS-objektantall avviker fra CSV.')
    return layer


def write_point_geopackage(dataset, mapping, profile, target):
    """Save a NEW GeoPackage, without overwriting or transforming the source."""
    target = Path(target)
    if target.suffix.lower() != '.gpkg' or target.exists():
        raise ValueError('Velg et nytt GeoPackage-filnavn som slutter med .gpkg.')
    temporary = make_point_layer(dataset, mapping, profile)
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = 'GPKG'
    options.fileEncoding = 'UTF-8'
    options.layerName = 'feltpunkter'
    result = QgsVectorFileWriter.writeAsVectorFormatV3(
        temporary, str(target), QgsProject.instance().transformContext(), options)
    if result[0] != QgsVectorFileWriter.NoError:
        if target.exists():
            target.unlink()
        raise ValueError('GeoPackage kunne ikke skrives: ' + str(result[-1]))
    saved = QgsVectorLayer(
        str(target) + '|layername=feltpunkter',
        'Feltmålinger – ' + dataset.filename, 'ogr')
    if not saved.isValid() or saved.featureCount() != temporary.featureCount():
        raise ValueError('Kontroll etter lagring: GeoPackage kunne ikke leses tilbake riktig.')
    saved.setCustomProperty('sosi_survey/field_import', True)
    saved.setCustomProperty('sosi_survey/source_sha256', dataset.sha256)
    saved.setCustomProperty('sosi_survey/source_crs', mapping.crs)
    saved.setCustomProperty('sosi_survey/source_height_reference', mapping.height_reference or '')
    saved.setCustomProperty('sosi_survey/source_columns', json.dumps(
        source_field_names(dataset.headers, [rule['path'] for rule in profile['fields']]),
        ensure_ascii=False))
    QgsProject.instance().addMapLayer(saved)
    return saved


def run_csv_import(parent, profile):
    """Run the review and return the new GeoPackage point layer."""
    path, _ = QFileDialog.getOpenFileName(
        parent, 'Velg CSV fra valgfri mottaker', '',
        'Tekstfiler (*.csv *.txt);;Alle filer (*)')
    if not path:
        return None
    dialog = FieldCsvImportDialog(parent, path, QgsProject.instance().crs().authid())
    if dialog.exec() != 1:
        return None
    target, _ = QFileDialog.getSaveFileName(
        parent, 'Lagre feltimport som nytt GeoPackage (CSV beholdes)',
        str(Path(path).with_suffix('.gpkg')), 'GeoPackage (*.gpkg)')
    if not target:
        return None
    if not target.lower().endswith('.gpkg'):
        target += '.gpkg'
    return write_point_geopackage(dialog.dataset, dialog.mapping, profile, target)


def check_existing_point_layer(layer):
    """Accept existing QGIS point layers independently of receiver brand."""
    if not isinstance(layer, QgsVectorLayer) or not layer.isValid():
        raise ValueError('Velg et gyldig QGIS-vektorlag med innmålte punkter.')
    if QgsWkbTypes.flatType(layer.wkbType()) != QgsWkbTypes.Type.Point:
        raise ValueError('Velg et punktlag (Point/PointZ), ikke linjer eller flater.')
    if layer.crs().authid() not in ALLOWED_CRS:
        raise ValueError('Punktlaget må være i bekreftet EUREF89 / UTM 31–36. '
                         'Ingen transformasjon skjer automatisk.')
    return layer
