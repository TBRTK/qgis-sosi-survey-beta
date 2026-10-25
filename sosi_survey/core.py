# SPDX-License-Identifier: GPL-3.0-or-later
"""QGIS-independent draft rules and SOSI point/curve writer.

This implements a deliberately restricted subset, not SOSI-kontroll.
Only trusted, declarative JSON profiles are supported; no code is evaluated.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import math
import re


TAG = re.compile(r"^[A-ZÆØÅ][A-ZÆØÅ0-9_-]*$")
CRS_CODES = {f"EPSG:258{zone}": zone - 10 for zone in range(31, 37)}
HEIGHTS = ("NN2000", "NN54", "ELLIP", "LOKAL")


@dataclass
class Record:
    fid: int
    kind: str
    coordinates: list
    values: dict
    geometry_error: str = ""
    geometry_wkb: str = ""
    rings: list | None = None
    refs: list | None = None


@dataclass
class Issue:
    severity: str
    code: str
    message: str
    fid: int | None = None
    attribute: str = ""


@dataclass
class Settings:
    crs: str
    height: str
    unit: float = 0.01
    producer: str = ""
    owner: str = ""
    catalogue: str = ""
    catalogue_version: str = ""
    height_confirmed: bool = False
    encoding: str = "ISO8859-10"


def blank(value):
    return value is None or (isinstance(value, str) and not value.strip())


def validate_profile(profile):
    if profile.get("schema_version") != 1:
        raise ValueError("Profilen må ha schema_version 1.")
    rules = profile.get("fields")
    if not isinstance(rules, list) or not rules:
        raise ValueError("Profilen må ha en ikke-tom fields-liste.")
    paths = []
    for rule in rules:
        path = rule.get("path", "")
        if not isinstance(path, str) or not all(TAG.fullmatch(p) for p in path.split(".")):
            raise ValueError("Ugyldig SOSI-felt i profil.")
        if rule.get("type") not in ("text", "integer", "decimal", "date"):
            raise ValueError(f"Ukjent felttype for {path}.")
        if rule.get("required", False) not in (True, False):
            raise ValueError(f"required må være boolsk: {path}")
        if path.split(".")[0] in {"NØ", "NØH", "NØD", "REF", "HODE", "SLUTT"}:
            raise ValueError("Profilen forsøker å overstyre geometri/filstruktur.")
        if path in paths or any(path.startswith(p + ".") or p.startswith(path + ".") for p in paths):
            raise ValueError(f"Duplisert eller overlappende felt: {path}")
        paths.append(path)
    if "OBJTYPE" not in paths:
        raise ValueError("Profilen må inneholde OBJTYPE.")
    obj = rules[paths.index("OBJTYPE")]
    if obj.get("type") != "text" or not obj.get("required"):
        raise ValueError("OBJTYPE må være påkrevd tekst.")
    for group, members in profile.get("compact_groups", {}).items():
        if not TAG.fullmatch(group) or not isinstance(members, list) or not members or len(set(members)) != len(members):
            raise ValueError("Ugyldig kompakt gruppe i profil.")
        if any(not isinstance(m, str) or not TAG.fullmatch(m) for m in members):
            raise ValueError("Ugyldig gruppemedlem i profil.")
        actual = [p.split(".")[1] for p in paths if p.startswith(group + ".") and p.count(".") == 1]
        if not set(actual).issubset(members) or any(p.count(".") > 1 for p in paths if p.startswith(group + ".")):
            raise ValueError("Kompakt gruppe mangler felt eller har for dyp struktur.")
    return profile


def normalize(value, rule):
    if blank(value):
        return None
    text = str(value).strip()
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise ValueError("Kontrolltegn eller linjeskift er ikke tillatt.")
    kind = rule["type"]
    if kind == "integer":
        if not re.fullmatch(r"[+-]?\d+", text):
            raise ValueError("Må være et heltall.")
        result = int(text)
    elif kind == "decimal":
        try:
            result = Decimal(text.replace(",", "."))
        except Exception:
            raise ValueError("Må være et tall.") from None
        if not result.is_finite():
            raise ValueError("Tallet må være endelig.")
    elif kind == "date":
        try:
            # Preserve dates only; never silently discard a time or time zone.
            fmt = "%Y-%m-%d" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text) else "%Y%m%d"
            if fmt == "%Y%m%d" and not re.fullmatch(r"\d{8}", text):
                raise ValueError()
            result = datetime.strptime(text, fmt).strftime("%Y%m%d")
        except ValueError:
            raise ValueError("Dato må være en gyldig YYYYMMDD eller YYYY-MM-DD.") from None
    else:
        result = text
        if len(text) > rule.get("max_length", 255):
            raise ValueError(f"Maksimalt {rule.get('max_length', 255)} tegn.")
    if "enum" in rule and str(result) not in [str(v) for v in rule["enum"]]:
        raise ValueError("Verdien finnes ikke i profilens kodeliste.")
    if kind in ("integer", "decimal"):
        if "min" in rule and result < Decimal(str(rule["min"])):
            raise ValueError(f"Verdien må være minst {rule['min']}.")
        if "max" in rule and result > Decimal(str(rule["max"])):
            raise ValueError(f"Verdien må være høyst {rule['max']}.")
    return result


def integer_coordinate(value, unit, origin=0):
    return int(((Decimal(str(value)) - Decimal(str(origin))) / Decimal(str(unit))).to_integral_value(rounding=ROUND_HALF_UP))


def coordinate_origin(records, unit):
    # Local integer origin preserves millimetres without overflowing northings.
    valid = [c for r in records
             for c in (r.coordinates + [p for ring in (r.rings or []) for p in ring])
             if len(c) in (2, 3) and
             all(isinstance(v, (int, float)) and math.isfinite(v) for v in c)]
    if unit != 0.001 or not valid:
        return (0, 0)
    return tuple(math.floor(min(c[axis] for c in valid) / 1000) * 1000 for axis in (0, 1))


def scaled_coordinate(coord, unit, origin):
    return tuple(integer_coordinate(v, unit, origin[axis] if axis < 2 else 0) for axis, v in enumerate(coord))


def validate(records, profile, settings, preserved=False):
    validate_profile(profile)
    issues = [Issue("ADVARSEL", "DELKONTROLL", "Kun utkastets oppgitte regler er kontrollert. Ikke Kartverkets SOSI-kontroll.")]
    if not profile.get("approved", False):
        issues.append(Issue("ADVARSEL", "PROFIL_UTKAST", "Foreløpig profil: objekttyper, kodelister og mottakerkrav er ikke verifisert."))
    if profile.get('recipient'):
        issues.append(Issue('ADVARSEL', 'MOTTAKER_UAVKLART',
                            profile.get('delivery_status', 'Mottakerkrav er ikke ferdig avklart.')))
        for requirement in profile.get('unresolved', []):
            issues.append(Issue('ADVARSEL', 'LEVERANSE_MANGLER', str(requirement)))
    if settings.crs not in CRS_CODES:
        issues.append(Issue("FEIL", "KOORDSYS", "Utkastet støtter bare EUREF89 / UTM sone 31–36 (EPSG:25831–25836). Ingen omprojisering utføres."))
    has_z = any(len(c) == 3 for record in records
                for c in (record.coordinates + [p for ring in (record.rings or []) for p in ring]))
    if has_z and (settings.height not in HEIGHTS or not settings.height_confirmed):
        issues.append(Issue("FEIL", "HOYDEGRUNNLAG", "Velg og bekreft høydegrunnlaget. Z-verdier transformeres ikke."))
    if not has_z and not preserved and (settings.height not in HEIGHTS or not settings.height_confirmed):
        issues.append(Issue("FEIL", "HOYDEGRUNNLAG", "Nye SOSI-leveranser krever eksplisitt høydegrunnlag."))
    valid_unit = math.isfinite(settings.unit) and (settings.unit > 0 if preserved else settings.unit in (1.0, 0.1, 0.01, 0.001))
    origin = (0, 0) if preserved else coordinate_origin(records, settings.unit)
    if not valid_unit:
        issues.append(Issue("FEIL", "ENHET", "Velg oppløsning 1, 0.1, 0.01 eller 0.001 meter."))
    if not records:
        issues.append(Issue("FEIL", "TOMT", "Ingen objekter å eksportere."))
    for name in ("producer", "owner", "catalogue", "catalogue_version"):
        try:
            normalize(getattr(settings, name), {"type": "text", "max_length": 100})
        except ValueError as error:
            issues.append(Issue("FEIL", "FILHODE", str(error), attribute=name))
    if bool(settings.catalogue.strip()) != bool(settings.catalogue_version.strip()):
        issues.append(Issue("FEIL", "OBJEKTKATALOG", "Både objektkatalogens kortnavn og versjon må fylles inn, eller begge stå tomme."))
    if not settings.catalogue.strip():
        issues.append(Issue("ADVARSEL", "INGEN_KATALOG", "Ingen objektkatalog er oppgitt. Full ekstern fagkontroll krever riktig katalog og kontrolloppsett."))
    codecs = {"ISO8859-10": "iso8859-10", "UTF-8": "utf-8"}
    if preserved:
        codecs.update({'UTF8':'utf-8', 'ISO8859-1':'iso8859-1', 'ANSI':'cp1252'})
    codec = codecs.get(settings.encoding)
    if codec is None:
        issues.append(Issue("FEIL", "TEGNSETT", "Bare ISO8859-10 og UTF-8 støttes."))
    elif settings.encoding == "UTF-8" and not preserved:
        issues.append(Issue("ADVARSEL", "UTF8_INNLESING", "Lokal QGIS 4.0/GDAL 3.12.2 avviste UTF-8-prøvefilen. ISO8859-10 bestod innlesing. Test UTF-8 i mottakers verktøy."))
    if codec:
        for value in (settings.producer, settings.owner, settings.catalogue, settings.catalogue_version):
            try:
                value.encode(codec)
            except UnicodeEncodeError:
                issues.append(Issue("FEIL", "TEGNSETT", "Tekst i filhodet kan ikke skrives med valgt tegnsett."))
    seen = set()
    for record in records:
        if record.fid in seen:
            issues.append(Issue("FEIL", "DUPLIKAT_ID", "Duplisert objekt-ID.", record.fid))
        seen.add(record.fid)
        if record.geometry_error:
            issues.append(Issue("FEIL", "GEOMETRI", record.geometry_error, record.fid))
        if record.kind not in (("PUNKT", "KURVE", "BUEP", "FLATE")
                               if preserved else ("PUNKT", "KURVE", "FLATE")):
            issues.append(Issue("FEIL", "GEOMETRITYPE",
                                "Ny eksport støtter bare Point, LineString og rett Polygon. Multipart/buer krever bevarende SOSI-import.", record.fid))
        coords = record.coordinates
        if not coords or (record.kind in ("PUNKT", "FLATE") and len(coords) != 1) or (record.kind == "KURVE" and len(coords) < 2):
            issues.append(Issue("FEIL", "ANTALL_KOORDINATER", "Tom geometri eller for få/for mange koordinater.", record.fid))
        dimensions = set()
        quantized = []
        for coord in coords:
            dimensions.add(len(coord))
            if len(coord) not in (2, 3) or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in coord):
                issues.append(Issue("FEIL", "KOORDINAT", "Ugyldig koordinat eller manglende høyde i 3D-geometri.", record.fid))
                continue
            if profile.get("require_z", True) and len(coord) != 3 and not (record.kind == "FLATE" and not preserved):
                issues.append(Issue("FEIL", "MANGLER_Z", "Denne innmålingsprofilen krever høyde for hvert punkt.", record.fid))
            if valid_unit and not preserved:
                point = scaled_coordinate(coord, settings.unit, origin)
                if any(abs(v) > 2147483647 for v in point):
                    issues.append(Issue("FEIL", "KOORDINATOMRAADE", "Koordinat overskrider utkastets 32-bits heltallsgrense etter valg av origo; velg grovere oppløsning.", record.fid))
                if quantized and point[:2] == quantized[-1][:2]:
                    issues.append(Issue("FEIL", "SAMMENFALL", "To påfølgende linjepunkter faller sammen i plan etter avrunding.", record.fid))
                quantized.append(point)
        if len(dimensions) > 1:
            issues.append(Issue("FEIL", "DIMENSJON", "Blandet 2D/3D i samme objekt.", record.fid))
        if record.kind == "FLATE" and not preserved:
            if not record.rings:
                issues.append(Issue("FEIL", "RING", "Flaten mangler ytre polygonring.", record.fid))
            else:
                ring_dimensions = set()
                for number, ring in enumerate(record.rings, 1):
                    if len(ring) < 4 or tuple(ring[0]) != tuple(ring[-1]):
                        issues.append(Issue("FEIL", "RING", f"Ring {number} er ikke lukket.", record.fid))
                        continue
                    if len(set(tuple(p[:2]) for p in ring[:-1])) < 3:
                        issues.append(Issue("FEIL", "RING", f"Ring {number} har for få unike hjørner.", record.fid))
                    last_xy = None
                    for point in ring:
                        if len(point) not in (2, 3) or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in point):
                            issues.append(Issue("FEIL", "KOORDINAT", f"Ring {number} har ugyldige koordinater.", record.fid))
                            continue
                        ring_dimensions.add(len(point))
                        if profile.get("require_z", True) and len(point) != 3:
                            issues.append(Issue("FEIL", "MANGLER_Z", f"Ring {number} mangler Z.", record.fid))
                        if valid_unit:
                            quant = scaled_coordinate(point, settings.unit, origin)
                            if any(abs(value) > 2147483647 for value in quant):
                                issues.append(Issue("FEIL", "KOORDINATOMRAADE", f"Ring {number} overskrider koordinatgrensen.", record.fid))
                            if last_xy == quant[:2]:
                                issues.append(Issue("FEIL", "KANTRUNDING", f"En kant i ring {number} kollapser etter avrunding.", record.fid))
                            last_xy = quant[:2]
                if len(ring_dimensions) != 1:
                    issues.append(Issue("FEIL", "DIMENSJON", "Alle polygonringer må ha lik 2D-/3D-dimensjon.", record.fid))
            if not isinstance(profile.get("boundary_objtype"), str) or not profile.get("boundary_objtype", "").strip():
                issues.append(Issue("FEIL", "GRENSETYPE",
                                    "Eksportprofilen må angi boundary_objtype for nye FLATE-grenser.", record.fid))
            if any(rule.get("required") and rule["path"] != "OBJTYPE" for rule in profile["fields"]):
                issues.append(Issue("FEIL", "GRENSEFELT",
                                    "Profilens ekstra obligatoriske felter er ikke definert for automatisk opprettede KURVE-objekter.", record.fid))
        for rule in profile["fields"]:
            value = record.values.get(rule["path"])
            if blank(value) and rule.get("required"):
                issues.append(Issue("FEIL", "PAKREVD", "Påkrevd verdi mangler i valgt profil.", record.fid, rule["path"]))
            elif not blank(value):
                try:
                    normalize(value, rule)
                    if codec:
                        str(value).encode(codec)
                except UnicodeEncodeError:
                    issues.append(Issue("FEIL", "TEGNSETT", "Verdien inneholder tegn som ikke støttes av valgt tegnsett.", record.fid, rule["path"]))
                except ValueError as error:
                    issues.append(Issue("FEIL", "FELTVERDI", str(error), record.fid, rule["path"]))
    return issues


def token(value):
    # Quote all text and double embedded quotation marks (SOSI text escaping).
    if isinstance(value, str):
        return '"' + value.replace('"', '""') + '"'
    return str(value)


def render(records, profile, settings):
    issues = validate(records, profile, settings)
    if any(issue.severity == "FEIL" for issue in issues):
        raise ValueError("Eksport er blokkert: rett alle feil og kjør kontroll på nytt.")
    origin = coordinate_origin(records, settings.unit)
    if any(record.kind == "FLATE" for record in records):
        from .polygon_export import expand_polygons
        export_records = expand_polygons(records, profile, settings, origin)
    else:
        export_records = records
    scaled = [[scaled_coordinate(c, settings.unit, origin) for c in r.coordinates] for r in export_records]
    # Bounds enclose actual exported (quantized) coordinates, in whole metres.
    east = [p[0] * settings.unit + origin[0] for coords in scaled for p in coords]
    north = [p[1] * settings.unit + origin[1] for coords in scaled for p in coords]
    lines = [".HODE", f"..TEGNSETT {settings.encoding}", "..SOSI-VERSJON 5.0", "..TRANSPAR",
             f"...KOORDSYS {CRS_CODES[settings.crs]}", f"...ORIGO-NØ {origin[1]} {origin[0]}",
             f"...ENHET {settings.unit:g}", f"...ENHET-H {settings.unit:g}",
             f"...VERT-DATUM {settings.height}", "..OMRÅDE",
             f"...MIN-NØ {math.floor(min(north))} {math.floor(min(east))}",
             f"...MAX-NØ {math.ceil(max(north))} {math.ceil(max(east))}"]
    if settings.catalogue.strip():
        lines.append(f"..OBJEKTKATALOG {token(settings.catalogue.strip())} {token(settings.catalogue_version.strip())}")
    for tag, value in (("PRODUSENT", settings.producer), ("EIER", settings.owner)):
        if value.strip():
            lines.append(f"..{tag} {token(value.strip())}")
    lines.append("! Utkast SOSI Survey 0.5.2. Kun delkontroll; ikke godkjent leveranse.")
    for serial, (record, coords) in enumerate(zip(export_records, scaled), 1):
        lines.append(f".{record.kind} {serial}:")
        # Build a tree so siblings in a grouped SOSI property stay together.
        tree = {}
        for rule in profile["fields"]:
            value = normalize(record.values.get(rule["path"]), rule)
            if value is None:
                continue
            branch = tree
            parts = rule["path"].split(".")
            for part in parts[:-1]:
                branch = branch.setdefault(part, {})
            branch[parts[-1]] = (value, rule["type"])
        def emit(branch, depth=2):
            for name, value in branch.items():
                if isinstance(value, dict):
                    members = profile.get("compact_groups", {}).get(name) if depth == 2 else None
                    if members:
                        tokens = []
                        for member in members:
                            node = value.get(member)
                            tokens.append("*" if node is None else token(node[0]) if node[1] == "text" else str(node[0]))
                        while tokens and tokens[-1] == "*":
                            tokens.pop()
                        lines.append("." * depth + name + " " + " ".join(tokens))
                    else:
                        lines.append("." * depth + name)
                        emit(value, depth + 1)
                else:
                    scalar, kind = value
                    lines.append("." * depth + name + " " + (token(scalar) if kind == "text" else str(scalar)))
        emit(tree)
        if record.kind == "FLATE":
            if not record.refs or not record.refs[0]:
                raise ValueError("Flateeksport mangler SOSI-referanser til grensekurver.")
            lines.append("..REF " + " ".join(":" + str(ref) for ref in record.refs[0]))
            for hole in record.refs[1:]:
                lines.append("(" + " ".join(":" + str(ref) for ref in hole) + ")")
        lines.append("..NØH" if len(coords[0]) == 3 else "..NØ")
        for point in coords:
            lines.append(" ".join(str(v) for v in (point[1], point[0], *point[2:])))
    lines.append(".SLUTT")
    return "\n".join(lines) + "\n"
