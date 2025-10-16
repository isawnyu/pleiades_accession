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
from pathlib import Path
import re
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
        }
        for sl in self.sourceLabels:
            if sl.label == self.label:
                continue
            if sl.lang:
                d["sourceLabels"].append({"label": sl.label, "lang": sl.lang})
            else:
                d["sourceLabels"].append({"label": sl.label})
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

    def to_dict(self) -> dict:
        """
        Convert LPFPlace to dictionary, ready for JSON serialization in LPF format
        """
        d = {
            "@id": self.id,
            "type": "Feature",
            "properties": {
                "fclasses": self.feature_classes,
            },
            "types": self.types,
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
            # types
            for ptype in feature.get("types", []):
                place.add_type(**ptype)

    def _augment_from_whg_place_api(self, place: LPFPlace, source_data: dict | list):
        """
        Augment place from WHG Place API data
        """
        pass

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
