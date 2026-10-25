# SPDX-License-Identifier: GPL-3.0-or-later
"""Receiver-neutral building-outline geometry from reviewed measured corners.

Source measurements are immutable. This is geometric documentation only:
neither FKB feature classification nor municipality delivery approval.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from math import hypot, isfinite

VALID_REFERENCES = ('grunnmur', 'fasadeliv', 'takkant', 'annet')
VALID_HEIGHTS = ('NN2000', 'NN54', 'ELLIP', 'LOKAL')
VALID_CRS = tuple('EPSG:258' + str(zone) for zone in range(31, 37))
MAX_CORNERS = 120


@dataclass(frozen=True)
class MeasuredCorner:
    key: str
    easting: float
    northing: float
    elevation: float | None = None
    point_id: str = ''
    code: str = ''
    description: str = ''
    source_row: str = ''
    source_hash: str = ''


@dataclass(frozen=True)
class BuildingOutline:
    vertices: tuple
    corners: tuple
    geometry_kind: str
    measured_reference: str
    crs: str
    height_reference: str
    includes_z: bool
    area_m2: float
    perimeter_m: float
    warnings: tuple


def _cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (
        b[1] - a[1]) * (c[0] - a[0])


def _point_on_segment(p, a, b):
    tolerance = 1e-9 * max(1.0, hypot(b[0] - a[0], b[1] - a[1]))
    return (
        abs(_cross(a, b, p)) <= tolerance
        and min(a[0], b[0]) - tolerance <= p[0] <= max(a[0], b[0]) + tolerance
        and min(a[1], b[1]) - tolerance <= p[1] <= max(a[1], b[1]) + tolerance
    )


def _intersects(a, b, c, d):
    ab_c, ab_d = _cross(a, b, c), _cross(a, b, d)
    cd_a, cd_b = _cross(c, d, a), _cross(c, d, b)
    eps = 1e-10
    if (ab_c > eps and ab_d < -eps or ab_c < -eps and ab_d > eps) and (
            cd_a > eps and cd_b < -eps or cd_a < -eps and cd_b > eps):
        return True
    return any((_point_on_segment(p, q, r) for p, q, r in (
        (c, a, b), (d, a, b), (a, c, d), (b, c, d))))


def _signed_area(points):
    origin_x, origin_y = points[0][:2]
    return sum(
        (a[0] - origin_x) * (b[1] - origin_y)
        - (b[0] - origin_x) * (a[1] - origin_y)
        for a, b in zip(points, points[1:] + points[:1])
    ) / 2.0


def _validate_ring(points):
    n = len(points)
    if len({(p[0], p[1]) for p in points}) != n:
        raise ValueError('To hushjørner har samme øst-/nordkoordinat.')
    for i in range(n):
        a, b = points[i], points[(i + 1) % n]
        if a[:2] == b[:2]:
            raise ValueError('To påfølgende hushjørner er sammenfallende.')
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue
            c, d = points[j], points[(j + 1) % n]
            if _intersects(a, b, c, d):
                raise ValueError(
                    'Bygningsomrisset krysser eller berører seg selv. '
                    'Kontroller hjørnerekkefølgen.')
    if abs(_signed_area(points)) <= 1e-7:
        raise ValueError('Hushjørnene danner ikke en flate med positivt areal.')


def _quantize(value, unit):
    return int((Decimal(str(value)) / Decimal(str(unit))).to_integral_value(
        rounding=ROUND_HALF_UP))


def make_building_outline(corners, *, crs, measured_reference,
                          geometry_kind='LINE', include_z=False,
                          height_reference='', order_confirmed=False,
                          coordinate_unit=0.01):
    """Build a closed line or polygon WITHOUT changing the source records.

    Corner order is exactly the operator-supplied order; never automatically
    sort by point name or infer wall geometry from a GNSS code.
    """
    ordered = tuple(corners)
    if not order_confirmed:
        raise ValueError('Bekreft rekkefølgen på hushjørnene før omrisset lages.')
    if crs not in VALID_CRS:
        raise ValueError('Kilden må være i bekreftet EUREF89/UTM 31–36.')
    if measured_reference not in VALID_REFERENCES:
        raise ValueError('Angi om målingen gjelder grunnmur, fasade eller takkant.')
    if geometry_kind not in ('LINE', 'POLYGON'):
        raise ValueError('Velg lukket linje eller polygon.')
    if not (3 <= len(ordered) <= MAX_CORNERS):
        raise ValueError('Velg 3–120 hjørnepunkter fra samme bygningsomriss.')
    if not (isfinite(coordinate_unit) and coordinate_unit > 0):
        raise ValueError('Ugyldig koordinatoppløsning.')
    keys = [str(p.key) for p in ordered]
    if any(not key.strip() for key in keys) or len(set(keys)) != len(keys):
        raise ValueError('Punktene må ha unike QGIS-identifikatorer.')
    points = []
    for corner in ordered:
        x, y = float(corner.easting), float(corner.northing)
        if not isfinite(x) or not isfinite(y):
            raise ValueError('Et hjørne har ugyldig øst-/nordkoordinat.')
        if corner.elevation is not None and not isfinite(float(corner.elevation)):
            raise ValueError('Et hjørne har ugyldig registrert høyde.')
        if include_z:
            if corner.elevation is None:
                raise ValueError('3D-omriss krever målt Z for samtlige hjørner.')
            points.append((x, y, float(corner.elevation)))
        else:
            points.append((x, y))
    if include_z and height_reference not in VALID_HEIGHTS:
        raise ValueError('Bekreft høydegrunnlaget før 3D-omriss opprettes.')
    _validate_ring(points)
    rounded = [(_quantize(p[0], coordinate_unit),
                _quantize(p[1], coordinate_unit)) for p in points]
    try:
        _validate_ring(rounded)
    except ValueError as error:
        raise ValueError(
            'Omrisset blir ugyldig ved valgt SOSI-koordinatoppløsning: '
            + str(error)) from error
    area = abs(_signed_area(points))
    perimeter = sum(hypot(b[0] - a[0], b[1] - a[1])
                    for a, b in zip(points, points[1:] + points[:1]))
    warnings = []
    if not include_z and any(p.elevation is not None for p in ordered):
        warnings.append('Omrisset er 2D. Originale Z-verdier beholdes bare i sporingsdata.')
    if geometry_kind == 'POLYGON':
        warnings.append('Ny polygon krever godkjent SOSI-grenseprofil før FKB-leveranse.')
    warnings.append('OBJTYPE og målekvalitet må bekreftes mot mottakerens krav.')
    return BuildingOutline(
        tuple(points + [points[0]]), ordered, geometry_kind,
        measured_reference, crs, height_reference if include_z else '',
        bool(include_z), area, perimeter, tuple(warnings))
