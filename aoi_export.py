"""Export an Earth Engine polygon geometry to GeoJSON, KML, and KMZ files.

Used by AOI_Selector.ipynb after an AOI is drawn on the map, but the
functions only need an ee.Geometry (or an equivalent GeoJSON dict), so they
work outside a notebook too.
"""

import json
from pathlib import Path

import ee
import simplekml


def _to_coordinates(geometry):
    """Return the raw GeoJSON 'coordinates' array for a Polygon geometry."""
    if isinstance(geometry, ee.Geometry):
        geom_info = geometry.getInfo()
    elif isinstance(geometry, dict):
        geom_info = geometry.get("geometry", geometry)
    else:
        raise TypeError("geometry must be an ee.Geometry or a GeoJSON-like dict")

    if geom_info["type"] != "Polygon":
        raise ValueError(
            f"Expected a Polygon geometry, got '{geom_info['type']}'. "
            "Draw the AOI with the rectangle or polygon tool."
        )

    return geom_info["coordinates"]


def export_geojson(geometry, out_path, name="AOI"):
    """Write the geometry as a single-feature GeoJSON FeatureCollection."""
    coordinates = _to_coordinates(geometry)
    feature_collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": name},
                "geometry": {"type": "Polygon", "coordinates": coordinates},
            }
        ],
    }
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(feature_collection, indent=2))
    return out_path


def _build_kml(geometry, name):
    coordinates = _to_coordinates(geometry)
    outer_ring = [(lon, lat) for lon, lat in coordinates[0]]
    holes = [[(lon, lat) for lon, lat in ring] for ring in coordinates[1:]]

    kml = simplekml.Kml()
    polygon = kml.newpolygon(name=name)
    polygon.outerboundaryis = outer_ring
    if holes:
        polygon.innerboundaryis = holes
    polygon.style.linestyle.width = 2
    polygon.style.linestyle.color = simplekml.Color.red
    polygon.style.polystyle.fill = 0
    return kml


def export_kml(geometry, out_path, name="AOI"):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _build_kml(geometry, name).save(str(out_path))
    return out_path


def export_kmz(geometry, out_path, name="AOI"):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _build_kml(geometry, name).savekmz(str(out_path))
    return out_path


def export_all(geometry, out_dir, name="AOI"):
    """Write geojson/kml/kmz versions of the geometry into out_dir, all named `name`."""
    out_dir = Path(out_dir)
    return {
        "geojson": export_geojson(geometry, out_dir / f"{name}.geojson", name=name),
        "kml": export_kml(geometry, out_dir / f"{name}.kml", name=name),
        "kmz": export_kmz(geometry, out_dir / f"{name}.kmz", name=name),
    }


def load_geometry(geojson_path):
    """Load an ee.Geometry.Polygon back from a GeoJSON file written by export_geojson."""
    geojson_path = Path(geojson_path)
    data = json.loads(geojson_path.read_text())
    coordinates = data["features"][0]["geometry"]["coordinates"]
    return ee.Geometry.Polygon(coordinates)
