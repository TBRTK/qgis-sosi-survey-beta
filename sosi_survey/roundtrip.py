# SPDX-License-Identifier: GPL-3.0-or-later
"""Strict straight point/curve reader; retain source coordinates and other properties."""
import re
import hashlib
from decimal import Decimal
from .core import CRS_CODES, normalize, token
from .presentation import read_presentation

QUALITY_FIELDS = ['KVALITET.MÅLEMETODE', 'KVALITET.NØYAKTIGHET',
                  'KVALITET.SYNBARHET', 'KVALITET.H-MÅLEMETODE', 'KVALITET.H-NØYAKTIGHET']
FIELDS = ['OBJTYPE', 'DATAFANGSTDATO'] + QUALITY_FIELDS + [
    'OPPDATERINGSDATO', 'REGFORM', 'VERTNIV',
]

def scalar(text):
    text = text.strip()
    if text.startswith('"') and text.endswith('"'):
        return text[1:-1].replace('""', '"')
    return '' if text == '*' else text

def properties(lines):
    values, spans, parents = {}, {}, {}
    for index, line in enumerate(lines):
        m = re.match(r'^(\.{2,})([^\s.]+)(?:\s+(.*))?$', line)
        if not m:
            continue
        depth, name, value = len(m[1]), m[2], m[3] or ''
        parents = {d:n for d,n in parents.items() if d < depth}
        path = '.'.join([parents[d] for d in sorted(parents)] + [name])
        if not value:
            parents[depth] = name
        if path in values:
            raise ValueError('Gjentatte egenskaper støttes ikke i redigerbar 3D-import: ' + path)
        values[path], spans[path] = scalar(value), index
        if path == 'KVALITET' and value:
            parts = value.split()
            if len(parts) > 6:
                raise ValueError('Ukjent kompakt KVALITET-struktur.')
            quality = QUALITY_FIELDS + ['KVALITET.MAKS-AVVIK']
            for field, part in zip(quality, parts):
                values[field] = scalar(part)
    return values, spans

def parse(data):
    head = data[:131072].decode('latin-1')
    match = re.search(r'^\.\.TEGNSETT\s+(\S+)', head, re.M)
    name = match[1].upper() if match else 'ISO8859-10'
    codecs = {'ISO8859-10':'iso8859-10', 'ISO8859-1':'iso8859-1', 'UTF-8':'utf-8-sig', 'UTF8':'utf-8-sig', 'ANSI':'cp1252'}
    if name not in codecs:
        raise ValueError('Ukjent tegnsett for 3D-import: ' + name)
    text = data.decode(codecs[name])
    lines = text.splitlines()
    starts = [i for i,line in enumerate(lines) if re.match(r'^\.[^.\s]', line)]
    if not starts or lines[starts[0]].strip() != '.HODE' or lines[starts[-1]].strip() != '.SLUTT':
        raise ValueError('Mangler .HODE eller .SLUTT.')
    header = lines[:starts[1]]
    if any(re.match(r'^\.{2,}(GEOKOORD|ORIGO-H|AKSE|ROTASJON)(?:\s|$)', line) for line in header):
        raise ValueError('Ukjent ekstra koordinattransformasjon i filhodet.')
    def header_value(tag, default=None):
        found = [m[1].strip() for line in header if (m := re.match(r'^\.{2,}' + re.escape(tag) + r'\s+(.+)$', line))]
        if len(found) > 1:
            raise ValueError('Tvetydig filhode: ' + tag)
        if not found and default is None:
            raise ValueError('Mangler ' + tag)
        return found[0] if found else default
    crs_code = header_value('KOORDSYS')
    crs = next((crs for crs,code in CRS_CODES.items() if str(code) == crs_code), None)
    if crs is None:
        raise ValueError('3D-redigering støtter foreløpig ETRS89/UTM sone 31–36. Ukjent KOORDSYS: ' + crs_code)
    unit = Decimal(header_value('ENHET'))
    h_unit = Decimal(header_value('ENHET-H', str(unit)))
    origin = [Decimal(v) for v in header_value('ORIGO-NØ', '0 0').split()]
    if len(origin) != 2 or not all(v.is_finite() for v in origin) or not unit.is_finite() or not h_unit.is_finite() or unit <= 0 or h_unit <= 0:
        raise ValueError('Ugyldig origo/enhet.')
    objects, ids = [], set()
    for start, end in zip(starts[1:-1], starts[2:]):
        block = lines[start:end]
        match = re.fullmatch(r'\.(PUNKT|KURVE|BUEP|FLATE|SYMBOL|TEKST)\s+(\d+):?\s*(?:!.*)?', block[0])
        if not match:
            raise ValueError('Ustøttet geometritype: ' + block[0] + '. Støttet: PUNKT, KURVE, BUEP og FLATE.')
        serial = int(match[2])
        if serial in ids:
            raise ValueError('Duplikat objekt-ID.')
        ids.add(serial)
        kind = match[1]
        if kind in ('SYMBOL', 'TEKST'):
            # Preview decoding must never change the preserved SOSI block.
            # Unsupported presentation syntax remains safely unedited.
            try:
                shown_values, shown_coordinates = read_presentation(
                    block, unit, h_unit, origin)
                preview_error = ''
            except ValueError as error:
                shown_values, shown_coordinates = {}, []
                preview_error = str(error)
            objects.append(dict(serial=serial, kind=kind, block=block,
                                pos=1, values=shown_values,
                                coordinates=shown_coordinates, rings=[],
                                opaque=True, presentation_error=preview_error))
            continue
        positions = [i for i, line in enumerate(block)
                     if re.match(r'\.\.(?:REF|NØH|NØ)(?:\s|$)', line)]
        if not positions:
            raise ValueError(f'Objekt {serial}: mangler geometri.')
        pos = positions[0]
        props, spans = properties(block[1:pos])
        if any(key in props for key in ('ENHET', 'ENHET-H', 'TRANSPAR', 'ORIGO-NØ', 'REF', 'GEOKOORD')):
            raise ValueError('Lokale transformasjoner/referanser må håndteres før 3D-redigering.')
        coordinates, ref_parts, mode = [], [], None
        coordinate_dimensions = set()
        for raw_line in block[pos:]:
            line = raw_line.split('!', 1)[0].strip()
            if not line:
                continue
            tag = re.fullmatch(r'\.\.(NØH|NØ|REF)(?:\s+(.*))?', line)
            if tag:
                if tag[1] == 'REF' and (kind != 'FLATE' or ref_parts):
                    raise ValueError('Ugyldig/gjentatt REF.')
                mode = tag[1]
                line = tag[2] or ''
                if not line: continue
            if mode == 'REF':
                ref_parts.append(line)
                continue
            # NØ is a legitimate 2D geometry. Never synthesize Z from the
            # header's height datum. Individual objects must not mix 2D/3D.
            if mode not in ('NØH', 'NØ'):
                raise ValueError(f'Objekt {serial}: ukjent koordinatsyntaks.')
            dimension = 3 if mode == 'NØH' else 2
            coordinate_dimensions.add(dimension)
            # Some older cadastral curves mix NØ and NØH; preserve exact
            # source coordinates, then present a strictly 2D QGIS layer.
            # KP codes (including 999) are source metadata, not heights.
            pattern = r'[+-]?\d+\s+[+-]?\d+' + (r'\s+[+-]?\d+' if dimension == 3 else '') + r'(?:\s+\.{2,3}KP\s+\d+)?'
            if not re.fullmatch(pattern, line):
                raise ValueError(f'Objekt {serial}: ukjent koordinatsyntaks; ingen høyder gjettes.')
            coordinates_text = line.split(' ...KP ')[0].split(' ..KP ')[0]
            numbers = list(map(Decimal, coordinates_text.split()))
            n,e = numbers[:2]
            coordinates.append([float(origin[1]+e*unit), float(origin[0]+n*unit)] +
                               ([float(numbers[2]*h_unit)] if dimension == 3 else []))
        if (kind in ('PUNKT','FLATE') and len(coordinates) != 1) or (kind == 'KURVE' and len(coordinates)<2) or (kind == 'BUEP' and len(coordinates)!=3):
            raise ValueError('Ugyldig antall koordinater.')
        rings = parse_references(' '.join(ref_parts)) if kind == 'FLATE' else []
        objects.append(dict(serial=serial, kind=kind, block=block, pos=pos, values=props,
                            coordinates=coordinates, rings=rings,
                            mixed_dimension=len(coordinate_dimensions)>1))
    if not objects:
        raise ValueError('Ingen punkter/linjer med høyder.')
    return dict(header=header, tail=lines[starts[-1]:], objects=objects, codec=codecs[name],
                crs=crs, height=header_value('VERT-DATUM', ''), unit=float(unit), h_unit=float(h_unit),
                version=header_value('SOSI-VERSJON', 'ikke oppgitt'), encoding=name,
                source_sha256=hashlib.sha256(data).hexdigest(), source_size=len(data))


def header_details(document):
    """Read display/report values from the retained header, never from UI defaults."""
    values, _ = properties(document['header'])
    catalogue = values.get('OBJEKTKATALOG.KORTNAVN', '')
    version = values.get('OBJEKTKATALOG.VERSJON', '')
    compact = next((m[1] for line in document['header'] if
                    (m := re.match(r'^\.\.OBJEKTKATALOG\s+(.+)$', line))), '')
    if compact:
        words = re.findall(r'"(?:[^"]|"")*"|[^\s]+', compact)
        if len(words) >= 2:
            catalogue, version = scalar(words[0]), scalar(words[1])
    encoding = document.get('encoding') or next((name for name, codec in
                    [('ISO8859-10','iso8859-10'), ('ISO8859-1','iso8859-1'),
                     ('ANSI','cp1252'), ('UTF-8','utf-8-sig')] if codec == document['codec']), '')
    return dict(version=document['version'], crs=document['crs'], height=document['height'],
                unit=document['unit'], h_unit=document['h_unit'], encoding=encoding,
                origin_ne=values.get('TRANSPAR.ORIGO-NØ', values.get('ORIGO-NØ', '0 0')),
                producer=values.get('PRODUSENT', ''), owner=values.get('EIER', ''),
                catalogue=catalogue, catalogue_version=version)


def parse_references(text):
    tokens = re.findall(r':[+-]?\d+|[()]', text)
    if re.sub(r':[+-]?\d+|[()]|\s+', '', text) or not tokens:
        raise ValueError('Ugyldig/manglende flatereferanse.')
    rings, current, inside, holes_started = [[]], None, False, False
    for item in tokens:
        if item == '(':
            if inside or not rings[0]: raise ValueError('Ugyldig nøsting av hullreferanser.')
            inside, holes_started, current = True, True, []
        elif item == ')':
            if not inside or not current: raise ValueError('Tomt/ugyldig hull.')
            rings.append(current)
            inside, current = False, None
        else:
            if holes_started and not inside: raise ValueError('Ytterreferanser etter hull støttes ikke.')
            value = int(item[1:])
            if value == 0: raise ValueError('Referanse 0 er ugyldig.')
            (current if inside else rings[0]).append(value)
    if inside: raise ValueError('Uavsluttet hullreferanse.')
    refs = [abs(r) for ring in rings for r in ring]
    if len(refs) != len(set(refs)): raise ValueError('Gjentatt flatereferanse.')
    return rings

def render_preserved(document, records, profile, settings):
    if settings.crs != document['crs'] or settings.height != document['height']:
        raise ValueError('Ved bevarende eksport må CRS og høydegrunnlag være lik originalen. Ingen transformasjon utføres.')
    by_id = {o['serial']:o for o in document['objects']}
    edited_objects = {}
    mapping = document.get('feature_map', {})
    for record in records:
        serial = int(mapping.get(str(record.fid), record.fid))
        if serial in edited_objects: raise ValueError('Duplikat objekt-ID i eksportkopien.')
        edited_objects[serial] = record
    if not set(edited_objects).issubset(by_id): raise ValueError('Objekt mangler i originalfilen.')
    output = list(document['header'])
    for original in document['objects']:
        record = edited_objects.get(original['serial'])
        if record is None:
            output += original['block']
            continue
        expected_coords = original.get('display_coordinates', original['coordinates'])
        if record.kind != original['kind'] or record.coordinates != [tuple(c) for c in expected_coords] or (original.get('geometry_wkb') and record.geometry_wkb != original['geometry_wkb']):
            raise ValueError('Geometrien har endret seg. Bevarende eksport er stoppet.')
        block = original['block']
        props = block[1:original['pos']]
        _, spans = properties(props)
        replacements, additions, insert_after = {}, [], {}
        quality_updates = {}
        for rule in profile['fields']:
            field = rule['path']
            if field not in FIELDS:
                raise ValueError('Feltet støttes ikke av bevarende eksport: ' + field)
            value = normalize(record.values.get(field), rule)
            try:
                old = normalize(original['values'].get(field), rule)
            except ValueError:
                old = object()  # Invalid originals may be corrected explicitly.
            if value == old:
                continue
            formatted = '*' if value is None else token(value) if rule['type'] == 'text' else str(value)
            if field == 'DATAFANGSTDATO' and value is not None:
                formatted = str(value).replace('-', '')
            if field.startswith('KVALITET.') and 'KVALITET' in spans and original['values'].get('KVALITET'):
                quality_updates[field] = formatted
                continue
            depth = field.count('.') + 2
            line = '.'*depth + field.split('.')[-1] + ' ' + formatted
            if field in spans:
                replacements[spans[field]] = line
            elif depth == 2:
                additions.append(line)
            elif 'KVALITET' not in spans:
                quality_updates[field] = formatted
            else:
                insert_after.setdefault(spans['KVALITET'], []).append(line)
        if quality_updates:
            keys = QUALITY_FIELDS + ['KVALITET.MAKS-AVVIK']
            parts = [quality_updates.get(key, original['values'].get(key) or '*') for key in keys]
            while parts and parts[-1] == '*': parts.pop()
            line = '..KVALITET ' + ' '.join(parts)
            if 'KVALITET' in spans: replacements[spans['KVALITET']] = line
            else: additions.append(line)
        edited = []
        for i,line in enumerate(props):
            edited.append(replacements.get(i,line))
            edited.extend(insert_after.get(i, []))
        output += [block[0]] + edited + additions + block[original['pos']:]
    return '\n'.join(output + document['tail']) + '\n'
