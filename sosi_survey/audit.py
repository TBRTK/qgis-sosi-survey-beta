# SPDX-License-Identifier: GPL-3.0-or-later
"""Verify the complete serialized file and describe deliberate attribute edits.

This is internal readback verification, not independent SOSI-kontroll.
"""
from copy import deepcopy
from decimal import Decimal
import hashlib
import os
from pathlib import Path
import tempfile

from .core import Record, normalize, validate, coordinate_origin, scaled_coordinate, render
from .roundtrip import parse, properties, header_details
from .source_geometry import build_geometries


def source_records(document):
    document = deepcopy(document)
    build_geometries(document)
    return [Record(obj['serial'], obj['kind'], [tuple(c) for c in obj['display_coordinates']],
                   dict(obj['values']), geometry_wkb=obj['geometry_wkb'])
            for obj in document['objects'] if not obj.get('opaque')]


def complete_records(document, edited):
    """Use SOSI serials throughout whole-document validation, including hidden objects."""
    records = source_records(document)
    by_id = {r.fid: r for r in records}
    mapping = document.get('feature_map', {})
    seen = set()
    for record in edited:
        if str(record.fid) not in mapping:
            raise ValueError('Objektet mangler kobling til originalens SOSI-ID.')
        serial = int(mapping[str(record.fid)])
        if serial not in by_id or serial in seen:
            raise ValueError('Ugyldig eller gjentatt SOSI-ID i eksportkopien.')
        seen.add(serial)
        copy = deepcopy(record)
        copy.fid = serial
        by_id[serial] = copy
    return [by_id[r.fid] for r in records]


def comparable(value, rule):
    value = normalize(value, rule)
    return str(value) if isinstance(value, Decimal) else value


def changes(before, after, profile):
    previous = {r.fid: r for r in before}
    result = []
    for record in after:
        for rule in profile['fields']:
            path = rule['path']
            raw = previous[record.fid].values.get(path)
            try:
                old = comparable(raw, rule)
            except ValueError:
                old = raw  # Invalid original values may be repaired explicitly.
            new = comparable(record.values.get(path), rule)
            if old != new:
                result.append(dict(object_id=record.fid, field=path, before=old, after=new))
    return result


def _unmodified_lines(obj, edited_fields):
    lines = obj['block'][1:obj['pos']]
    values, spans = properties(lines)
    excluded = {spans[path] for path in edited_fields if path in spans}
    if any(path.startswith('KVALITET.') for path in edited_fields) and 'KVALITET' in spans:
        excluded.add(spans['KVALITET'])
    return [line for index, line in enumerate(lines) if index not in excluded]


def verify_bytes(data, profile, settings, expected, document=None):
    """Parse actual disk bytes, rebuild curves/rings and verify all XYZ and attributes."""
    actual = parse(data)
    if document is None and any(record.kind == 'FLATE' for record in expected):
        # This path checks the exact serialized bytes, QGIS geometry validity,
        # referenced curves, and metadata. It is NOT official SOSI-kontroll.
        codec = 'iso8859-10' if settings.encoding == 'ISO8859-10' else 'utf-8'
        if data != render(expected, profile, settings).encode(codec):
            raise ValueError('Gjeninnlesing: polygonfilen avviker fra kontrollert eksport.')
        origin = coordinate_origin(expected, settings.unit)
        from .polygon_export import expand_polygons
        expanded = expand_polygons(expected, profile, settings, origin)
        checked = source_records(actual)
        if len(checked) != len(expanded) or len(actual['objects']) != len(expanded):
            raise ValueError('Gjeninnlesing: antall KURVE/FLATE-objekter stemmer ikke.')
        if [r.kind for r in checked] != [r.kind for r in expanded]:
            raise ValueError('Gjeninnlesing: geometrityper eller rekkefølge har endret seg.')
        details = header_details(actual)
        if (details['version'], details['crs'], details['height'], details['unit'],
                details['encoding'], details['h_unit']) != (
                '5.0', settings.crs, settings.height, settings.unit,
                settings.encoding, settings.unit):
            raise ValueError('Gjeninnlesing: SOSI-filhode eller koordinatoppløsning er endret.')
        for key in ('producer', 'owner', 'catalogue', 'catalogue_version'):
            if details[key] != getattr(settings, key).strip():
                raise ValueError('Gjeninnlesing: filhodet har endret ' + key + '.')
        return dict(status='BESTÅTT',
                    method='Intern SOSI-parser, QGIS/GEOS og bytekontroll. Ikke ekstern SOSI-kontroll.',
                    objects_checked=len(checked), input_objects=len(expected),
                    boundary_curve_count=sum(r.kind == 'KURVE' for r in checked),
                    geometry_xyz_verified=True, header=details, source_sha256=None,
                    export_sha256=hashlib.sha256(data).hexdigest(), changes=[],
                    geometry_mode='Ny SOSI-flate med refererte rette grenser; avrundet til valgt enhet.',
                    maximum_rounding_metres=settings.unit / 2)
    actual_records = source_records(actual)
    issues = validate(actual_records, profile, settings, preserved=True)
    errors = [i for i in issues if i.severity == 'FEIL']
    if errors:
        first = errors[0]
        raise ValueError(f'Gjeninnlesing feilet for SOSI-ID {first.fid}: {first.attribute} {first.message}')
    if len(actual_records) != len(expected):
        raise ValueError('Gjeninnlesing: antall objekter har endret seg.')
    details = header_details(actual)
    if (details['crs'], details['height'], details['unit'], details['encoding']) != (
            settings.crs, settings.height, settings.unit, settings.encoding):
        raise ValueError('Gjeninnlesing: filhodet stemmer ikke med eksportoppsettet.')
    field_changes = []
    rounding = 0.0
    if document:
        if not document.get('source_sha256'):
            raise ValueError('Importer originalfilen på nytt for å registrere kontrollsum før eksport.')
        if actual['header'] != document['header'] or actual['tail'] != document['tail']:
            raise ValueError('Gjeninnlesing: originalens filhode eller filslutt er endret.')
        baseline = source_records(document)
        field_changes = changes(baseline, expected, profile)
        changed = {}
        for change in field_changes:
            changed.setdefault(change['object_id'], set()).add(change['field'])
        if len(document['objects']) != len(actual['objects']):
            raise ValueError('Gjeninnlesing: antall kildedataobjekter har endret seg.')
        for old, new in zip(document['objects'], actual['objects']):
            if (old['serial'], old['kind'], old['block'][old['pos']:]) != (
                    new['serial'], new['kind'], new['block'][new['pos']:]):
                raise ValueError('Gjeninnlesing: geometri, høyder eller flatereferanser er endret.')
            edited_fields = changed.get(old['serial'], set())
            if _unmodified_lines(old, edited_fields) != _unmodified_lines(new, edited_fields):
                raise ValueError(f"Gjeninnlesing: øvrige egenskaper/kommentarer er endret for {old['serial']}.")
            ignored = set(edited_fields)
            if any(path.startswith('KVALITET.') for path in edited_fields):
                ignored.add('KVALITET')
            # Also protect implicit children of compact KVALITET, outside the profile.
            old_values = {k:v for k,v in old['values'].items() if k not in ignored}
            new_values = {k:v for k,v in new['values'].items() if k not in ignored}
            # A compact quality tuple may introduce explicit trailing '*' placeholders.
            old_values = {k:v for k,v in old_values.items() if v != ''}
            new_values = {k:v for k,v in new_values.items() if v != ''}
            if old_values != new_values:
                raise ValueError('Gjeninnlesing: en annen egenskap ble endret enn de registrerte rettelsene.')
    else:
        origin = coordinate_origin(expected, settings.unit)
        if details['version'] != '5.0' or details['h_unit'] != settings.unit:
            raise ValueError('Gjeninnlesing: feil SOSI-versjon eller høydeenhet.')
        for key in ('producer', 'owner', 'catalogue', 'catalogue_version'):
            if details[key] != getattr(settings, key).strip():
                raise ValueError('Gjeninnlesing: feil verdi i filhodet: ' + key)
    for index, (wanted, got) in enumerate(zip(expected, actual_records), 1):
        if got.fid != (wanted.fid if document else index) or got.kind != wanted.kind:
            raise ValueError('Gjeninnlesing: objekt-ID, rekkefølge eller geometritype har endret seg.')
        if document:
            if got.geometry_wkb != wanted.geometry_wkb or got.coordinates != wanted.coordinates:
                raise ValueError('Gjeninnlesing: XYZ-geometrien er endret.')
        else:
            quantized = [[float(Decimal(v) * Decimal(str(settings.unit)) +
                          Decimal(str(origin[axis] if axis < 2 else 0)))
                          for axis, v in enumerate(scaled_coordinate(c, settings.unit, origin))]
                         for c in wanted.coordinates]
            if got.coordinates != [tuple(c) for c in quantized]:
                raise ValueError('Gjeninnlesing: koordinatene avviker fra valgt avrunding.')
            rounding = max(rounding, max(abs(a-b) for c,d in zip(wanted.coordinates, got.coordinates) for a,b in zip(c,d)))
        for rule in profile['fields']:
            if comparable(got.values.get(rule['path']), rule) != comparable(wanted.values.get(rule['path']), rule):
                raise ValueError(f"Gjeninnlesing: feltverdien {rule['path']} stemmer ikke for {got.fid}.")
    return dict(status='BESTÅTT', method='Intern gjeninnlesing av faktiske filbytes; ikke ekstern SOSI-kontroll',
                objects_checked=len(actual_records), geometry_xyz_verified=True,
                header=details, source_sha256=document.get('source_sha256') if document else None,
                export_sha256=hashlib.sha256(data).hexdigest(), changes=field_changes,
                geometry_mode='Originale geometri-/høyde-/referanseblokker bevart' if document else 'Avrundet etter valgt koordinatoppløsning',
                maximum_rounding_metres=rounding)


def write_verified(path, data, verifier):
    """Verify staged bytes before exclusive publication; confirm published disk bytes."""
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix='.sosi_', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        staged = Path(temporary).read_bytes()
        result = verifier(staged)
        if os.name == 'nt':
            os.rename(temporary, path)
        else:
            os.link(temporary, path)
            os.unlink(temporary)
        if path.read_bytes() != staged:
            raise ValueError(f'Kontroll etter skriving feilet. Filen {path} må ikke leveres.')
        result['disk_readback_verified'] = True
        return result
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def change_report(audit):
    header = audit['header']
    shown = lambda value: '(tom)' if value is None or value == '' else str(value)
    lines = ['SOSI Survey – endringsrapport',
             'Intern delkontroll og gjeninnlesing; full ekstern SOSI-kontroll gjenstår.',
             'Status: Gjeninnlesing fra disk bestått.' if audit.get('disk_readback_verified') else
             'Status: Forhåndskontroll bestått. Denne rapporten bekrefter ikke lagring til disk.',
             f"Kontrollert: {audit['objects_checked']} objekter i hele eksportfilen.",
             'Geometri: ' + audit['geometry_mode'],
             'Original SHA256: ' + (audit['source_sha256'] or 'Ikke SOSI-import; eksport fra QGIS-lag'),
             'Eksport SHA256: ' + audit['export_sha256'],
             f"Filhode: SOSI {header['version']}, {header['crs']}, høydegrunnlag {shown(header['height'])}.",
             f"Planenhet {header['unit']:g} m, høydeenhet {header['h_unit']:g} m, origo NØ {header['origin_ne']}, tegnsett {header['encoding']}.",
             f"Produsent: {shown(header['producer'])}. Eier: {shown(header['owner'])}.",
             f"Objektkatalog: {shown(header['catalogue'])}. Katalogversjon: {shown(header['catalogue_version'])}.",
             f"Registrerte feltendringer: {len(audit['changes'])}"]
    for item in audit['changes']:
        lines.append(f"SOSI-ID {item['object_id']} | {item['field']} | {shown(item['before'])} → {shown(item['after'])}")
    if not audit['source_sha256']:
        lines.append(f"Største avrunding per koordinatkomponent: {audit['maximum_rounding_metres']:.9g} m")
    lines.append('Linjeskift og eventuell UTF-8-BOM kan være normalisert. Originalfilen er beholdt.')
    return '\n'.join(lines) + '\n'
