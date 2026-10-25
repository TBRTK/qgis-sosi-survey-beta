# SPDX-License-Identifier: GPL-3.0-or-later
"""Receiver-neutral delimited field point imports, independent of QGIS.

No source coordinates are transformed, elevations inferred or survey codes
silently mapped to SOSI object types. Preserve all source values as strings.
"""
from dataclasses import dataclass
from pathlib import Path
from io import StringIO
import csv
import hashlib
import math
import re
import unicodedata

SUPPORTED_ENCODINGS = ('utf-8-sig', 'iso-8859-10', 'cp1252')
ALLOWED_CRS = tuple('EPSG:258' + str(i) for i in range(31, 37))
HEADER_ALIASES = {
    'easting': ('easting', 'east', 'utm_easting', 'utme', 'x', 'ost', 'ostkoord', 'e'),
    'northing': ('northing', 'north', 'utm_northing', 'utmn', 'y', 'nord', 'nordkoord', 'n'),
    'elevation': ('elevation', 'height', 'hoyde', 'altitude', 'z', 'kote', 'h'),
    'point_id': ('name', 'point_id', 'pointid', 'pointnumber', 'point_number', 'ptid', 'id', 'punktnummer', 'punktnavn', 'nr'),
    'code': ('code', 'featurecode', 'feature_code', 'surveycode', 'survey_code', 'kode'),
    'description': ('description', 'desc', 'beskrivelse', 'comment', 'comments', 'note', 'notes', 'merknad'),
}
RESERVED_COLUMNS = {'source_id', 'source_code', 'source_description', 'source_row',
                    'source_file_sha256', 'source_columns_json', 'source_crs',
                    'source_height_reference'}


def normalized(name):
    # Normalize only for matching/column names; preserve original source text.
    text = name.casefold().replace('ø', 'o').replace('æ', 'ae').replace('å', 'a')
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return re.sub('[^a-z0-9]', '', text)


def suggest_columns(headers):
    """Suggestions only; an operator must confirm mappings in the import UI."""
    lookup = {normalized(h): h for h in headers}
    return {semantic: next((lookup[normalized(alias)] for alias in aliases
                            if normalized(alias) in lookup), None)
            for semantic, aliases in HEADER_ALIASES.items()}


@dataclass(frozen=True)
class CsvData:
    headers: tuple
    rows: tuple
    delimiter: str
    encoding: str
    sha256: str
    filename: str


@dataclass(frozen=True)
class FieldMapping:
    easting: str
    northing: str
    elevation: str | None = None
    point_id: str | None = None
    code: str | None = None
    description: str | None = None
    crs: str = ''
    height_reference: str | None = None
    reviewed: bool = False


@dataclass(frozen=True)
class FieldPoint:
    source_row: int
    easting: float
    northing: float
    elevation: float | None
    point_id: str
    code: str
    description: str
    raw: dict


def read_delimited(path, encoding='utf-8-sig', delimiter='auto',
                   max_bytes=30_000_000, max_rows=100_000):
    if encoding not in SUPPORTED_ENCODINGS:
        raise ValueError('Velg et støttet tegnsett i importdialogen.')
    if delimiter not in ('auto', ',', ';', '\t'):
        raise ValueError('Ugyldig skilletegn.')
    source = Path(path)
    if not source.is_file() or source.stat().st_size > max_bytes:
        raise ValueError('Filen finnes ikke eller overstiger grensen for feltimport.')
    data = source.read_bytes()
    if not data or b'\x00' in data:
        raise ValueError('Filen er tom eller er ikke en tekstbasert CSV-fil.')
    text = data.decode(encoding, errors='strict')
    if delimiter == 'auto':
        try:
            dialect = csv.Sniffer().sniff(text[:12000], delimiters=',;\t')
            sep = dialect.delimiter
        except csv.Error as error:
            raise ValueError('Kunne ikke bestemme skilletegn. Velg skilletegn manuelt.') from error
    else:
        sep = delimiter
        dialect = csv.excel()
        dialect.delimiter = sep
    reader = csv.reader(StringIO(text, newline=''), dialect)
    try:
        original = next(reader)
    except StopIteration as error:
        raise ValueError('Filen mangler kolonneoverskrifter.') from error
    headers = tuple(h.strip() for h in original)
    if len(headers) < 2 or any(not h for h in headers):
        raise ValueError('CSV må ha minst to navngitte kolonner.')
    if len({h.casefold() for h in headers}) != len(headers):
        raise ValueError('CSV inneholder dupliserte kolonnenavn.')
    rows = []
    for row in reader:
        if not any(value.strip() for value in row):
            continue
        if len(row) != len(headers):
            raise ValueError(f'Rad {reader.line_num}: {len(row)} verdier, forventet {len(headers)}.')
        if len(rows) >= max_rows:
            raise ValueError('For mange punkter til å importere i ett oppdrag.')
        rows.append(dict(zip(headers, row)))
    if not rows:
        raise ValueError('Fant ingen målerader i CSV-filen.')
    return CsvData(headers, tuple(rows), sep, encoding,
                   hashlib.sha256(data).hexdigest(), source.name)


def parse_number(value, field, row):
    s = str(value).strip().replace(',', '.')
    try:
        n = float(s)
    except (ValueError, TypeError) as error:
        raise ValueError(f'Rad {row}: ugyldig verdi for {field}: {value!r}.') from error
    if not math.isfinite(n):
        raise ValueError(f'Rad {row}: {field} må være et endelig tall.')
    return n


def make_points(dataset, mapping):
    if not mapping.reviewed:
        raise ValueError('Bekreft kildekoordinater og akser før import.')
    if mapping.crs not in ALLOWED_CRS:
        raise ValueError('Velg dokumentert EUREF89 / UTM sone 31–36; NTM er ikke konvertert.')
    if not mapping.easting or not mapping.northing or mapping.easting == mapping.northing:
        raise ValueError('Øst og nord må komme fra forskjellige kolonner.')
    for column in (mapping.easting, mapping.northing, mapping.elevation,
                   mapping.point_id, mapping.code, mapping.description):
        if column is not None and column not in dataset.headers:
            raise ValueError('Ukjent kildekolonne: ' + str(column))
    if mapping.elevation and mapping.height_reference not in ('NN2000', 'NN54', 'ELLIP', 'LOKAL'):
        raise ValueError('Velg og bekreft høydegrunnlag før 3D-import.')
    if not mapping.elevation and mapping.height_reference:
        raise ValueError('Høydegrunnlag er valgt, men ingen høydekolonne.')
    points = []
    for row_number, raw in enumerate(dataset.rows, start=2):
        easting = parse_number(raw[mapping.easting], 'øst', row_number)
        northing = parse_number(raw[mapping.northing], 'nord', row_number)
        if abs(easting) <= 180 and abs(northing) <= 90:
            raise ValueError(f'Rad {row_number}: koordinatene ligner grader, ikke UTM-meter.')
        elevation = parse_number(raw[mapping.elevation], 'høyde', row_number) if mapping.elevation else None
        points.append(FieldPoint(row_number, easting, northing, elevation,
                                 raw[mapping.point_id].strip() if mapping.point_id else '',
                                 raw[mapping.code].strip() if mapping.code else '',
                                 raw[mapping.description].strip() if mapping.description else '',
                                 dict(raw)))
    return tuple(points)


def source_field_names(headers, reserved=()):
    """Safe unique column names; original header mapping is retained as JSON."""
    used = set(RESERVED_COLUMNS) | {str(f).casefold() for f in reserved}
    result = {}
    for header in headers:
        stem = normalized(header)[:42] or 'field'
        candidate = 'src_' + stem
        number = 2
        while candidate.casefold() in used:
            candidate = 'src_' + stem + '_' + str(number)
            number += 1
        result[header] = candidate
        used.add(candidate.casefold())
    return result
