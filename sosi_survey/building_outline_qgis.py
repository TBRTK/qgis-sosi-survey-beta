# SPDX-License-Identifier: GPL-3.0-or-later
"""Reviewable building outline from selected points in QGIS 3.44/4.

The original point layer is never edited. Derived geometry and full ordered
source-point evidence are kept in a local GeoPackage. This is a documentation
prototype, NOT approved FKB-Bygning or municipal SOSI delivery.
"""
from dataclasses import asdict
import json
from pathlib import Path

from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)
from qgis.core import (
    QgsFeature, QgsField, QgsGeometry, QgsLineString,
    QgsPoint, QgsPolygon, QgsProject, QgsVectorFileWriter,
    QgsVectorLayer, QgsWkbTypes,
)
from .building_outline import (
    MeasuredCorner, MAX_CORNERS, make_building_outline,
)
from .field_data import suggest_columns
from .field_import_qgis import check_existing_point_layer
from .attribute_help import configure_draft_attribute_form


def _to_text(value):
    if value is None or (hasattr(value, 'isNull') and value.isNull()):
        return ''
    return str(value)


def _attr(feature, field, field_names):
    return _to_text(feature[field]) if field and field in field_names else ''


def selected_measured_corners(layer, features, id_field='', code_field='',
                              description_field=''):
    """Capture selected source features without rewriting or inventing values."""
    check_existing_point_layer(layer)
    if QgsWkbTypes.hasM(layer.wkbType()):
        raise ValueError('Punktlag med M-dimensjon støttes ennå ikke.')
    field_names = {field.name() for field in layer.fields()}
    for field in (id_field, code_field, description_field):
        if field and field not in field_names:
            raise ValueError('Ukjent kildekolonne: '+field)
    corners = []
    snapshot = []
    for feature in features:
        geometry = feature.geometry()
        if geometry.isNull() or geometry.isEmpty():
            raise ValueError('Et valgt hjørne mangler punktgeometri.')
        point = geometry.asPoint()
        z = point.z() if QgsWkbTypes.hasZ(geometry.wkbType()) else None
        corner = MeasuredCorner(
            key=str(feature.id()), easting=point.x(), northing=point.y(),
            elevation=z, point_id=_attr(feature, id_field, field_names),
            code=_attr(feature, code_field, field_names),
            description=_attr(feature, description_field, field_names),
            source_row=_attr(feature, 'source_row', field_names),
            source_hash=_attr(feature, 'source_file_sha256', field_names)
                          or _to_text(layer.customProperty('sosi_survey/source_sha256', '')),
        )
        corners.append(corner)
        snapshot.append({
            'corner': asdict(corner),
            'original_attributes': {
                field.name(): _to_text(feature[field.name()])
                for field in layer.fields()
            },
            'source_wkb': bytes(geometry.asWkb()).hex(),
        })
    return tuple(corners), tuple(snapshot)


def _geometry(outline):
    points = [QgsPoint(*point) for point in outline.vertices]
    if outline.geometry_kind == 'LINE':
        geometry = QgsGeometry.fromPolyline(points)
    else:
        polygon = QgsPolygon()
        polygon.setExteriorRing(QgsLineString(points))
        geometry = QgsGeometry(polygon)
    if geometry.isNull() or geometry.isEmpty() or not geometry.isGeosValid():
        raise ValueError('Bygningsomrisset er ikke en gyldig QGIS-geometri.')
    return geometry


def write_outline_geopackage(outline, snapshot, profile, destination, local_id=''):
    """Persist derived geometry in a NEW GeoPackage; do not alter source data."""
    path = Path(destination)
    if path.suffix.lower() != '.gpkg' or path.exists():
        raise ValueError('Velg et nytt filnavn med .gpkg. Eksisterende filer erstattes ikke.')
    if not profile.get('id') == 'bygning_plassering_utkast':
        raise ValueError('Bygningsveiviseren trenger egen dokumentasjonsprofil.')
    names = [rule['path'] for rule in profile['fields']]
    tracking = [
        'local_building_id', 'measured_reference', 'source_point_ids',
        'source_feature_ids', 'source_codes', 'source_descriptions',
        'source_rows', 'source_hashes', 'source_snapshot_json',
        'source_height_reference', 'height_handling', 'geometry_origin',
    ]
    if len({name.casefold() for name in names + tracking}) != len(names + tracking):
        raise ValueError('SOSI-profilen kolliderer med sporingsfelter.')
    geom_name = ('LineString' if outline.geometry_kind == 'LINE' else 'Polygon')
    uri = geom_name + ('Z' if outline.includes_z else '') + '?crs=' + outline.crs
    memory = QgsVectorLayer(uri, 'Bygning – kontrollert omriss', 'memory')
    if not memory.isValid():
        raise ValueError('QGIS kunne ikke opprette bygningsgeometrien.')
    provider = memory.dataProvider()
    if not provider.addAttributes([QgsField(name, QVariant.String)
                                   for name in names + tracking]):
        raise ValueError('QGIS kunne ikke opprette attributter.')
    memory.updateFields()
    feature = QgsFeature(memory.fields())
    source_ids = [p.point_id for p in outline.corners]
    values = (
        [''] * len(names) +
        [
            local_id, outline.measured_reference,
            json.dumps(source_ids, ensure_ascii=False),
            json.dumps([p.key for p in outline.corners]),
            json.dumps([p.code for p in outline.corners], ensure_ascii=False),
            json.dumps([p.description for p in outline.corners], ensure_ascii=False),
            json.dumps([p.source_row for p in outline.corners]),
            json.dumps(sorted({p.source_hash for p in outline.corners if p.source_hash})),
            json.dumps(list(snapshot), ensure_ascii=False, sort_keys=True),
            outline.height_reference,
            ('Målt Z i avledet omriss' if outline.includes_z
             else '2D-omriss; eventuelle målehøyder kun i sporingsdata'),
            outline.geometry_kind,
        ]
    )
    feature.setAttributes(values)
    feature.setGeometry(_geometry(outline))
    if not provider.addFeatures([feature])[0]:
        raise ValueError('Kunne ikke opprette omrissobjektet.')
    memory.updateExtents()
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = 'GPKG'
    options.fileEncoding = 'UTF-8'
    options.layerName = 'bygningsomriss'
    result = QgsVectorFileWriter.writeAsVectorFormatV3(
        memory, str(path), QgsProject.instance().transformContext(), options)
    if result[0] != QgsVectorFileWriter.NoError:
        if path.exists():
            path.unlink()
        raise ValueError('Kunne ikke lagre GeoPackage: ' + str(result[-1]))
    saved = QgsVectorLayer(str(path) + '|layername=bygningsomriss',
                           'Bygningsomriss – ' + (local_id or 'feltmåling'), 'ogr')
    if not saved.isValid() or saved.featureCount() != 1:
        raise ValueError('GeoPackage kunne ikke gjeninnleses korrekt.')
    recorded = next(saved.getFeatures())
    if (recorded['source_snapshot_json'] != values[names.__len__() + tracking.index('source_snapshot_json')]
            or bytes(recorded.geometry().asWkb()) != bytes(feature.geometry().asWkb())):
        raise ValueError('Gjeninnlesing: geometri eller sporingsdata har endret seg.')
    saved.setCustomProperty('sosi_survey/building_placement_draft', True)
    saved.setCustomProperty('sosi_survey/draft_profile', profile['id'])
    configure_draft_attribute_form(saved, profile)
    QgsProject.instance().addMapLayer(saved)
    return saved


class BuildingOutlineDialog(QDialog):
    def __init__(self, parent, preferred_layer, profile, coordinate_unit=0.01):
        super().__init__(parent)
        self.profile = profile
        self.saved_layer = None
        self.features = []
        self.coordinate_unit = coordinate_unit if coordinate_unit else 0.01
        self.setWindowTitle('Bygningsomriss fra innmålte hushjørner')
        self.resize(900, 670)
        layout = QVBoxLayout(self)
        heading = QLabel(
            'Marker minst tre punkter i QGIS-kartet først. Velg dem her, '
            'ordne hjørnene langs ytterkanten, og bekreft målereferansen. '
            'Dette dokumenterer geometri – ikke automatisk FKB-klassifisering.')
        heading.setWordWrap(True)
        layout.addWidget(heading)
        form = QFormLayout()
        self.layer_combo = QComboBox()
        sources = sorted(
            (layer for layer in QgsProject.instance().mapLayers().values()
             if isinstance(layer, QgsVectorLayer) and layer.isValid()
             and QgsWkbTypes.flatType(layer.wkbType()) == QgsWkbTypes.Type.Point),
            key=lambda layer: layer.name().casefold())
        for layer in sources:
            self.layer_combo.addItem(layer.name(), layer.id())
        if preferred_layer and self.layer_combo.findData(preferred_layer.id()) >= 0:
            self.layer_combo.setCurrentIndex(self.layer_combo.findData(preferred_layer.id()))
        form.addRow('Innmålt punktlag', self.layer_combo)
        self.fields = {}
        for key, label in (
            ('id', 'Felt-ID / navn'), ('code', 'Feltkode'),
            ('description', 'Beskrivelse'),
        ):
            combo = QComboBox()
            self.fields[key] = combo
            form.addRow(label, combo)
        self.reference = QComboBox()
        for label, key in (
            ('Ytterkant grunnmur, målt ved bakken', 'grunnmur'),
            ('Yttervegg / fasadeliv', 'fasadeliv'),
            ('Takkant', 'takkant'),
            ('Annen bekreftet målereferanse', 'annet'),
        ):
            self.reference.addItem(label, key)
        form.addRow('Hva er målt?', self.reference)
        self.geom_choice = QComboBox()
        self.geom_choice.addItem('Lukket linje (KURVE i SOSI-utkast)', 'LINE')
        self.geom_choice.addItem('Flate (polygon – må ha egen godkjent SOSI-profil)', 'POLYGON')
        form.addRow('Lag geometri', self.geom_choice)
        self.use_z = QCheckBox(
            'Bruk alle målte Z-verdier i 3D-omriss (ellers 2D med Z bevart i sporing)')
        form.addRow('Høyde', self.use_z)
        self.height = QComboBox()
        self.height.addItem('Velg/kontroller høydegrunnlag', '')
        for key in ('NN2000', 'NN54', 'ELLIP', 'LOKAL'):
            self.height.addItem(key, key)
        form.addRow('Målingenes høydesystem', self.height)
        self.local_id = QLineEdit()
        self.local_id.setPlaceholderText('Valgfritt lokalt byggnummer / referanse')
        form.addRow('Bygg-ID (lokal)', self.local_id)
        layout.addLayout(form)
        load = QPushButton('Hent markerte hushjørner fra punktlaget')
        load.clicked.connect(self.load_points)
        layout.addWidget(load)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ['Rekkefølge', 'Felt-ID', 'Øst', 'Nord', 'Z', 'Kode/beskrivelse'])
        self.table.setSortingEnabled(False)
        layout.addWidget(self.table)
        moves = QHBoxLayout()
        up = QPushButton('Flytt opp')
        down = QPushButton('Flytt ned')
        up.clicked.connect(lambda: self.move(-1))
        down.clicked.connect(lambda: self.move(1))
        moves.addWidget(up)
        moves.addWidget(down)
        layout.addLayout(moves)
        self.confirm = QCheckBox(
            'Jeg har kontrollert rekkefølgen rundt bygget og hva punktene representerer.')
        layout.addWidget(self.confirm)
        self.status = QLabel('Ingen hjørner valgt ennå. Tegn eller marker dem i QGIS.')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons = QHBoxLayout()
        review = QPushButton('Kontroller omriss')
        review.clicked.connect(self.review_outline)
        save = QPushButton('Opprett bygningsomriss (GeoPackage)')
        save.clicked.connect(self.save_outline)
        cancel = QPushButton('Avbryt')
        cancel.clicked.connect(self.reject)
        buttons.addWidget(review)
        buttons.addWidget(save)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)
        self.layer_combo.currentIndexChanged.connect(self.layer_changed)
        for combo in self.fields.values():
            combo.currentIndexChanged.connect(self.invalidate)
        self.height.currentIndexChanged.connect(self.invalidate)
        self.reference.currentIndexChanged.connect(self.invalidate)
        self.geom_choice.currentIndexChanged.connect(self.invalidate)
        self.use_z.toggled.connect(self.invalidate)
        self.layer_changed()

    def source_layer(self):
        return QgsProject.instance().mapLayer(self.layer_combo.currentData())

    def invalidate(self, *_):
        self.confirm.setChecked(False)

    def layer_changed(self, *_):
        self.features = []
        self.table.setRowCount(0)
        self.confirm.setChecked(False)
        layer = self.source_layer()
        if layer is None:
            return
        fields = [field.name() for field in layer.fields()]
        guesses = suggest_columns(fields)
        lookup = {'id': 'source_id' if 'source_id' in fields else guesses['point_id'],
                  'code': 'source_code' if 'source_code' in fields else guesses['code'],
                  'description': 'source_description' if 'source_description' in fields
                                 else guesses['description']}
        for key, combo in self.fields.items():
            combo.blockSignals(True)
            combo.clear()
            combo.addItem('Ikke oppgitt', '')
            for name in fields:
                combo.addItem(name, name)
            selected = lookup[key]
            if selected and combo.findData(selected) >= 0:
                combo.setCurrentIndex(combo.findData(selected))
            combo.blockSignals(False)
        reference = layer.customProperty('sosi_survey/source_height_reference', '')
        if reference and self.height.findData(reference) >= 0:
            self.height.setCurrentIndex(self.height.findData(reference))
        self.status.setText('Velg 3–120 hushjørner i kartet og trykk Hent.')

    def load_points(self):
        layer = self.source_layer()
        try:
            check_existing_point_layer(layer)
            features = sorted(layer.getSelectedFeatures(), key=lambda feature: feature.id())
            if not (3 <= len(features) <= MAX_CORNERS):
                raise ValueError('Marker 3–120 hushjørner i QGIS før du henter dem.')
            self.features = features
            self.draw_table()
            self.confirm.setChecked(False)
            self.status.setText(
                f'{len(features)} punkter hentet. Første rekkefølge er QGIS-ID, '
                'IKKE nødvendigvis riktig gangretning. Flytt rader til korrekt omriss.')
        except (ValueError, AttributeError) as error:
            self.status.setText(str(error))

    def draw_table(self):
        layer = self.source_layer()
        field_names = {field.name() for field in layer.fields()}
        self.table.setRowCount(len(self.features))
        for row, feature in enumerate(self.features):
            point = feature.geometry().asPoint()
            vals = (
                str(row + 1), _attr(feature, self.fields['id'].currentData(), field_names)
                or 'QGIS-ID ' + str(feature.id()),
                f'{point.x():.4f}', f'{point.y():.4f}',
                f'{point.z():.4f}' if QgsWkbTypes.hasZ(feature.geometry().wkbType())
                else '(2D)',
                (_attr(feature, self.fields['code'].currentData(), field_names)
                 + ' / ' + _attr(feature, self.fields['description'].currentData(), field_names)),
            )
            for column, value in enumerate(vals):
                self.table.setItem(row, column, QTableWidgetItem(value))

    def move(self, delta):
        row = self.table.currentRow()
        target = row + delta
        if row < 0 or not (0 <= target < len(self.features)):
            return
        self.features[row], self.features[target] = (
            self.features[target], self.features[row])
        self.draw_table()
        self.table.selectRow(target)
        self.confirm.setChecked(False)

    def build_snapshot(self):
        if not self.features:
            raise ValueError('Hent først minst tre markerte hjørnepunkter.')
        layer = self.source_layer()
        # Refuse to work with geometries modified since the table was loaded.
        for feature in self.features:
            latest = layer.getFeature(feature.id())
            if (not latest.isValid() or
                    bytes(latest.geometry().asWkb()) !=
                    bytes(feature.geometry().asWkb())):
                raise ValueError('Et kildepunkt har endret seg. Hent hjørnene på nytt.')
        corners, snapshot = selected_measured_corners(
            layer, self.features,
            self.fields['id'].currentData(),
            self.fields['code'].currentData(),
            self.fields['description'].currentData())
        outline = make_building_outline(
            corners, crs=layer.crs().authid(),
            measured_reference=self.reference.currentData(),
            geometry_kind=self.geom_choice.currentData(),
            include_z=self.use_z.isChecked(),
            height_reference=self.height.currentData() or '',
            order_confirmed=self.confirm.isChecked(),
            coordinate_unit=self.coordinate_unit)
        return outline, snapshot

    def review_outline(self):
        try:
            outline, _ = self.build_snapshot()
            self.status.setText(
                f'Kontroll bestått: areal {outline.area_m2:.2f} m², '
                f'omkrets {outline.perimeter_m:.2f} m. '
                + ' '.join(outline.warnings))
        except ValueError as error:
            self.status.setText(str(error))

    def save_outline(self):
        try:
            outline, snapshot = self.build_snapshot()
            target, _ = QFileDialog.getSaveFileName(
                self, 'Lagre ny GeoPackage med omriss og målesporing',
                'bygningsomriss.gpkg', 'GeoPackage (*.gpkg)')
            if not target:
                return
            if not target.lower().endswith('.gpkg'):
                target += '.gpkg'
            self.saved_layer = write_outline_geopackage(
                outline, snapshot, self.profile, target, self.local_id.text())
            super().accept()
        except (ValueError, OSError, RuntimeError) as error:
            QMessageBox.warning(self, 'Bygningsomriss', str(error))


def run_building_outline(parent, current_layer, profile, coordinate_unit=0.01):
    dialog = BuildingOutlineDialog(parent, current_layer, profile, coordinate_unit)
    if dialog.exec() != 1:
        return None
    return dialog.saved_layer
