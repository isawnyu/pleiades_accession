#
# This file is part of pleiades_accession
# by Tom Elliott for the Institute for the Study of the Ancient World
# (c) Copyright 2025 by New York University
# Licensed under the AGPL-3.0; see LICENSE.txt file.
#

"""
Manage Pleiades data and queries
"""
import csv
from datetime import datetime, timedelta
import functools
import json
import logging
from math import cos, radians
from pathlib import Path
from platformdirs import user_cache_path
from pleiades_local.filesystem import (
    PleiadesFilesystem,
    PleiadesFilesystemNotIndexedError,
)
from pprint import pformat
from shapely import concave_hull, convex_hull, from_geojson, to_geojson, STRtree
from shapely.errors import GEOSException
from shapely.geometry import GeometryCollection, shape
from urllib.parse import urlparse

hull_cache_path = user_cache_path("pleiades_accession") / "hulls"
hull_cache_path.mkdir(parents=True, exist_ok=True)


@functools.lru_cache(maxsize=None)
def meters_to_degrees(m, origin_latitude):
    """
    Convert meters to degrees latitude/longitude at the specified origin latitude
    https://gis.stackexchange.com/questions/2951/algorithm-for-offsetting-latitude-longitude-by-some-amount-of-meters
    """
    lat = m / 111111
    lon = m / (111111 * cos(radians(origin_latitude)))
    return (lat + lon) / 2


class PleiadesPlace:
    """
    Wrapper for a single Pleiades place resource
    """

    def __init__(self, places: PleiadesFilesystem, pid: str):
        """Get and wrap a PleiadesPlace from a place resource dictionary."""
        self.pid = pid
        self._raw_data = places.get(pid)

    @functools.lru_cache(maxsize=None)
    def as_dict(self) -> dict:
        """Return the raw data as a dictionary."""
        d = {
            "pid": self.pid,
            "uri": f"https://pleiades.stoa.org/places/{self.pid}",
            "title": self.title,
            "name_strings": list(self.name_strings),
            "precision": self.precision,
            # "raw_data": self._raw_data,
        }
        return d

    @property
    @functools.lru_cache(maxsize=None)
    def name_strings(self) -> set:
        """Return a set containing all name strings for the place."""
        name_strings = set()
        title = self.title
        for tpart in [t.strip() for t in title.split("/") if t.strip()]:
            if not (tpart.startswith("()") and tpart.endswith(")")):
                name_strings.add(tpart)
        for name in self._raw_data["names"]:
            try:
                attested = name["attested"].strip()
            except AttributeError:
                attested = None
            if attested:
                name_strings.add(attested)
            for romanized in [
                n.strip() for n in name["romanized"].split(",") if n.strip()
            ]:
                name_strings.add(romanized)
        return name_strings

    @property
    @functools.lru_cache(maxsize=None)
    def footprint(self):
        """Calculate and return the spatial footprint, including accuracy, of all combined locations."""
        this_cache_path = hull_cache_path / f"{self.pid}.geojson"
        if this_cache_path.is_file():
            timestamp = this_cache_path.stat().st_mtime
            dt = datetime.fromtimestamp(timestamp)
            if datetime.now() - dt < timedelta(days=1):
                with open(this_cache_path, "r", encoding="utf-8") as f:
                    geo_str = f.read()
                del f
                if geo_str:
                    return from_geojson(geo_str)
                else:
                    return None

        geometries = dict()
        for i, loc in enumerate(self._raw_data.get("locations", [])):
            if (
                loc["geometry"]
                and self._raw_data["features"][i]["properties"]["location_precision"]
                == "precise"
            ):
                geometries[i] = shape(loc["geometry"])
        self.geometries = geometries.values()
        self.buffered_geometries = list()
        for i, geom in geometries.items():
            accuracy_value = self._raw_data["locations"][i]["accuracy_value"]
            if accuracy_value is None:
                raise RuntimeError(
                    f"Location {self._raw_data['locations'][i]['id']} on {self.pid} has no accuracy_value"
                )
            if "darmc" in self._raw_data["locations"][i]["accuracy"]:
                accuracy_value = max(
                    accuracy_value, 2000.0
                )  # fudge factor for DARMC relocations to modern labels in GE
            centroid = geometries[i].centroid
            self.buffered_geometries.append(
                geom.buffer(meters_to_degrees(accuracy_value, centroid.y))
            )
        if self.buffered_geometries:
            try:
                h = concave_hull(GeometryCollection(self.buffered_geometries), 0.2)
            except GEOSException:
                try:
                    h = convex_hull(GeometryCollection(self.buffered_geometries))
                except GEOSException as err:
                    err.add_note(
                        f"Failed creation of both concave and convex hulls with {len(self.buffered_geometries)} buffered geometries for pid: '{self.pid}'"
                    )
                    raise err
                else:
                    h = concave_hull(h, 0.2)
        else:
            h = None
        with open(this_cache_path, "w", encoding="utf-8") as f:
            geojson = to_geojson(h)
            if geojson:
                f.write(geojson)
            else:
                f.write("")
        del f
        return h

    @property
    @functools.lru_cache(maxsize=None)
    def place_type_uris(self) -> set:
        """Return a set containing all place types for the place."""
        place_types = {pt for pt in self._raw_data.get("placeTypeURIs", []) if pt}
        for loc in self._raw_data.get("locations", []):
            place_types.update(loc.get("locationTypeURI", []))
        return place_types

    @property
    @functools.lru_cache(maxsize=None)
    def precision(self) -> str:
        """Return the overall precision of the place."""
        precisions = set()
        for i, loc in enumerate(self._raw_data.get("locations", [])):
            if loc["geometry"]:
                precisions.add(
                    self._raw_data["features"][i]["properties"]["location_precision"]
                )
        if "precise" in precisions:
            return "precise"
        elif "rough" in precisions:
            return "rough"
        else:
            return "unknown"

    @property
    def title(self) -> str:
        """Return the title of the place."""
        return self._raw_data["title"].strip()


class Pleiades:
    """
    Manage Pleiades data and queries
    """

    def __init__(self, root_path: Path, names_index_path: Path = None):  # type: ignore
        """Initialize the Pleiades filesystem manager, which will generate a catalog of
        JSON files if needed."""
        logger = logging.getLogger(f"{__name__}:Pleiades.__init__")
        if not isinstance(root_path, Path):
            self.root_path = Path(root_path)
        else:
            self.root_path = root_path
        self.fs = PleiadesFilesystem(root_path)
        self.places = dict()
        logger.info(f"Loaded {len(self.fs):,} Pleiades place resources.")
        self.names_index = dict()
        self._initialize_names_index(names_index_path)
        self._place_type_vocabulary = dict()
        self._spatial_index = None
        self._spatial_index_2_pid = dict()
        self._initialize_spatial_index()
        self._initialize_links_index()

    def get(self, pid) -> PleiadesPlace | None:
        """Get the Pleiades place resource for the specified pid."""
        logger = logging.getLogger(f"{__name__}:Pleiades.get")
        try:
            return self.places[pid]
        except KeyError:
            try:
                p = PleiadesPlace(self.fs, pid)
            except PleiadesFilesystemNotIndexedError as err:
                logger.error(str(err))
                return None
            else:
                self.places[pid] = p
                return p

    def get_links_by_pid(self, pid, target_netloc: str = "") -> list:
        """Get all links associated with a particular pid."""
        try:
            links = self._links_by_pids[pid]
        except KeyError:
            return []
        if target_netloc:
            return [link for link in links if urlparse(link).netloc == target_netloc]
        else:
            return list(links)

    def get_pid_by_link(self, link, netloc=None) -> str | None:
        """Get the Pleiades place resource for the specified link."""
        try:
            return self._links_index[link]
        except KeyError:
            return

    def _initialize_links_index(self):
        """Initialize the links index."""
        logger = logging.getLogger(f"{__name__}:Pleiades._initialize_links_index")
        self._links_index = dict()
        self._links_by_pids = dict()
        for pid in self.fs.index.keys():  # type: ignore
            self._links_by_pids[pid] = set()
            place = self.get(pid)
            for ref in place._raw_data.get("references", []):  # type: ignore
                uri = ref.get("accessURI", "").strip()
                if not uri:
                    continue
                netloc = urlparse(uri).netloc.lower()
                try:
                    self._links_index[uri]
                except KeyError:
                    self._links_index[uri] = set()
                self._links_index[uri].add(pid)
                self._links_by_pids[pid].add(uri)

        logger.info(
            f"Generated links index with {len(self._links_index):,} links from Pleiades data"
        )

    def _initialize_names_index(self, names_index_path: Path = None):  # type: ignore
        """Initialize the names index, generating it if needed."""
        logger = logging.getLogger(f"{__name__}:Pleiades._initialize_names_index")
        if names_index_path:
            self._load_names_index(names_index_path)
        else:
            for pid in self.fs.index.keys():
                place = self.get(pid)
                for name_string in place.name_strings:
                    try:
                        self.names_index[name_string]
                    except KeyError:
                        self.names_index[name_string] = set()
                    self.names_index[name_string].add(pid)
            logger.info(
                f"Generated names index with {len(self.names_index):,} name strings from Pleiades data"
            )

    def _initialize_spatial_index(self):
        """Initialize the spatial index."""
        logger = logging.getLogger(f"{__name__}:Pleiades._initialize_spatial_index")
        hulls = list()
        i = 0
        for pid in self.fs.index.keys():  # type: ignore
            place = self.get(pid)
            if place.footprint:  # type: ignore
                self._spatial_index_2_pid[i] = pid
                i += 1
                hulls.append(place.footprint)  # type: ignore
        self._spatial_index = STRtree(hulls)
        logger.info(
            f"Generated spatial index with {len(self._spatial_index_2_pid):,} place footprints from Pleiades data"
        )

    def _load_names_index(self, names_index_path: Path):
        """Load the names index from the specified path."""
        with open(names_index_path, "r", encoding="utf-8") as f:
            raw_index = json.load(f)
        del f
        for name_string, pid in raw_index:
            try:
                self.names_index[name_string]
            except KeyError:
                self.names_index[name_string] = set()
            self.names_index[name_string].add(pid)
        logger = logging.getLogger(f"{__name__}:Pleiades._load_names_index")
        logger.info(
            f"Loaded {len(self.names_index):,} name strings from {names_index_path}"
        )

    def __len__(self):
        """Return the number of places in the Pleiades data set"""
        return len(self.fs)

    @functools.lru_cache(maxsize=None)
    def get_place_types(self, pid: str) -> set:
        """Return the set of place types for the specified pid."""
        logger = logging.getLogger(f"{__name__}:Pleiades.get_place_types")
        place = self.get(pid)
        if not self._place_type_vocabulary:
            vocab_path = (self.root_path / "../gis/place_types.csv").resolve()
            with open(vocab_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self._place_type_vocabulary[
                        f"https://pleiades.stoa.org/vocabularies/place-types/{row['key']}"
                    ] = {
                        t.replace("(deprecated)", "").strip()
                        for t in row["term"].split(",")
                        if t.strip()
                    }
            del f
            for k, v in self._place_type_vocabulary.items():
                alternates = set()
                for t in v:
                    if "(" in t:
                        alt_t = t.split("(", 1)[0].strip()
                        if alt_t and alt_t != t:
                            alternates.add(alt_t)
                v.update(alternates)
            logger.info(
                f"Loaded {len(self._place_type_vocabulary):,} place type keys from {vocab_path}"
            )
        if place:
            uris = place.place_type_uris
            terms = set()
            for uri in uris:
                try:
                    these_terms = self._place_type_vocabulary.get(uri, set())
                except Exception as err:
                    err.add_note(
                        f"Failed lookup of place type vocabulary for pid '{pid}' on uri '{pformat(uri)}' from with place_type_uris: {pformat(place.place_type_uris, indent=4)}"
                    )
                    raise err
                else:
                    try:
                        terms.update(these_terms)
                    except TypeError as err:
                        err.add_note(
                            f"Failed addition of place type vocabulary term '{pformat(these_terms)}' for pid '{pid}' on uri '{pformat(uri)}' from with place_type_uris: {pformat(place.place_type_uris, indent=4)}"
                        )
                        raise err
            return terms
        else:
            return set()

    def spatial_query(self, geometry):
        """Return Pleiades places within which this geometry intersects."""
        if self._spatial_index is None:
            raise RuntimeError("Spatial index not initialized")
        match_indexes = self._spatial_index.query(geometry)
        matched_pids = {self._spatial_index_2_pid[i] for i in match_indexes}
        return matched_pids

    def spatial_nearest(self, geometry, max_distance=0.18):
        """Return the nearest Pleiades places to this geometry (less than roughly 20km)."""
        if self._spatial_index is None:
            raise RuntimeError("Spatial index not initialized")
        nearest_geometries = self._spatial_index.query_nearest(geometry, max_distance)
        matched_pids = {self._spatial_index_2_pid[i] for i in nearest_geometries}
        return matched_pids
