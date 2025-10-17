#
# This file is part of pleiades_accession
# by Tom Elliott for the Institute for the Study of the Ancient World
# (c) Copyright 2025 by New York University
# Licensed under the AGPL-3.0; see LICENSE.txt file.
#

"""
Make new LPF from scratch, using provided resources
"""
from datetime import timedelta
import json
import logging
from pathlib import Path
from pprint import pformat
import re
from pleiades_accession.text import normalize_text
from shapely import from_geojson, to_geojson
from urllib.parse import urlparse
from uuid import uuid4
from validators import url as validate_url
from webiquette.webi import Webi

web_interfaces = dict()
HEADERS = {
    "User-Agent": "pleiades_accession/0.1 (+https://pleiades.stoa.org)",
    "From": "pleiades.admin@nyu.edu",
}
EXPIRE_AFTER = timedelta(days=1)
origin_url_rxx = [
    (r"^https://whgazetteer\.org/api/db/\?id=(\d)+$", "whg_db_api"),
    (r"^https://whgazetteer.org/api/place/(\d)+/$", "whg_place_api"),
]
VALID_LINK_TYPES = {
    "closeMatch",
    "primaryTopicOf",
    "subjectOf",
    "seeAlso",
    "citesAsDataSource",
    "member",
}
VALID_CERTAINTY_VALUES = {"certain", "less-certain", "uncertain"}


class LPFSourceLabel:
    """
    Class representing a source label after Linked Places Format (LPF)
    """

    def __init__(self, label: str, lang: str = ""):
        """
        Initialize LPFSourceLabel class
        """
        self.label = label  # preferred label
        self.lang = lang  # language tag


class LPFType:
    """
    Class representing a place type after Linked Places Format (LPF)
    """

    def __init__(
        self,
        identifier: str,
        label: str = "",
        sourceLabels: list = [],
        sourceLabel: str = "",
        when: dict = dict(),
    ):
        """
        Initialize LPFType class
        """
        self.identifier = identifier  # urn or url
        self.label = label  # preferred label (str)
        self.sourceLabels = list()  # list of LPFSourceLabel
        for sl in sourceLabels:
            if isinstance(sl, LPFSourceLabel):
                self.sourceLabels.append(sl)
            elif isinstance(sl, dict):
                self.sourceLabels.append(LPFSourceLabel(**sl))
            elif isinstance(sl, str):
                self.sourceLabels.append(LPFSourceLabel(label=sl))
        if sourceLabel:
            self.sourceLabels.append(LPFSourceLabel(label=sourceLabel))
        if when:
            raise NotImplementedError("LPFType 'when' not implemented yet")

    def to_dict(self) -> dict:
        """
        Convert LPFType to dictionary, ready for JSON serialization in LPF format
        """
        d = {
            "label": self.label,
            "sourceLabels": [],
        }
        for sl in self.sourceLabels:
            if sl.label == self.label:
                continue
            if sl.lang:
                d["sourceLabels"].append({"label": sl.label, "lang": sl.lang})
            else:
                d["sourceLabels"].append({"label": sl.label})
        if not d["sourceLabels"]:
            del d["sourceLabels"]
        return d


class LPFGeometry:
    """
    Class representing a GeoJSON geometry
    """

    def __init__(
        self, geom_type: str = "", coordinates: list = [], certainty: str = "certain"
    ):
        """
        Initialize LPFGeometry class
        """
        self.type = geom_type  # GeoJSON geometry type
        self.coordinates = coordinates  # GeoJSON coordinates
        self.when = None  # when? (not implemented yet)
        self.citations = []  # citations? (not implemented yet)
        self.certainty = certainty
        self.shape = from_geojson(
            json.dumps({"type": geom_type, "coordinates": coordinates})
        )
        logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        logger.debug(f"Created LPFGeometry: {self.shape.wkt}")

    def to_dict(self) -> dict:
        """
        Convert LPFGeometry to dictionary, ready for JSON serialization in LPF format
        """
        d = json.loads(to_geojson(self.shape))
        d["certainty"] = self.certainty
        return d


class LPFPlace:
    """
    Class representing a place after Linked Places Format (LPF)
    """

    def __init__(self):
        """
        Initialize LPFPlace class
        """
        self.id = str(uuid4())
        self._types = (
            dict()
        )  # keys are urns (preferably urls), values are {label, sourceLabels*, when?}
        self._feature_classes = set()  # geonames feature classes
        self._links = dict()  # keys are urls, values are strings
        self._title = ""  # title of record
        self._country_codes = set()
        self._geometries = list()  # GeoJSON geometry

    #
    # country codes
    #
    @property
    def country_codes(self) -> list:
        """
        Get country codes as list
        """
        return list(self._country_codes)

    def add_country_code(self, country_code: str):
        """
        Add a country code
        """
        self._country_codes.add(country_code.upper())

    #
    # feature classes
    #
    @property
    def feature_classes(self) -> list:
        """
        Get feature classes as list
        """
        return list(self._feature_classes)

    def add_feature_class(self, feature_class: str):
        """
        Add a feature class
        """
        self._feature_classes.add(feature_class)

    #
    # geometries
    #
    @property
    def geometries(self) -> list:
        """
        Get geometries as list
        """
        return [g.to_dict() for g in self._geometries]

    def add_geometry(
        self, geom_type: str, coordinates: list, certainty: str = "certain"
    ):
        """
        Add a geometry
        """
        if certainty not in VALID_CERTAINTY_VALUES:
            raise ValueError(f"Unrecognized certainty value: {certainty}")
        self._geometries.append(
            LPFGeometry(
                geom_type=geom_type, coordinates=coordinates, certainty=certainty
            )
        )

    #
    # place types
    #
    @property
    def types(self) -> list:
        """
        Get types as list
        """
        return [{"identifier": k, **v.to_dict()} for k, v in self._types.items()]

    @property
    def type_identifiers(self) -> list:
        """
        Get type identifiers as list
        """
        return list(self._types.keys())

    @property
    def type_labels(self) -> list:
        """
        Get type labels as list
        """
        current_labels = set()
        for v in self._types.values():
            current_labels.add(v["label"])
            for sl in v["sourceLabels"]:
                current_labels.add(sl["label"])
        return list(current_labels)

    def add_type(
        self,
        identifier: str,
        label: str,
        sourceLabels: list = [],
        sourceLabel: str = "",
        when: dict = dict(),
        gn_class: str = "",
    ):
        """
        Add a type
        """
        if identifier not in self._types:
            self._types[identifier] = LPFType(
                identifier=identifier,
                label=label,
                sourceLabels=sourceLabels,
                sourceLabel=sourceLabel,
                when=when,
            )
        else:
            raise NotImplementedError("Updating existing LPFType not implemented yet")
        if gn_class:
            self.add_feature_class(gn_class)

    #
    # links
    #

    @property
    def links(self) -> list:
        """
        Get links as list
        """
        return [
            {"identifier": k, "type": v["type"], "label": v["label"]}
            for k, v in self._links.items()
        ]

    def add_link(self, identifier: str, link_type: str = "closeMatch", label: str = ""):
        """
        Add a link
        """
        if link_type not in VALID_LINK_TYPES:
            raise ValueError(f"Unrecognized link type: {link_type}")
        if identifier not in self._links:
            self._links[identifier] = {"type": link_type, "label": label}

    #
    # title
    #
    @property
    def title(self) -> str:
        """
        Get title (preferred label)
        """
        return self._title

    @title.setter
    def title(self, value: str):
        """
        Set title (preferred label)
        """
        value = normalize_text(value)
        if not value:
            raise ValueError("Title cannot be empty")
        self._title = value

    def to_dict(self) -> dict:
        """
        Convert LPFPlace to dictionary, ready for JSON serialization in LPF format
        """
        d = {
            "@id": self.id,
            "type": "Feature",
            "properties": {
                "title": self.title,
                "ccodes": self.country_codes,
                "fclasses": self.feature_classes,
            },
            "types": self.types,
            "links": self.links,
        }
        geoms = self.geometries
        logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        logger.debug(pformat(geoms, indent=2))
        if len(geoms) == 1:
            logger.debug("foo")
            d["geometry"] = geoms[0]
        else:
            logger.debug("bar")
            d["geometry"] = {
                "type": "GeometryCollection",
                "geometries": [g for g in geoms],
            }
        return d


class Maker:
    """
    Class to make new LPF from scratch, using provided resources
    """

    def __init__(self):
        """
        Initialize Maker class
        """
        self.places = dict()

    def make(self, sources: list = []) -> LPFPlace:
        """
        Make new LPF
        """
        place = LPFPlace()
        self.places[place.id] = place
        for source in sources:
            source_identity = self._identify_source(str(source))
            if isinstance(source, str):
                if validate_url(source):
                    source_data = self._ingest_from_url(source)
                else:
                    source_data = self._ingest_from_file(source)
            elif isinstance(source, Path):
                source_data = self._ingest_from_file(str(source))
            else:
                raise TypeError("Source must be str or Path. Got {type(source)}")
            self._augment_place(place, source_data, source_identity)
        return place

    def _augment_place(
        self, place: LPFPlace, source_data: dict | list, source_identity: str
    ):
        """
        Augment place with source data
        """
        return getattr(self, f"_augment_from_{source_identity}")(place, source_data)

    def _augment_from_whg_db_api(self, place: LPFPlace, source_data: dict | list):
        """
        Augment place from WHG DB API data
        """
        if isinstance(source_data, list):
            raise TypeError("WHG DB API data should be a dict, not a list")
        features = source_data.get("features", [])
        for feature in features:
            for k, v in feature.items():

                if not v:
                    continue

                # types
                if k == "types":
                    for ptype in v:
                        place.add_type(**ptype)

                # links
                elif k == "links":
                    raise NotImplementedError("WHG DB API 'links' not implemented yet")

                # related
                elif k == "related":
                    raise NotImplementedError(
                        "WHG DB API 'related' not implemented yet"
                    )

                # whens
                elif k == "whens":
                    raise NotImplementedError("WHG DB API 'whens' not implemented yet")

                # descriptions
                elif k == "descriptions":
                    raise NotImplementedError(
                        "WHG DB API 'descriptions' not implemented yet"
                    )

                # depictions
                elif k == "depictions":
                    raise NotImplementedError(
                        "WHG DB API 'depictions' not implemented yet"
                    )

                # type = Feature
                elif k == "type":
                    if v != "Feature":
                        raise ValueError(
                            f"WHG DB API feature unexpected type value {feature.get('type')}, expected Feature"
                        )

                # uri
                elif k == "uri":
                    place.add_link(v, link_type="citesAsDataSource")

                # properties
                elif k == "properties":
                    for kk, vv in v.items():  # type: ignore
                        if kk in [
                            "place_id",
                            "src_id",
                            "dataset_label",
                            "dataset_title",
                            "minmax",
                        ]:
                            continue
                        elif kk == "title":
                            place.title = normalize_text(vv)
                        elif kk == "dataset_uri":
                            place.add_link(
                                identifier=vv,
                                link_type="member",
                                label=feature["properties"].get("dataset_title", ""),
                            )
                        elif kk == "ccodes":
                            for cc in vv:
                                place.add_country_code(cc)
                        elif kk == "fclasses":
                            for fc in vv:
                                place.add_feature_class(fc)
                        elif kk == "timespans":
                            if vv:
                                raise NotImplementedError(
                                    "WHG DB API 'timespans' not implemented yet (value: {vv})"
                                )
                        else:
                            raise NotImplementedError(
                                f"WHG DB API property '{k}' not implemented yet"
                            )

                # geometry
                elif k == "geometry":
                    geom = v
                    if geom:
                        if (
                            geom.get("type") == "MultiPoint"  # type: ignore
                            and len(geom["coordinates"]) == 1  # type: ignore
                        ):
                            place.add_geometry(
                                geom_type="Point",
                                coordinates=geom["coordinates"][0],  # type: ignore
                                certainty=geom.get("certainty", "certain"),  # type: ignore
                            )
                        else:
                            place.add_geometry(
                                geom_type=geom["type"],  # type: ignore
                                coordinates=geom["coordinates"],  # type: ignore
                                certainty=geom.get("certainty", "certain"),  # type: ignore
                            )

                else:
                    raise NotImplementedError(
                        f"WHG DB API feature key '{k}' not implemented yet"
                    )

    def _augment_from_whg_place_api(self, place: LPFPlace, source_data: dict | list):
        """
        Augment place from WHG Place API data
        """
        raise NotImplementedError("WHG Place API not implemented yet")

    def _identify_source(self, source: str) -> str:
        """
        Identify source type
        """
        if validate_url(source):
            for rxx, identity in origin_url_rxx:
                if re.match(rxx, source):
                    return identity
            raise ValueError("Unrecognized URL source: {source}")
        else:
            raise NotImplementedError("File source identification not implemented yet")

    def _ingest_from_url(self, url: str) -> dict | list:
        """
        Ingest data from URL
        """
        url_parts = urlparse(url)
        try:
            interface = web_interfaces[url_parts.netloc]
        except KeyError:
            interface = Webi(
                url_parts.netloc,
                headers=HEADERS,
                respect_robots_txt=False,
                cache_control=False,
                expire_after=EXPIRE_AFTER,
            )
            web_interfaces[url_parts.netloc] = interface
        r = interface.get(url)
        return r.json()

    def _ingest_from_file(self, filepath: str | Path) -> dict | list:
        """
        Ingest data from file
        """
        if isinstance(filepath, str):
            filepath = Path(filepath)
        with filepath.open("r", encoding="utf-8") as f:
            r = json.load(f)
        del f
        return r
