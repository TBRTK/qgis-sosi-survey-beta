# SPDX-License-Identifier: GPL-3.0-or-later
"""Guided creation of draft QGIS layers for subsequent SOSI validation.

No object types, heights, quality codes or product specifications are guessed.
This wizard cannot certify a delivered SOSI file as valid.
"""
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtWidgets import (QWizard, QWizardPage, QFormLayout, QVBoxLayout,
                                 QComboBox, QLabel)
from qgis.core import QgsProject, QgsVectorLayer, QgsField
from .core import CRS_CODES, validate_profile
from .attribute_help import configure_draft_attribute_form, field_guidance


# QGIS dark themes can supply white label text while the native QWizard
# keeps a white page background (notably on Windows/Vista-style dialogs).
# Scope a high-contrast light style to these two wizard pages only.
# Other QGIS forms and the application theme are not changed.
_PAGE_LABEL_STYLE = (
    "QLabel { color: #202020; background-color: #ffffff; }"
)


class NewSosiLayerWizard(QWizard):
    def __init__(self, parent, profile):
        super().__init__(parent)
        self.profile = validate_profile(profile)
        self.setWindowTitle('SOSI-veiviser – nytt arbeidslag')
        self.resize(630, 430)
        first = QWizardPage()
        first.setStyleSheet(_PAGE_LABEL_STYLE)
        first.setTitle('1. Velg geometri og koordinatsystem')
        form = QFormLayout(first)
        self.geometry_choice = QComboBox()
        for label, kind, geom in (
            ('Punkt – PUNKT', 'PUNKT', 'Point'),
            ('Linje – KURVE', 'KURVE', 'LineString'),
            ('Flate – FLATE', 'FLATE', 'Polygon'),
        ):
            self.geometry_choice.addItem(label, (kind, geom))
        form.addRow('Geometritype', self.geometry_choice)
        self.dimensions = QComboBox()
        self.dimensions.addItem('2D – bare øst/nord (NØ)', 2)
        self.dimensions.addItem('3D – øst/nord/høyde (NØH)', 3)
        if profile.get('require_z', True):
            self.dimensions.setCurrentIndex(1)
        form.addRow('Dimensjon', self.dimensions)
        crs = QgsProject.instance().crs().authid() or '(ikke valgt)'
        crs_label = QLabel(crs)
        crs_label.setStyleSheet("color: #202020; background-color: #ffffff;")
        form.addRow('Prosjekt-CRS', crs_label)
        info = QLabel('Arbeidslaget bruker prosjekt-CRS uten reprojisering. '
                      'Bare EUREF89 / UTM sone 31–36 støttes.')
        info.setWordWrap(True)
        info.setStyleSheet("color: #202020; background-color: #ffffff;")
        form.addRow(info)
        self.addPage(first)
        second = QWizardPage()
        second.setStyleSheet(_PAGE_LABEL_STYLE)
        second.setTitle('2. Før SOSI-eksport')
        layout = QVBoxLayout(second)
        required = [f.get('label', f['path']) for f in profile['fields']
                    if f.get('required')]
        guidance = QLabel(
            'Profil: ' + profile.get('name', 'Ukjent') + '\n'
            'Påkrevde profilfelt: ' + (', '.join(required) or '(ingen)') + '\n\n'
            '1. Bruk feltimport av CSV/eksisterende QGIS-punktlag, eller tegn i kartet.\n'
            '2. Koble kildens felter til SOSI-felter i fane 2.\n'
            '3. Fyll inn manglende verdier i fane 3.\n'
            '4. Bekreft riktig høydegrunnlag og kjør intern kontroll.\n'
            '5. Eksporter prøvefil og kontroller mot riktig SOSI/DEF.\n\n'
            'Dette er et minnelag. Lagre det til GeoPackage dersom '
            'det skal beholdes etter at QGIS lukkes.')
        guidance.setWordWrap(True)
        # Explicit foreground AND background are needed: a dark inherited
        # palette with white-on-white native QWizard pages hides this label.
        guidance.setStyleSheet(
            "color: #202020; background-color: #ffffff; padding: 6px;")
        layout.addWidget(guidance)
        warning = QLabel('Ingen OBJTYPE, høyder, kvalitetskoder eller '
                         'mottakerkrav fylles ut automatisk. '
                         'Intern kontroll er ikke leveransegodkjenning.')
        warning.setWordWrap(True)
        warning.setStyleSheet(
            "color: #202020; background-color: #ffffff; padding: 6px;")
        layout.addWidget(warning)
        self.addPage(second)

    def create_layer(self):
        kind, geometry = self.geometry_choice.currentData()
        dimension = int(self.dimensions.currentData())
        crs = QgsProject.instance().crs().authid()
        if crs not in CRS_CODES:
            raise ValueError('Sett QGIS-prosjektet til EUREF89 / UTM 31–36. '
                             'Veiviseren endrer ikke koordinatsystemet.')
        if dimension == 2 and self.profile.get('require_z', True):
            raise ValueError('Valgt profil krever 3D. Velg 3D eller en dokumentert 2D-profil.')
        if kind == 'FLATE' and not self.profile.get('boundary_objtype'):
            raise ValueError('Valgt profil mangler boundary_objtype for '
                             'opprettelse av SOSI-grensekurver.')
        uri = geometry + ('Z' if dimension == 3 else '') + '?crs=' + crs
        layer = QgsVectorLayer(uri, 'SOSI utkast – ' + kind + ' ' + str(dimension) + 'D', 'memory')
        if not layer.isValid():
            raise ValueError('QGIS kunne ikke lage arbeidslag for ' + kind + '.')
        fields = []
        for rule in self.profile['fields']:
            field = QgsField(rule['path'], QVariant.String)
            guide = field_guidance(rule, self.profile)
            field.setComment(guide['inline'] + ' ' + guide['details'])
            fields.append(field)
        if not layer.dataProvider().addAttributes(fields):
            raise ValueError('QGIS kunne ikke opprette feltene i arbeidslaget.')
        layer.updateFields()
        configure_draft_attribute_form(layer, self.profile)
        if not layer.startEditing():
            raise ValueError('QGIS kunne ikke starte redigering av arbeidslaget.')
        layer.setCustomProperty('sosi_survey/draft_profile', self.profile.get('id', ''))
        layer.setCustomProperty('sosi_survey/new_draft', True)
        QgsProject.instance().addMapLayer(layer)
        return layer


def create_new_sosi_layer(parent, profile):
    wizard = NewSosiLayerWizard(parent, profile)
    if wizard.exec() != 1:
        return None
    return wizard.create_layer()
