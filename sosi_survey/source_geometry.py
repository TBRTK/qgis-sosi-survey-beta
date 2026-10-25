# SPDX-License-Identifier: GPL-3.0-or-later
"""Construct QGIS curves/surfaces while retaining the original SOSI topology."""
from qgis.core import (QgsPoint, QgsGeometry, QgsLineString, QgsCircularString,
                       QgsCompoundCurve, QgsCurvePolygon)


def build_geometries(document):
    objects = {o['serial']:o for o in document['objects']}
    built, visiting = {}, set()

    def build(serial):
        if serial in built: return built[serial]
        if serial not in objects: raise ValueError(f'Flatereferanse til manglende objekt {serial}.')
        if serial in visiting: raise ValueError('Sykliske flatereferanser.')
        visiting.add(serial)
        obj = objects[serial]
        coordinates = obj['coordinates']
        if obj.get('mixed_dimension'):
            coordinates = [xyz[:2] for xyz in coordinates]
        points = [QgsPoint(*xyz) for xyz in coordinates]
        kind = obj['kind']
        if kind == 'PUNKT':
            shape = points[0]
        elif kind == 'KURVE':
            shape = QgsLineString(points)
        elif kind == 'BUEP':
            a,b,c = obj['coordinates']
            cross = (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
            if cross == 0: raise ValueError(f'BUEP {serial}: punktene er kollineære; sirkelbuen er ikke entydig.')
            shape = QgsCircularString()
            shape.setPoints(points)
        else:
            shape = QgsCurvePolygon()
            # Resolve all referenced boundaries before creating any compound
            # rings. Some valid SOSI plans have Z on only a subset of curves
            # delimiting a 2D FLATE. QgsCompoundCurve must never receive
            # segments of mixed dimensionality.
            boundary_groups = []
            for index, refs in enumerate(obj['rings']):
                segments = []
                for ref in refs:
                    target = objects.get(abs(ref))
                    segment = build(abs(ref))
                    if target['kind'] == 'FLATE':
                        if index == 0 or len(refs) != 1 or segment.numInteriorRings():
                            raise ValueError('En referert FLATE støttes bare som ett sammenhengende hull uten egne hull.')
                        segment = segment.exteriorRing().clone()
                    elif target['kind'] not in ('KURVE', 'BUEP'):
                        raise ValueError('Flategrenser må referere KURVE/BUEP.')
                    else:
                        segment = segment.clone()
                    if ref < 0:
                        segment = segment.reversed()
                    segments.append(segment)
                boundary_groups.append(segments)
            force_2d = any(not segment.is3D() for group in boundary_groups for segment in group)
            rings = []
            for refs, segments in zip(obj['rings'], boundary_groups):
                ring, first, last = QgsCompoundCurve(), None, None
                for ref, segment in zip(refs, segments):
                    if force_2d and segment.is3D():
                        segment.dropZValue()  # clone only; original remains 3D
                    start, finish = segment.startPoint(), segment.endPoint()
                    coords = lambda p: (p.x(), p.y(), p.z()) if segment.is3D() else (p.x(), p.y())
                    current_start, current_end = coords(start), coords(finish)
                    if last is not None and last != current_start:
                        raise ValueError(f'FLATE {serial}: grensekurvene møtes ikke med identisk XY/XYZ.')
                    if first is None:
                        first = current_start
                    last = current_end
                    ring.addCurve(segment)
                if first != last:
                    raise ValueError(f'FLATE {serial}: ringen er ikke lukket i XY/XYZ.')
                rings.append(ring)
            shape.setExteriorRing(rings[0])
            for ring in rings[1:]:
                shape.addInteriorRing(ring)
        geometry = QgsGeometry(shape.clone())
        if geometry.isEmpty() or not geometry.isGeosValid():
            raise ValueError(f'Objekt {serial}: ugyldig geometri ifølge QGIS/GEOS.')
        if kind == 'FLATE':
            rep = QgsGeometry.fromWkt(f'POINT ({points[0].x()} {points[0].y()})')
            if not geometry.intersects(rep):
                raise ValueError(f'FLATE {serial}: representasjonspunktet ligger utenfor flaten og dens grense.')
        built[serial] = shape
        visiting.remove(serial)
        obj['geometry_wkb'] = bytes(geometry.asWkb()).hex()
        obj['display_coordinates'] = [[p.x(), p.y(), p.z()] if geometry.constGet().is3D()
                                      else [p.x(), p.y()] for p in geometry.vertices()]
        return shape

    for serial in objects:
        if not objects[serial].get('opaque'):
            build(serial)
    return built
