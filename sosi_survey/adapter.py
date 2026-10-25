# SPDX-License-Identifier: GPL-3.0-or-later
"""Read QGIS geometries without flattening curves, multipart or Z/M."""
from qgis.core import QgsVectorLayer, QgsWkbTypes
from qgis.PyQt.QtCore import QVariant
from .core import Record
import json


def collect(layer, profile, mappings, selected_only=False):
    if not isinstance(layer, QgsVectorLayer) or not layer.isValid():
        raise ValueError("Velg et gyldig vektorlag.")
    if layer.customProperty('sosi_survey/presentation_only', False):
        raise ValueError('Dette er et skrivebeskyttet visningslag for SOSI-tekst/symbol. '
                         'Velg ALLE objekter (feltkontroll) for bevarende eksport.')
    records = []
    payload = layer.customProperty('sosi_survey/roundtrip', '')
    document = json.loads(payload) if payload else None
    objects = {o['serial']:o for o in document['objects']} if document else {}
    features = layer.getSelectedFeatures() if selected_only else layer.getFeatures()
    for feature in features:
        values = {}
        for rule in profile["fields"]:
            path = rule["path"]
            mapping = mappings.get(path, {})
            source = mapping.get("field", "")
            value = feature[source] if source and layer.fields().indexFromName(source) >= 0 else None
            if value is None or (hasattr(value, 'isNull') and value.isNull()):
                value = None
            if hasattr(value, "toString"):
                value = value.toString("yyyy-MM-dd")
            if value is None or (isinstance(value, str) and not value.strip()):
                value = mapping.get("fallback", "")
            values[path] = value
        geometry = feature.geometry()
        geometry_wkb = bytes(geometry.asWkb()).hex()
        kind, coords, error, rings = "UKJENT", [], "", None
        if document:
            original = objects.get(int(document.get('feature_map', {}).get(str(feature.id()), -1)))
            if original is None:
                error = 'Objektet finnes ikke i originalfilen.'
            else:
                kind = original['kind']
                if layer.customProperty('sosi_survey/attribute_table', False):
                    coords = [tuple(c) for c in original['display_coordinates']]
                    geometry_wkb = original['geometry_wkb']
                else:
                    coords = [(p.x(), p.y(), p.z()) if geometry.constGet().is3D()
                              else (p.x(), p.y()) for p in geometry.vertices()]
                if geometry_wkb != original['geometry_wkb']:
                    error = 'Geometrien er endret. Bevarende eksport er stoppet.'
        elif geometry.isNull() or geometry.isEmpty():
            error = "Objektet har tom geometri."
        else:
            wkb = geometry.wkbType()
            flat = QgsWkbTypes.flatType(wkb)
            if QgsWkbTypes.hasM(wkb):
                error = "M-verdier støttes ikke; fjern dem eksplisitt i en arbeidskopi."
            if flat == QgsWkbTypes.Type.Point:
                kind = "PUNKT"
            elif flat == QgsWkbTypes.Type.LineString:
                kind = "KURVE"
            elif flat == QgsWkbTypes.Type.Polygon:
                kind = "FLATE"
                polygon = geometry.constGet()
                if polygon.hasCurvedSegments():
                    error = "Nye buede polygoner kan ikke eksporteres uten eksplisitt SOSI-kurvestøtte."
                elif not geometry.isGeosValid():
                    error = "Ugyldig polygon; rett topologien i QGIS først."
                else:
                    representative = geometry.pointOnSurface()
                    if representative.isNull() or representative.isEmpty():
                        error = "Fant ikke representasjonspunkt innenfor flaten."
                    else:
                        point = representative.asPoint()
                        coords = [(point.x(), point.y())]
                        boundaries = [polygon.exteriorRing()] + [
                            polygon.interiorRing(i) for i in range(polygon.numInteriorRings())]
                        rings = []
                        for boundary in boundaries:
                            coords_ring = [
                                (vertex.x(), vertex.y(), vertex.z())
                                if QgsWkbTypes.hasZ(wkb) else (vertex.x(), vertex.y())
                                for vertex in boundary.vertices()]
                            if coords_ring and coords_ring[-1] != coords_ring[0]:
                                coords_ring.append(coords_ring[0])
                            rings.append(coords_ring)
            else:
                error = "Bare Point, LineString og rett Polygon (2D/3D) støttes. Multipart kan ikke forenkles automatisk."
            if kind in ("PUNKT", "KURVE"):
                for vertex in geometry.vertices():
                    coords.append((vertex.x(), vertex.y(), vertex.z()) if QgsWkbTypes.hasZ(wkb) else (vertex.x(), vertex.y()))
            if not error and not geometry.isGeosValid():
                error = "Geometrien er ugyldig ifølge QGIS/GEOS."
        records.append(Record(feature.id(), kind, coords, values, error, geometry_wkb, rings=rings))
    return records
