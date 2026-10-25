# SPDX-License-Identifier: GPL-3.0-or-later
"""Produce shared SOSI boundary KURVE groups for new QGIS polygon exports.

Only straight 2D/3D rings with exactly quantized coincident vertices are
supported. No geometry is resampled or given invented elevations. Polygon
ring references are serialized by core.render(). This is not SOSI-kontroll.
"""
from dataclasses import replace
from collections import defaultdict
from math import gcd


def expand_polygons(records, profile, settings, origin):
    """Return KURVE+FLATE records with signed references and shared edges.

    Output object serials are their 1-based positions. Matching opposite edges
    refer to the same boundary, with a negative reference for reverse travel.
    """
    from .core import Record, scaled_coordinate

    if not any(record.kind == 'FLATE' for record in records):
        return list(records)
    boundary_type = profile.get('boundary_objtype', '')
    if not boundary_type or not isinstance(boundary_type, str):
        raise ValueError('Polygon-eksport krever boundary_objtype i SOSI-profilen.')

    result = []
    shared = {}
    ref_use = defaultdict(list)
    seen_outlines = set()
    for record in records:
        if record.kind != 'FLATE':
            result.append(record)
            continue
        if not record.rings:
            raise ValueError(f'FLATE {record.fid}: polygon mangler ringgeometri.')
        refs = []
        local_refs = set()
        for ring in record.rings:
            if len(ring) < 4 or tuple(ring[0]) != tuple(ring[-1]):
                raise ValueError(f'FLATE {record.fid}: polygonring er ikke lukket.')
            vertices = [tuple(scaled_coordinate(p, settings.unit, origin))
                        for p in ring]
            if len(set(vertices[:-1])) < 3:
                raise ValueError(f'FLATE {record.fid}: polygonring kollapser etter avrunding.')
            if len(set(v[:2] for v in vertices[:-1])) < 3:
                raise ValueError(f'FLATE {record.fid}: ring kollapser i plan etter avrunding.')
            ring_refs = []
            for i, (first, second) in enumerate(zip(vertices[:-1], vertices[1:])):
                if first[:2] == second[:2]:
                    raise ValueError(f'FLATE {record.fid}: kant {i + 1} kollapser ved valgt oppløsning.')
                key = tuple(sorted((first, second)))
                if key not in shared:
                    serial = len(result) + 1
                    result.append(Record(
                        serial, 'KURVE', [tuple(ring[i]), tuple(ring[i + 1])],
                        {'OBJTYPE': boundary_type}))
                    shared[key] = (serial, first)
                serial, original_start = shared[key]
                if serial in local_refs:
                    raise ValueError(f'FLATE {record.fid}: samme kant er referert flere ganger.')
                local_refs.add(serial)
                sign = 1 if original_start == first else -1
                ref_use[serial].append(sign)
                if (len(ref_use[serial]) > 2 or
                    (len(ref_use[serial]) == 2 and sum(ref_use[serial]) != 0)):
                    raise ValueError('En delt grense må brukes av høyst to flater i motsatte retninger.')
                ring_refs.append(sign * serial)
            refs.append(ring_refs)
        outline = frozenset(abs(v) for v in refs[0])
        if outline in seen_outlines:
            raise ValueError('To polygoner har identisk ytre grense; duplikat flate er ikke støttet.')
        seen_outlines.add(outline)
        result.append(replace(record, refs=refs))
    # Coincident edges must be noded identically in both polygons. Detect
    # collinear partial overlaps and T-junctions instead of quietly emitting
    # duplicated boundaries with incompatible vertices.
    collinear = defaultdict(list)
    for start, end in shared:
        x1, y1 = start[:2]
        x2, y2 = end[:2]
        dx, dy = x2 - x1, y2 - y1
        length = gcd(abs(dx), abs(dy))
        if not length:
            raise ValueError('Ugyldig grense med null lengde.')
        dx, dy = dx // length, dy // length
        if dx < 0 or (dx == 0 and dy < 0):
            dx, dy = -dx, -dy
        offset = dy * x1 - dx * y1
        t1, t2 = x1 * dx + y1 * dy, x2 * dx + y2 * dy
        collinear[(dx, dy, offset)].append((min(t1, t2), max(t1, t2)))
    for spans in collinear.values():
        spans.sort()
        previous_end = None
        for start, end in spans:
            if previous_end is not None and start < previous_end:
                raise ValueError('Delvis overlappende grenser må deles i like knutepunkter før SOSI-eksport.')
            previous_end = end
    return result
