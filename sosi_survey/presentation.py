# SPDX-License-Identifier: GPL-3.0-or-later
"""Decode SOSI TEKST/SYMBOL positions for read-only QGIS previews.

The original presentation group is preserved independently of this preview.
This is not a replacement for an official SOSI portrayal specification.
"""
from decimal import Decimal, InvalidOperation
import re

_MARKER = re.compile(r'^\.\.(NØH|NØ)(?:\s|$)')
_ATTRIBUTE = re.compile(r'^\.\.([^\s.]+)(?:\s+(.*))?$')
_COORD = re.compile(r'^[+-]?\d+\s+[+-]?\d+(?:\s+[+-]?\d+)?(?:\s+\.{2,3}KP\s+\d+)?$')


def read_presentation(block, unit, height_unit, origin_ne):
    """Return shallow attributes and original-dimensional position coordinates."""
    values = {}
    coordinates = []
    mode = None
    for line in block[1:]:
        row = line.strip()
        if not row or row.startswith('!'):
            continue
        tag = _MARKER.match(row)
        if tag:
            mode = tag.group(1)
            if row != '..' + mode:
                raise ValueError('Koordinater på samme linje som NØ/NØH støttes ikke for presentasjon.')
            continue
        if mode is None:
            match = _ATTRIBUTE.fullmatch(row)
            if match and match.group(2):
                key, value = match.groups()
                if key in ('OBJTYPE', 'STRENG', 'DIM', 'ARKARTSTD', 'ARTYPE', 'REFMSTK'):
                    value = value.strip()
                    values[key] = (value[1:-1].replace('""', '"')
                                   if len(value) >= 2 and value[0] == '"' and value[-1] == '"'
                                   else value)
            continue
        if row.startswith('.'):
            raise ValueError('Uventet SOSI-tag inne i presentasjonskoordinater.')
        row = row.split('!', 1)[0].strip()
        if not _COORD.fullmatch(row):
            raise ValueError('Ukjent koordinatsyntaks i presentasjonsobjekt.')
        cleaned = re.sub(r'\s+\.{2,3}KP\s+\d+$', '', row)
        parts = cleaned.split()
        expected = 3 if mode == 'NØH' else 2
        if len(parts) != expected:
            raise ValueError('Presentasjonskoordinater har feil dimensjon.')
        try:
            north, east = Decimal(parts[0]), Decimal(parts[1])
            height = Decimal(parts[2]) if expected == 3 else None
            pos = [float(origin_ne[1] + east * unit),
                   float(origin_ne[0] + north * unit)]
            if height is not None:
                pos.append(float(height * height_unit))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError('Ugyldig tallverdi i presentasjonskoordinater.') from exc
        coordinates.append(pos)
    return values, coordinates
