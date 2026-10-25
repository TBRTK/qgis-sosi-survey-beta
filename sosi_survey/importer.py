# SPDX-License-Identifier: GPL-3.0-or-later
"""Version-neutral access through the installed GDAL/FYBA SOSI reader."""
from pathlib import Path
import re
from osgeo import gdal
from qgis.core import QgsVectorLayer
from qgis.core import QgsFeature, QgsGeometry, QgsPoint, QgsLineString, QgsField
from qgis.PyQt.QtCore import QVariant
import json
from .roundtrip import parse, FIELDS
from .source_geometry import build_geometries



def _presentation_layers(document, path):
    """Add optional point previews. These are NOT editable source geometries."""
    from qgis.core import (QgsPointXY, QgsPalLayerSettings,
                           QgsVectorLayerSimpleLabeling)

    columns = ('SOSI_ID', 'OBJTYPE', 'STRENG', 'DIM', 'REFMSTK',
               'ARKARTSTD', 'ARTYPE')
    layers = []
    for kind, suffix in (('TEKST', 'etiketter'), ('SYMBOL', 'posisjoner')):
        objects = [o for o in document['objects']
                   if o['kind'] == kind and o.get('coordinates')]
        if not objects:
            continue
        layer = QgsVectorLayer(
            f'Point?crs={document["crs"]}',
            f'{Path(path).stem} – {kind} ({suffix}, ikke originalsymbolikk)',
            'memory')
        if not layer.isValid():
            raise ValueError(f'Kunne ikke lage visningslag for {kind}.')
        provider = layer.dataProvider()
        provider.addAttributes([QgsField(name, QVariant.String)
                                for name in columns])
        layer.updateFields()
        features = []
        for obj in objects:
            point = obj['coordinates'][0]
            feature = QgsFeature(layer.fields())
            feature.setAttributes([str(obj['serial'])] +
                                  [str(obj['values'].get(key, ''))
                                   for key in columns[1:]])
            feature.setGeometry(QgsGeometry.fromPointXY(
                QgsPointXY(float(point[0]), float(point[1]))))
            features.append(feature)
        if not provider.addFeatures(features)[0]:
            raise ValueError(f'Kunne ikke fylle visningslag for {kind}.')
        layer.updateExtents()
        if kind == 'TEKST':
            settings = QgsPalLayerSettings()
            settings.fieldName = 'STRENG'
            layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
            layer.setLabelsEnabled(True)
        layer.setReadOnly(True)
        layer.setCustomProperty('sosi_survey/presentation_only', True)
        layer.setCustomProperty('sosi_survey/source_path',
                                str(Path(path).resolve()))
        layers.append(layer)
    return layers


def read_sosi_3d(path):
    document = parse(Path(path).read_bytes())
    geometries = build_geometries(document)
    layers = []
    for kind in ('PUNKT', 'KURVE', 'BUEP', 'FLATE'):
        for dimension in (2, 3):
            objects = [o for o in document['objects']
                       if o['kind'] == kind and (3 if geometries[o['serial']].is3D() else 2) == dimension]
            if not objects:
                continue
            geometry_type = {'PUNKT': 'Point', 'KURVE': 'LineString',
                             'BUEP': 'CircularString', 'FLATE': 'CurvePolygon'}[kind]
            if dimension == 3:
                geometry_type += 'Z'
            layer = QgsVectorLayer(f'{geometry_type}?crs={document["crs"]}',
                                   f'{Path(path).stem} – {kind} {dimension}D', 'memory')
            provider = layer.dataProvider()
            provider.addAttributes([QgsField(field, QVariant.String) for field in FIELDS])
            layer.updateFields()
            feature_map = {}
            for obj in objects:
                feature = QgsFeature(layer.fields())
                feature.setAttributes([obj['values'].get(field, '') for field in FIELDS])
                feature.setGeometry(QgsGeometry(geometries[obj['serial']].clone()))
                ok, added = provider.addFeatures([feature])
                if not ok:
                    raise ValueError('Kunne ikke opprette SOSI-arbeidskopi.')
                feature_map[str(added[0].id())] = obj['serial']
            layer.updateExtents()
            layer.setReadOnly(True)
            subset = dict(document, feature_map=feature_map)
            layer.setCustomProperty('sosi_survey/roundtrip', json.dumps(subset, ensure_ascii=False))
            layer.setCustomProperty('sosi_survey/source_path', str(Path(path).resolve()))
            layer.setCustomProperty('sosi_survey/source_version', document['version'])
            layers.append(layer)
    layers.extend(_presentation_layers(document, path))
    if len(layers) > 1:
        # One table permits fixing a whole mixed file in a single export copy.
        table = QgsVectorLayer('None', f'{Path(path).stem} – ALLE objekter (feltkontroll)', 'memory')
        provider = table.dataProvider()
        provider.addAttributes([QgsField(field, QVariant.String) for field in FIELDS])
        table.updateFields()
        feature_map = {}
        for obj in document['objects']:
            if obj.get('opaque'):
                continue
            feature = QgsFeature(table.fields())
            feature.setAttributes([obj['values'].get(field, '') for field in FIELDS])
            ok, added = provider.addFeatures([feature])
            if not ok: raise ValueError('Kunne ikke opprette felles feltkontroll.')
            feature_map[str(added[0].id())] = obj['serial']
        table.setReadOnly(True)
        table.setCustomProperty('sosi_survey/roundtrip', json.dumps(dict(document, feature_map=feature_map), ensure_ascii=False))
        table.setCustomProperty('sosi_survey/attribute_table', True)
        table.setCustomProperty('sosi_survey/source_path', str(Path(path).resolve()))
        from qgis.core import QgsCoordinateReferenceSystem
        table.setCrs(QgsCoordinateReferenceSystem(document['crs']))
        layers.insert(0,table)
    return layers, document['version']


def read_sosi(path, preserve_z=True):
    if preserve_z:
        return read_sosi_3d(path)
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError('Filen finnes ikke.')
    if gdal.GetDriverByName('SOSI') is None:
        raise ValueError('Denne QGIS-installasjonen mangler SOSI/FYBA-leseren.')
    # Header is informational: never reject a file based on its declared version.
    with path.open('rb') as handle:
        header = handle.read(131072).decode('latin-1')
    match = re.search(r'^\.\.SOSI-VERSJON\s+([^\r\n]+)', header, re.MULTILINE)
    version = match.group(1).strip() if match else 'ikke oppgitt'
    dataset = gdal.OpenEx(str(path), gdal.OF_VECTOR | gdal.OF_READONLY, allowed_drivers=['SOSI'])
    if dataset is None:
        raise ValueError('SOSI-leseren kunne ikke åpne filen. Kontroller filformat, tegnsett og filens innhold. Ingen versjonsgrense er satt i pluginen.')
    layers = []
    for index in range(dataset.GetLayerCount()):
        source = dataset.GetLayer(index)
        if source.GetFeatureCount() == 0:
            continue
        layer = QgsVectorLayer(f'{path}|layerid={index}', f'{path.stem} – {source.GetName()}', 'ogr')
        if not layer.isValid():
            raise ValueError(f'QGIS kunne ikke lese del-lag {source.GetName()}. Ingen lag er lagt til.')
        layer.setReadOnly(True)
        layer.setCustomProperty('sosi_survey/source_version', version)
        layer.setCustomProperty('sosi_survey/import_xy_only', True)
        layers.append(layer)
    if not layers:
        raise ValueError('Ingen lesbare geografiske objekter ble funnet. Ingen lag er lagt til.')
    return layers, version
