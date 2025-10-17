#
# This file is part of pleiades_accession
# by Tom Elliott for the Institute for the Study of the Ancient World
# (c) Copyright 2025 by New York University
# Licensed under the AGPL-3.0; see LICENSE.txt file.
#

"""
Make new LPF from scratch, using provided resources
"""
from alphabet_detector import AlphabetDetector
from datetime import timedelta
import json
import logging
from pathlib import Path
from pprint import pformat
import re
from romanize import romanize
from pleiades_accession.text import normalize_text
from shapely import from_geojson, to_geojson
from shapely.testing import assert_geometries_equal
from slugify import slugify
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
ALPHABET_DETECTOR = AlphabetDetector()


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
        else:
            d["sourceLabels"] = sorted(
                d["sourceLabels"], key=lambda x: x["label"]
            )  # type: ignore
        return d


class LPFGeometry:
    """
    Class representing a GeoJSON geometry
    """

    def __init__(
        self,
        geom_type: str = "",
        coordinates: list = [],
        certainty: str = "certain",
        citations: list = [],
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


class LPFCitation:
    """
    Class representing a citation after Linked Places Format (LPF)
    """

    def __init__(self, label: str = "", year: int = None, identifier: str = "", **kwargs):  # type: ignore
        """
        Initialize LPFCitation class
        """
        try:
            self.label = normalize_text(label)
        except TypeError as err:
            err.add_note(
                f"while normalizing citation label of type {type(label)}: {pformat(label)}"
            )
            raise err
        self.year = year  # citation year
        self.identifier = identifier  # citation identifier (i.e. URL)


class LPFName:
    """
    Class representing a place name after Linked Places Format (LPF) with additional Pleiades requirements
    """

    def __init__(
        self,
        toponym: str,
        romanizations: list = [],
        lang: str = "und",
        citations: list = [],
        when: dict = dict(),
    ):
        """
        Initialize LPFName class
        """
        self.toponym = normalize_text(toponym)  # place name
        self.romanizations = {
            normalize_text(r) for r in romanizations
        }  # romanized forms
        self.lang = lang  # language tag
        self.romanizations.add(slugify(toponym, separator=" ", lowercase=False))
        if lang == "de":
            # German U with umlaut special case
            self.romanizations.add(
                slugify(
                    toponym,
                    separator=" ",
                    lowercase=False,
                    replacements=[["Ü", "UE"], ["ü", "ue"]],
                )
            )
        if ALPHABET_DETECTOR.only_alphabet_chars(toponym, "LATIN"):
            self.romanizations.add(toponym)
        else:
            alphabets = ALPHABET_DETECTOR.detect_alphabet(toponym)
            if alphabets == {"GREEK"} and lang in {"el", "grc", "und"}:
                self.romanizations.add(romanize(toponym))
                if lang == "und":
                    self.lang = "el"
            elif len(alphabets) > 1:
                pass  # skip mixed-alphabet toponyms; slugify is best we can do
            else:
                raise NotImplementedError(
                    f"Romanization for alphabet {alphabets} not implemented yet"
                )
        if citations:
            for c in citations:
                if "@id" in c:
                    c["identifier"] = c["@id"]
            self.citations = [LPFCitation(**c) for c in citations]
        if when:
            raise NotImplementedError("LPFName 'when' not implemented yet for names")

    def to_dict(self) -> dict:
        """
        Convert LPFName to dictionary, ready for JSON serialization in LPF format
        """
        d = {
            "toponym": self.toponym,
            "lang": self.lang,
        }
        if self.romanizations:
            d["romanizations"] = sorted(list(self.romanizations))  # type: ignore
        if hasattr(self, "citations"):
            d["citations"] = [  # type: ignore
                {
                    "label": c.label,
                    **({"year": c.year} if c.year else {}),
                    **({"@id": c.identifier} if c.identifier else {}),
                }
                for c in self.citations
            ]
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
        self._names = list()  # LPFName instances

    #
    # country codes
    #
    @property
    def country_codes(self) -> list:
        """
        Get country codes as list
        """
        return list(self._country_codes)

    def add_country_code(self, country_code: str | dict):
        """
        Add a country code
        """
        if isinstance(country_code, dict):
            country_code = country_code.get("ccode", "")
        elif isinstance(country_code, str):
            country_code = country_code
        self._country_codes.add(country_code.upper())  # type: ignore

    #
    # feature classes
    #
    @property
    def feature_classes(self) -> list:
        """
        Get feature classes as list
        """
        return list(self._feature_classes)

    def add_feature_class(self, feature_class: str | dict):
        """
        Add a feature class
        """
        if isinstance(feature_class, dict):
            feature_class = feature_class.get("code", "")
        elif isinstance(feature_class, str):
            feature_class = feature_class
        else:
            raise TypeError(
                f"Feature class must be str or dict. Got {type(feature_class)}"
            )
        if feature_class:
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
        self,
        geom_type: str,
        coordinates: list,
        certainty: str = "certain",
        citations: list = [],
    ):
        """
        Add a geometry
        """
        if certainty not in VALID_CERTAINTY_VALUES:
            raise ValueError(f"Unrecognized certainty value: {certainty}")
        new_geom = LPFGeometry(
            geom_type=geom_type,
            coordinates=coordinates,
            certainty=certainty,
            citations=citations,
        )
        if self._geometries:
            # check for duplicates
            new_shape = new_geom.shape
            for existing_geom in self._geometries:
                if assert_geometries_equal(
                    existing_geom.shape, new_shape, normalize=True
                ):
                    # geometries are equal
                    if not existing_geom.citations and citations:
                        existing_geom.citations = citations
                    return
        self._geometries.append(new_geom)

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
    # names
    #

    @property
    def names(self) -> list:
        """
        Get names as list
        """
        raise NotImplementedError("LPFPlace 'names' not implemented yet")

    @property
    def name_strings(self) -> list:
        nstrings = set()
        for name in self._names:
            nstrings.add(name.toponym)
            nstrings.update(name.romanizations)
        return list(nstrings)

    def add_name(
        self, toponym: str, lang: str = "und", citations: list = [], when: dict = dict()
    ):
        """
        Add a name
        """
        if normalize_text(toponym) not in self.name_strings:
            self._names.append(
                LPFName(toponym=toponym, lang=lang, citations=citations, when=when)
            )

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
            "names": [n.to_dict() for n in self._names],
        }
        geoms = self.geometries
        logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        logger.debug(pformat(geoms, indent=2))
        if len(geoms) == 1:
            d["geometry"] = geoms[0]
        else:
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
        if isinstance(source_data, list):
            raise TypeError("WHG Place API data should be a dict, not a list")
        for k, v in source_data.items():

            if not v:
                continue

            # ignore
            if k in {"extent", "minmax"}:
                continue
            # id
            if k == "id":
                place.add_link(
                    identifier=f"https://whgazetteer.org/api/place/{v}/",
                    link_type="citesAsDataSource",
                )
                place.add_link(
                    identifier=f"https://whgazetteer.org/places/{v}/detail",
                    link_type="closeMatch",
                )

            # datasets
            elif k == "datasets":
                for dataset in v:
                    place.add_link(
                        identifier=f"https://whgazetteer.org/datasets/{dataset['id']}/places",
                        link_type="member",
                        label=dataset.get("title", ""),
                    )

            # title
            elif k == "title":
                place.title = v
                place.add_name(toponym=place.title)

            # names
            elif k == "names":
                for name in v:
                    place.add_name(**name)

            # types
            elif k == "types":
                for ptype in v:
                    place.add_type(**ptype)

            # fclasses
            elif k == "fclasses":
                for fc in v:
                    place.add_feature_class(fc)

            # geoms
            elif k == "geoms":
                for geom in v:
                    dataset_id = geom.get("ds", "")
                    dataset_uri = ""
                    if dataset_id:
                        dataset_uri = (
                            f"https://whgazetteer.org/datasets/{dataset_id}/places"
                        )
                    citations = []
                    if dataset_uri:
                        citations.append(
                            LPFCitation(
                                identifier=dataset_uri,
                            )
                        )
                    if (
                        geom.get("type") == "MultiPoint"  # type: ignore
                        and len(geom["coordinates"]) == 1  # type: ignore
                    ):
                        place.add_geometry(
                            geom_type="Point",
                            coordinates=geom["coordinates"][0],  # type: ignore
                            certainty=geom.get("certainty", "certain"),  # type: ignore
                            citations=citations,
                        )
                    else:
                        place.add_geometry(
                            geom_type=geom["type"],  # type: ignore
                            coordinates=geom["coordinates"],  # type: ignore
                            certainty=geom.get("certainty", "certain"),  # type: ignore
                            citations=citations,
                        )

            # countries
            elif k == "countries":
                for cc in v:
                    place.add_country_code(cc)

            else:
                raise NotImplementedError(
                    f"WHG Place API key '{k}' not implemented yet"
                )

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
