#
# This file is part of pleiades_accession
# by Tom Elliott for the Institute for the Study of the Ancient World
# (c) Copyright 2025 by New York University
# Licensed under the AGPL-3.0; see LICENSE.txt file.
#

"""
Make new LPF from scratch, using provided resources
"""
from bs4 import BeautifulSoup
from datetime import timedelta
from functools import lru_cache
import json
import logging
from pathlib import Path
from pprint import pformat
from pleiades_accession.text import normalize_text
from pleiades_writing_systems.romanization import Romanizer, ScriptDetector
import re
from shapely import from_geojson, to_geojson
from shapely.testing import assert_geometries_equal
from slugify import slugify
from urllib.parse import urlparse
from uuid import uuid4
from validators import url as validate_url
from webiquette.webi import Webi

web_interfaces = dict()
HEADERS = {
    "User-Agent": "pleiades_accession/0.1 (https://pleiades.stoa.org; pleiades.admin@nyu.edu)",
    "From": "pleiades.admin@nyu.edu",
}
EXPIRE_AFTER = timedelta(days=1)
origin_url_rxx = [
    (r"^https://whgazetteer\.org/api/db/\?id=(\d)+$", "whg_db_api"),
    (r"^https://whgazetteer.org/api/place/(\d)+/$", "whg_place_api"),
    (r"^https://www.wikidata.org/wiki/(Q\d+)/?$", "wikidata"),
]
VALID_LINK_TYPES = {
    "closeMatch",
    "primaryTopicOf",
    "subjectOf",
    "seeAlso",
    "citesAsDataSource",
    "member",
}
VALID_MILESTONE_TYPES = {"in", "earliest", "latest"}
VALID_CERTAINTY_VALUES = {"certain", "less-certain", "uncertain"}
RX_ISO8601_DATE = re.compile(r"^\d{4}(-\d{2}|-\d{2}-\d{2})?$")
RX_WIKIDATA_TIME = re.compile(r"^(?P<year>-?\d{4})-(?P<month>\d{2})-(?P<day>\d{2})T.+$")

SCRIPT_DETECTOR = ScriptDetector()

WIKIDATA_LABEL_LANGUAGES = [
    "en",
    "de",
    "es",
    "fr",
    "it",
    "pt",
]


class LPFMilestone:
    """
    Class representing an ISO 8601 temporal milestone used in LPFTimespan after Linked Places Format (LPF)
    """

    def __init__(self, milestone_type: str = "in", iso_date: str = ""):
        """
        Initialize LPFMilestone class
        """
        if milestone_type not in VALID_MILESTONE_TYPES:
            raise ValueError(f"Unrecognized milestone type: {milestone_type}")
        if not RX_ISO8601_DATE.match(iso_date):
            raise ValueError(f"Invalid ISO 8601 date: {iso_date}")
        self.milestone_type = milestone_type
        self.iso_date = iso_date

    def to_dict(self) -> dict:
        """
        Convert LPFMilestone to dictionary, ready for JSON serialization in LPF format
        """
        return {self.milestone_type: self.iso_date}


class LPFTimespan:
    """
    Class representing a timespan after Linked Places Format (LPF)
    """

    def __init__(
        self, start: list[LPFMilestone] | dict, end: list[LPFMilestone] | dict = []
    ):
        """
        Initialize LPFTimespan class
        """
        logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        logger.debug(
            f"Initializing LPFTimespan with start={pformat(start)} end={pformat(end)}"
        )
        self.start = []
        if isinstance(start, list):
            for ms in start:
                if not isinstance(ms, LPFMilestone):
                    raise TypeError(
                        "Start list items must be LPFMilestone instances. Got {type(ms)}: {pformat(ms)}"
                    )
                self.start.append(ms)
        elif isinstance(start, dict):
            for k, v in start.items():
                self.start.append(LPFMilestone(milestone_type=k, iso_date=v))
        else:
            raise TypeError(
                "Start must be list of LPFMilestone instances or dict. Got {type(start)}: {pformat(start)}"
            )

        self.end = []
        if end:
            if isinstance(end, list):
                for ms in end:
                    if not isinstance(ms, LPFMilestone):
                        raise TypeError(
                            "End list items must be LPFMilestone instances. Got {type(ms)}: {pformat(ms)}"
                        )
                    self.end.append(ms)
            elif isinstance(end, dict):
                for k, v in end.items():
                    self.end.append(LPFMilestone(milestone_type=k, iso_date=v))
            else:
                raise TypeError(
                    "End must be list of LPFMilestone instances or dict. Got {type(end)}: {pformat(end)}"
                )

    def to_dict(self) -> dict:
        """
        Convert LPFTimespan to dictionary, ready for JSON serialization in LPF format
        """
        d = {
            "start": [s.to_dict() for s in self.start],
            "end": [],
        }
        if self.end:
            d["end"] = [e.to_dict() for e in self.end]
        else:
            del d["end"]
        return d


class LPFPeriod:
    """
    Class representing a 'period' after Linked Places Format (LPF)
    """

    def __init__(self, name: str = "", uri: str = ""):
        """
        Initialize LPFPeriod class
        """
        self.name = name  # preferred label
        self.uri = uri  # urn or url

    def to_dict(self) -> dict:
        """
        Convert LPFPeriod to dictionary, ready for JSON serialization in LPF format
        """
        d = {"name": self.name, "uri": self.uri}
        return d


class LPFWhen:
    """
    Class representing a 'when' after Linked Places Format (LPF)
    """

    def __init__(self, timespans: list, periods: list = [], certainty: str = "certain", label: str = "", duration: str = ""):  # type: ignore
        """
        Initialize LPFWhen class
        """
        self.timespans = []
        for ts in timespans:
            if isinstance(ts, LPFTimespan):
                self.timespans.append(ts)
            elif isinstance(ts, dict):
                logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
                logger.debug(f"Initializing LPFTimespan from dict: {pformat(ts)}")
                self.timespans.append(LPFTimespan(**ts))

        self.periods = []
        if periods:
            raise NotImplementedError("LPFWhen 'periods' not implemented yet")
        self.certainty = certainty
        self.label = label
        self.duration = duration

    def to_dict(self) -> dict:
        """
        Convert LPFWhen to dictionary, ready for JSON serialization in LPF format
        """
        d = {
            "timespans": [ts.to_dict() for ts in self.timespans],
        }
        if self.periods:
            d["periods"] = self.periods
        if self.certainty:
            d["certainty"] = self.certainty  # type: ignore
        if self.label:
            d["label"] = self.label  # type: ignore
        if self.duration:
            d["duration"] = self.duration  # type: ignore
        return d


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
        precision: float = 0.0,
    ):
        """
        Initialize LPFGeometry class
        """
        self.type = geom_type  # GeoJSON geometry type
        self.coordinates = coordinates  # GeoJSON coordinates
        self.when = None  # when? (not implemented yet)
        self.citations = citations  # citations? (not implemented yet)
        self.certainty = certainty
        self.precision = precision
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
        d["precision"] = self.precision
        d["citations"] = [c.to_dict() for c in self.citations]
        return d


class LPFCitation:
    """
    Class representing a citation after Linked Places Format (LPF)
    """

    def __init__(self, label: str = "", year: int = None, identifier: str = "", ctype: str = "citesAsDataSource", **kwargs):  # type: ignore
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
        self.ctype = ctype

    def to_dict(self) -> dict:
        """
        Convert LPFCitation to dictionary, ready for JSON serialization in LPF format
        """
        d = {
            "label": self.label,
        }
        if self.year:
            d["year"] = self.year  # type: ignore
        if self.identifier:
            d["@id"] = self.identifier  # type: ignore
        if self.ctype:
            d["type"] = self.ctype  # type: ignore
        return d


class LPFLink:
    """
    Class representing a link after Linked Places Format (LPF)
    """

    def __init__(
        self,
        identifier: str,
        link_type: str = "closeMatch",
        label: str = "",
        source: str = "",
        authority: str = "",
        authority_alias: str = "",
    ):
        """
        Initialize LPFLink class
        """
        self.identifier = identifier  # link identifier (i.e. URL)
        if link_type not in VALID_LINK_TYPES:
            raise ValueError(f"Unrecognized link type: {link_type}")
        self.link_type = link_type
        self.label = normalize_text(label)  # link label
        self.source = source  # link source
        if authority and not authority_alias:
            authority_alias = slugify(authority)
        self.authority_alias = authority_alias  # link authority alias
        self.authority = authority  # link authority

    def to_dict(self) -> dict:
        """
        Convert LPFLink to dictionary, ready for JSON serialization in LPF format
        """
        d = {
            "identifier": self.identifier,
            "type": self.link_type,
        }
        if self.label:
            d["label"] = self.label  # type: ignore
        if self.source:
            d["source"] = self.source  # type: ignore
        if self.authority:
            d["authority"] = self.authority  # type: ignore
        return d


class LPFDescription:
    """
    Class representing a description after Linked Places Format (LPF)
    """

    def __init__(
        self, value: str, lang: str = "und", citations: list[LPFCitation | dict] = []
    ):
        """
        Initialize LPFDescription class
        """
        self.value = normalize_text(value)  # description text
        self.lang = lang  # language tag
        self.citations = []
        for c in citations:
            if isinstance(c, dict):
                self.citations.append(LPFCitation(**c))
            elif isinstance(c, LPFCitation):
                self.citations.append(c)

    def to_dict(self) -> dict:
        """
        Convert LPFDescription to dictionary, ready for JSON serialization in LPF format
        """
        d = {
            "value": self.value,
            "lang": self.lang,
        }
        if self.citations:
            d["citations"] = [c.to_dict() for c in self.citations]  # type: ignore
        return d


class LPFDepiction:
    """
    Class representing a depiction after Linked Places Format (LPF)
    """

    def __init__(self, identifier: str, title: str = "", license: str = ""):
        """
        Initialize LPFDepiction class
        """
        self.identifier = identifier  # depiction identifier (i.e. URL)
        self.title = normalize_text(title)  # depiction label
        self.license = license

    def to_dict(self) -> dict:
        """
        Convert LPFDepiction to dictionary, ready for JSON serialization in LPF format
        """
        d = {
            "@id": self.identifier,
            "title": self.title,
        }
        if self.license:
            d["license"] = self.license  # type: ignore
        return d


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
        self.citations = []
        self.toponym = normalize_text(toponym)  # place name
        romanizations_d = {
            normalize_text(r): 1 for r in romanizations
        }  # romanized forms, preserve order
        romanization_engines = [
            "yuconv",
            "romanize-schizas",
            "python-slugify",
            "iuliia",
        ]
        for romanization in Romanizer(use_engines=romanization_engines).romanize(
            self.toponym, lang_tags=lang
        ):
            rs = romanization.romanized
            try:
                romanizations_d[rs]
            except KeyError:
                romanizations_d[rs] = 1
            else:
                romanizations_d[rs] += 1

        self.romanizations = sorted(
            romanizations_d, key=romanizations_d.get, reverse=True
        )  # type: ignore
        script = SCRIPT_DETECTOR.detect_scripts(self.toponym)
        if script == ["Latn"]:
            # if the toponym is already in Latin script, ensure it's included in romanizations
            if self.toponym in self.romanizations:
                del self.romanizations[self.romanizations.index(self.toponym)]
            self.romanizations.insert(0, self.toponym)  # type: ignore

        self.lang = lang  # language tag
        if citations:
            for c in citations:
                if isinstance(c, dict):
                    if "@id" in c:
                        c["identifier"] = c["@id"]
                    self.citations.append(LPFCitation(**c))
                elif isinstance(c, LPFCitation):
                    self.citations.append(c)
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
            d["romanizations"] = self.romanizations  # type: ignore
        if hasattr(self, "citations"):
            d["citations"] = [c.to_dict() for c in self.citations]  # type: ignore
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
        self._links = list()  # LPFLink instances
        self._title = ""  # title of record
        self._country_codes = set()
        self._geometries = list()  # GeoJSON geometry
        self._names = list()  # LPFName instances
        self._timespans = list()  # LPFTimespan instances
        self._periods = list()  # LPFPeriod instancess
        self._depictions = list()  # LPFDepiction instances
        self._descriptions = list()  # LPFDescription instances

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
    # depictions
    #
    @property
    def depictions(self) -> list:
        """
        Get depictions as list
        """
        return [l.to_dict() for l in self._depictions]

    def add_depiction(self, identifier: str, title: str = "", license: str = ""):
        """
        Add a depiction
        """
        self._depictions.append(
            LPFDepiction(identifier=identifier, title=title, license=license)
        )

    #
    # descriptions
    #
    @property
    def descriptions(self) -> list:
        """
        Get descriptions as list
        """
        return [d.to_dict() for d in self._descriptions]

    def add_description(self, value: str, lang: str = "und", citations: list = []):
        """
        Add a description
        """
        self._descriptions.append(
            LPFDescription(value=value, lang=lang, citations=citations)
        )

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
        precision: float = 0.0,
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
            precision=precision,
        )
        if self._geometries:
            # check for duplicates
            new_shape = new_geom.shape
            for existing_geom in self._geometries:
                try:
                    assert_geometries_equal(
                        existing_geom.shape, new_shape, normalize=True
                    )
                except AssertionError:
                    pass
                else:
                    return  # duplicate found; do not add
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
        new_type = LPFType(
            identifier=identifier,
            label=label,
            sourceLabels=sourceLabels,
            sourceLabel=sourceLabel,
            when=when,
        )
        if identifier not in self._types:
            self._types[identifier] = new_type
        else:
            former_type = self._types[identifier]
            if not former_type.label and new_type.label:
                former_type.label = new_type.label
            if sourceLabel:
                former_sl = [
                    sl for sl in former_type.sourceLabels if sl.label == sourceLabel
                ]
                if not former_sl:
                    former_type.sourceLabels.append(LPFSourceLabel(label=sourceLabel))
                elif len(former_sl) == 1:
                    pass  # already present
                else:
                    raise ValueError(
                        f"Multiple sourceLabels with label '{sourceLabel}' found in existing LPFType"
                    )
            if sourceLabels:
                raise NotImplementedError(
                    "Updating existing LPFType with sourceLabels not implemented yet"
                )
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
        return [l.to_dict() for l in self._links]

    @property
    def link_keys(self) -> list:
        """
        Get link identifiers as list
        """
        keys = set()
        for l in self._links:
            if validate_url(l.identifier):
                keys.add(l.identifier)
            else:
                keys.add(l.authority_alias + ":" + l.identifier)
        return list(keys)

    def add_link(
        self,
        identifier: str,
        link_type: str = "closeMatch",
        label: str = "",
        source: str = "",
        authority: str = "",
        authority_alias: str = "",
    ):
        """
        Add a link
        """
        if link_type not in VALID_LINK_TYPES:
            raise ValueError(f"Unrecognized link type: {link_type}")
        add_it = True
        keys = self.link_keys
        if validate_url(identifier):
            if identifier in keys:
                add_it = False
        elif authority_alias:
            key = authority_alias + ":" + identifier
            if key in keys:
                add_it = False
        else:
            key = slugify(authority) + ":" + identifier
            if key in keys:
                add_it = False
        if add_it:
            self._links.append(
                LPFLink(
                    identifier=identifier,
                    link_type=link_type,
                    label=label,
                    source=source,
                    authority=authority,
                    authority_alias=authority_alias,
                )
            )

    #
    # names
    #

    @property
    def names(self) -> list:
        """
        Get names as list
        """
        return self._names

    def get_names_by_lang(self, lang: str) -> list:
        """
        Get names by language
        """
        return [name for name in self._names if name.lang == lang]

    def get_namestrings_by_lang(self, lang: str) -> list:
        """
        Get name strings by language
        """
        nstrings = set()
        for name in self._names:
            if name.lang == lang:
                nstrings.add(name.toponym)
                nstrings.update(name.romanizations)
        return list(nstrings)

    @property
    def name_strings(self) -> list:
        nstrings = set()
        for name in self._names:
            nstrings.add(name.toponym)
            nstrings.update(name.romanizations)
        return list(nstrings)

    @property
    def name_toponyms(self) -> list:
        toponyms = set()
        for name in self._names:
            toponyms.add(name.toponym)
        return list(toponyms)

    def add_name(
        self,
        toponym: str,
        lang: str = "und",
        citations: list = [],
        when: dict = dict(),
        force=False,
    ):
        """
        Add a name
        """
        add_it = False
        normed = normalize_text(toponym)
        if force:
            add_it = True
        elif normed not in self.name_toponyms and not self.get_names_by_lang(lang):
            add_it = True
        if add_it:
            self._names.append(
                LPFName(toponym=toponym, lang=lang, citations=citations, when=when)
            )

    #
    # periods
    #
    def add_period(self, name: str, uri: str):
        """
        Add a period
        """
        self._periods.append(LPFPeriod(name=name, uri=uri))

    #
    # timespans
    #
    def add_timespan(self, start: dict, end: dict):
        """
        Add a timespan
        """
        self._timespans.append(LPFTimespan(start=start, end=end))

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

    #
    # when
    #
    @property
    def when(self) -> dict:
        """
        Create when as dict
        """
        d = dict()
        if self._timespans:
            d["timespans"] = [ts.to_dict() for ts in self._timespans]
        if self._periods:
            d["periods"] = [p.to_dict() for p in self._periods]
        return d

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
            "depictions": [d.to_dict() for d in self._depictions],
            "descriptions": [d.to_dict() for d in self._descriptions],
            "when": self.when,
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

    def _expand_whg_link_prefix(self, identifier: str) -> str:
        """
        Expand WHG link prefix to full URL
        """
        logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        if validate_url(identifier):
            return identifier
        prefix, id = identifier.split(":", 1)
        if prefix == "tgn":
            return f"http://vocab.getty.edu/tgn/{id}"
        elif prefix == "wd":
            return f"https://www.wikidata.org/wiki/{id}"
        elif prefix == "gn":
            return f"https://www.geonames.org/{id}"
        elif prefix == "loc":
            return f"https://id.loc.gov/authorities/names/{id}"
        elif prefix == "bnf":
            return f"https://catalogue.bnf.fr/ark:/12148/cb{id}"
        elif prefix == "viaf":
            return f"https://viaf.org/viaf/{id}"
        elif prefix == "wp":
            return f"https://en.wikipedia.org/wiki/{id}"
        else:
            logger.warning(f"Unrecognized WHG link prefix: {prefix}")

    def _augment_from_whg_db_api(self, place: LPFPlace, source_data: dict | list):
        """
        Augment place from WHG DB API data
        """
        logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
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
                    for link in v:
                        identifier = self._expand_whg_link_prefix(link["identifier"])
                        default_link_type = "closeMatch"
                        if urlparse(identifier).netloc == "en.wikipedia.org":
                            default_link_type = "seeAlso"
                        place.add_link(
                            identifier=identifier,
                            link_type=link.get("type", default_link_type),
                            label=link.get("label", ""),
                        )

                # related
                elif k == "related":
                    raise NotImplementedError(
                        "WHG DB API 'related' not implemented yet"
                    )

                # whens
                elif k == "whens":
                    for when in v:
                        place.add_when(**when)

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
                                if (
                                    isinstance(vv, list)
                                    and len(vv) == 1
                                    and isinstance(vv[0], list)
                                    and len(vv[0]) == 2
                                    and isinstance(vv[0][0], int)
                                    and isinstance(vv[0][1], int)
                                ):
                                    logger.warning(
                                        f"IGNORED WHG DB API 'timespans' value in properties; it appears to be a list of two integers: {vv}"
                                    )
                                else:
                                    raise NotImplementedError(
                                        f"WHG DB API 'timespans' not implemented yet (value: {vv})"
                                    )
                        else:
                            raise NotImplementedError(
                                f"WHG DB API property '{k}' not implemented yet"
                            )

                # geometry
                elif k == "geometry":
                    if v["type"] == "GeometryCollection":
                        geoms = v.get("geometries", [])
                    else:
                        geoms = [v]
                    for geom in geoms:
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

            # links
            elif k == "links":
                for link in v:
                    identifier = self._expand_whg_link_prefix(link["identifier"])
                    place.add_link(
                        identifier=identifier,
                        link_type=link.get("type", "closeMatch"),
                        label=link.get("label", ""),
                    )

            else:
                raise NotImplementedError(
                    f"WHG Place API key '{k}' not implemented yet"
                )

    def _augment_from_wikidata(self, place: LPFPlace, source_data: dict | list):
        """
        Augment place from Wikidata data
        """
        logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        for k, v in source_data.items():  # type: ignore
            if not v:
                continue
            if k == "type":
                if v != "item":
                    raise ValueError(
                        f"Wikidata entity unexpected type value {v}, expected item"
                    )

            elif k in {"labels", "aliases"}:
                target_langs = {code: 1 for code in WIKIDATA_LABEL_LANGUAGES}
                country_langs = dict()
                for country_id, country_data in self._get_wikidata_countries(source_data).items():  # type: ignore
                    for lang_data in country_data["official_languages"].values():
                        target_langs[lang_data["wiki_code"]] = 1
                        country_langs[lang_data["wiki_code"]] = 1
                for lang_id in target_langs:
                    try:
                        label = v[lang_id]
                    except KeyError:
                        continue
                    except TypeError as err:
                        err.add_note(
                            f"while processing Wikidata labels for lang '{lang_id}': {pformat(v)}"
                        )
                        raise err
                    if isinstance(label, str):
                        labels = [label]
                    elif isinstance(label, list):
                        labels = label
                    else:
                        raise TypeError(
                            f"Wikidata label for lang '{lang_id}' must be str or list. Got {type(label)}"
                        )
                    for label in labels:
                        place.add_name(
                            toponym=label,
                            lang=lang_id,
                            citations=[
                                LPFCitation(
                                    identifier=f"https://www.wikidata.org/wiki/{source_data['id']}",
                                    label=self._get_wikidata_preferred_label(
                                        source_data["id"]  # type: ignore
                                    ),
                                )
                            ],
                            force=(lang_id in country_langs),
                        )  # type: ignore

            elif k == "descriptions":
                # ignore descriptions for now
                pass

            elif k == "id":
                item_data = self._get_wikidata_item(v)
                try:
                    title = item_data["labels"]["en"]
                except KeyError as err:
                    err.add_note(pformat(item_data))
                    raise err
                place.add_link(
                    identifier=f"https://www.wikidata.org/wiki/{v}",
                    link_type="citesAsDataSource",
                    label=title,
                )
            elif k == "sitelinks":
                # other Wiki links
                for langid in WIKIDATA_LABEL_LANGUAGES:
                    try:
                        wikivals = v[f"{langid}wiki"]
                    except KeyError:
                        continue
                    place.add_link(
                        identifier=wikivals["url"],
                        link_type="seeAlso",
                        label=wikivals["title"],
                    )

                # try to get wikipedias for the containing country's official languages as well
                hits = 0
                wiki_lang_codes = set()
                for country_id, country_data in self._get_wikidata_countries(source_data).items():  # type: ignore
                    for lang_data in country_data["official_languages"].values():
                        wiki_lang_codes.add(lang_data["wiki_code"])
                for wiki_lang_code in wiki_lang_codes:
                    try:
                        wikivals = v[wiki_lang_code]
                    except KeyError:
                        continue
                    hits += 1
                    place.add_link(
                        identifier=wikivals["url"],
                        link_type="seeAlso",
                        label=wikivals["title"],
                    )

                # if hits == 0:
                #     # try to add wikipedia articles in the official languages of the most populous countries
                #     # on the continent where the place is located
                #     logger.debug(pformat(source_data, indent=2))
                #     continents = self._get_wikidata_continents(source_data)  # type: ignore
                #     if not continents:
                #         continents = dict()
                #         for country_id, country_data in = self._get_wikidata_countries(source_data).items():  # type: ignore
                #             for continent_id, continent_data in country_data.get("continents", []).items():
                #                 continents[continent_id] = continent_data
                #     # from here a sparql query would be the best bet, but for now we will not try to get more wikipedia links

            elif k == "statements":

                properties_4_links = {
                    "P4102",  #  Atlas of Hillforts ID
                    "P5633",  #  Amphi-Theatrum ID
                    "P10053",  #  Atlas Project of Roman Aqueducts ID
                    "P8218",  #  Archaeology in Greece Online place ID
                    "P10510",  # Arachne entity ID
                    "P268",  # Bibliothèque nationale de France ID
                    "P4711",  # CHGIS ID
                    "P13279",  # Dictionary of Late Antiquity ID
                    "P1936",  #  Digital Atlas of the Roman Empire ID
                    "P9505",  #  Gardens of the Roman Empire ID
                    "P1566",  # GeoNames ID
                    "P2326",  # GNS Unique Feature ID (National Geospatial-Intelligence Agency's GEOnet Names Server)
                    "P1667",  # Getty Thesaurus of Geographic Names ID
                    "P9951",  # Greek Castles ID (Kastrologos)
                    "P8406",  #  Grove Art Online ID
                    "P6916",  #  Heritage Gazetteer of Cyprus
                    "P6751",  #  Heritage Gazetteer of Libya ID
                    "P8217",  #  iDAI.gazetteer ID
                    "P8137",  # Inventory of Archaic and Classical Poleis ID
                    "P1369",  # Iranian National Heritage registration number
                    "P244",  # Library of Congress authority ID
                    "P9736",  #  MANTO ID
                    "P4356",  # Megalithic Portal ID
                    "P9957",  # Museum-digital ID
                    "P2950",  # Nomisma ID
                    "P402",  # OpenStreetMap relation ID
                    "P11693",  # OpenStreetMap node ID
                    "P9106",  # Oxford Classical Dictionary ID
                    "P4212",  # PACTOLS thesaurus ID
                    "P12062",  # Pinakes city ID
                    "P1584",  #  Pleiades ID
                    "P13136",  #  Princeton Encyclopedia of Classical Sites ID
                    "P13496",  #  The Rural Settlement of Roman Britain ID
                    "P5634",  # Theatrum ID
                    "P8069",  # ToposText person ID
                    "P1958",  # Trismegistos Geo ID
                    "P214",  # VIAF ID
                    "P1481",  #  vici.org ID
                    "P13061",  #  World Historical Gazetteer place ID
                    "P13591",  # Yale LUX ID
                }
                for prop_id, prop_val in v.items():
                    # logger.debug(prop_id)
                    if prop_id in {
                        "P373",  # commons category
                        "P473",  # local dialing code
                        "P19",  # place of birth
                        "P646",  # freebase ID
                        "P190",  #  twinned administrative body
                        "P1464",  # category for people born here
                        "P1465",  # category for people who died here
                        "P1792",  #  category of associated people
                        "P2044",  # elevation above sea level
                        "P1997",  #  facebook location ID)
                        "P1082",  # population
                        "P948",  #  page banner
                        "P856",  # official website
                        "P421",  # time zone
                        "P3417",  # Quora topic ID
                        "P1417",  # Encyclopædia Britannica Online ID
                        "P3219",  # Encyclopædia Universalis ID
                        "P443",  # Pronunciation audio
                        "P1376",  # Capital of
                        "P2924",  # Great Russian Encyclopedia Online ID (old version)
                        "P6766",  # Who's on First ID
                        "P982",  # MusicBrainz area ID
                        "P227",  # GND ID
                        "P8189",  # National Library of Israel ID
                        "P269",  # IDref ID
                        "P9495",  # National Historical Museums of Sweden ID
                        "P7305",  # Online PWN Encyclopedia ID
                        "P1791",  # category for people buried here
                        "P1540",  # male population
                        "P1539",  # female population
                        "P950",  # National Library of Spain SpMaBN ID (BNE v1.0)
                        "P8179",  # Canadiana name authority ID
                        "P2163",  # FAST ID
                        "P463",  # member of
                        "P12749",  # SNARC ID
                        "P7314",  # TDV Encyclopedia of Islam ID
                        "P8168",  # FactGrid ID
                    }:
                        continue

                    if prop_id == "P17":  # country
                        logger.debug(f"Wikidata country: {pformat(prop_val, indent=2)}")
                        country_id = prop_val[0]["value"]["content"]
                        country_data = self._get_wikidata_country_data(country_id)
                        place.add_country_code(country_data["country_code"])

                    elif prop_id in properties_4_links:
                        prop_data = self._get_wikidata_property(prop_id)
                        try:
                            identifier = prop_data["url_template"].format(
                                prop_val[0]["value"]["content"]
                            )
                        except KeyError:
                            # some properties do not have url_template
                            identifier = prop_val[0]["value"]["content"]
                        place.add_link(identifier=identifier, link_type="closeMatch")
                    elif prop_id == "P1343":  # described by source
                        ignore_refs = {
                            "Q867541": "Encyclopædia Britannica 11th edition"
                        }
                        for ref in prop_val:
                            item_id = ref["value"]["content"]
                            if item_id in ignore_refs:
                                continue
                            else:
                                item_data = self._get_wikidata_item(item_id)
                                logger.debug(
                                    f"Unhandled described by source: {item_data['title']['en']})"
                                )
                                exit()
                    elif prop_id == "P625":  # coordinate location
                        try:
                            lat = prop_val[0]["value"]["content"]["latitude"]
                        except (TypeError, KeyError) as err:
                            err.add_note(f"{pformat(prop_val, indent=2)}")
                            raise err
                        lon = prop_val[0]["value"]["content"]["longitude"]
                        precision = prop_val[0]["value"]["content"]["precision"]
                        whence = prop_val[0]["references"][0]["parts"][0]["value"][
                            "content"
                        ]
                        if whence == "Q830106":
                            citations = [LPFCitation(label="GeoNames")]
                        elif whence == "Q48952":
                            citations = [LPFCitation(label="Persian Wikipedia")]
                        else:
                            raise NotImplementedError(
                                f"Wikidata coordinate location reference '{whence}' not implemented yet"
                            )
                        place.add_geometry(
                            geom_type="Point",
                            coordinates=[lon, lat],
                            certainty=(
                                "certain"
                                if precision and precision <= 0.0001
                                else "uncertain"
                            ),
                            citations=citations,
                        )
                    elif prop_id in {
                        "P910",  # topic's main category
                        "P7867",  # category for maps or plans
                        "P8989",  # category for the view of the item
                    }:
                        item_id = prop_val[0]["value"]["content"]
                        item_data = self._get_wikidata_item(item_id)
                        statement_data = item_data["statements"].get("P373")
                        if statement_data:
                            label = statement_data[0]["value"]["content"]
                            identifier = (
                                f"https://commons.wikimedia.org/wiki/Category:{label}"
                            )
                            place.add_link(
                                identifier=identifier,
                                link_type="seeAlso",
                                label=label,
                            )
                    elif (
                        prop_id == "P131"
                    ):  # located in the administrative territorial entity
                        wherein = []
                        item_id = prop_val[0]["value"]["content"]
                        while True:
                            wherein.append(self._get_wikidata_preferred_label(item_id))
                            item_data = self._get_wikidata_item(item_id)
                            try:
                                item_id = item_data["statements"]["P131"][0]["value"][
                                    "content"
                                ]
                            except KeyError:
                                break
                        if wherein:
                            place.add_description(
                                value=f"Located in: {', '.join(wherein)}",
                                lang="en",
                                citations=[
                                    LPFCitation(
                                        identifier=f"https://www.wikidata.org/wiki/{source_data['id']}",  # type: ignore
                                        label=self._get_wikidata_preferred_label(
                                            source_data["id"]  # type: ignore
                                        ),
                                    ),
                                ],
                            )
                    elif prop_id == "P31":  # instance of
                        for item in prop_val:
                            item_id = item["value"]["content"]
                            label = self._get_wikidata_preferred_label(item_id)
                            item_data = self._get_wikidata_item(item_id)
                            identifier = f"https://www.wikidata.org/wiki/{item_id}"
                            include = True
                            while True:
                                try:
                                    gn_feature_class = item_data["statements"]["P2452"]
                                except KeyError:
                                    pass
                                else:
                                    gn_feature_class = gn_feature_class[0]["value"][
                                        "content"
                                    ]
                                    gn_feature_class = gn_feature_class.split(".")[0]
                                    place.add_feature_class(gn_feature_class)
                                try:
                                    aat_ids = item_data["statements"][
                                        "P1014"
                                    ]  # getty AAT ID
                                except KeyError:
                                    pass
                                else:
                                    for aat_id in aat_ids:
                                        url = f"http://vocab.getty.edu/aat/{aat_id['value']['content']}"
                                        label = self._get_webpage_title(url)
                                        place.add_type(
                                            identifier=url,
                                            label=label,
                                        )
                                parts = label.split(" of ", 1)
                                if len(parts) == 2 and parts[0].strip() in {
                                    "administrative divisions",
                                    "administrative territorial entity",
                                    "city",
                                }:
                                    include = False
                                    try:
                                        item_id = item_data["statements"]["P279"][0][
                                            "value"
                                        ]["content"]
                                    except KeyError:
                                        break
                                    else:
                                        label = self._get_wikidata_preferred_label(
                                            item_id
                                        )
                                        identifier = (
                                            f"https://www.wikidata.org/wiki/{item_id}"
                                        )
                                        item_data = self._get_wikidata_item(item_id)
                                else:
                                    include = True
                                    break
                            if include:
                                place.add_type(
                                    identifier=identifier,
                                    label=label,
                                )
                                for term in [
                                    "city",
                                    "town",
                                    "village",
                                    "settlement",
                                    "hamlet",
                                ]:
                                    if term in label.lower():
                                        place.add_feature_class("P")  # populated place
                                        break

                    elif prop_id == "P18":  # image
                        for item in prop_val:
                            label = item["value"]["content"]
                            identifier = f"https://commons.wikimedia.org/wiki/File:{label.replace(' ', '_')}"
                            place.add_depiction(title=label, identifier=identifier)
                    elif prop_id in {"P1705", "P1448"}:  # native label, official name
                        for item in prop_val:
                            lang_code = item["value"]["content"]["language"]
                            toponym = item["value"]["content"]["text"]
                            place.add_name(
                                toponym=toponym,
                                lang=lang_code,
                                citations=[
                                    LPFCitation(
                                        identifier=f"https://www.wikidata.org/wiki/{source_data['id']}",  # type: ignore
                                        label=self._get_wikidata_preferred_label(
                                            source_data["id"]  # type: ignore
                                        ),
                                    )
                                ],
                                force=True,  # make sure this name gets added even if we already have other names in this language
                            )
                    elif prop_id == "P1435":  # heritage designation
                        for item in prop_val:
                            item_id = item["value"]["content"]
                            label = self._get_wikidata_preferred_label(item_id)
                            place.add_description(
                                value=f"Heritage designation: {label}",
                                lang="en",
                                citations=[
                                    LPFCitation(
                                        identifier=f"https://www.wikidata.org/wiki/{source_data['id']}",  # type: ignore
                                        label=self._get_wikidata_preferred_label(
                                            source_data["id"]  # type: ignore
                                        ),
                                    ),
                                ],
                            )
                    elif prop_id == "P2348":  # time period
                        # create a when for the place
                        for item in prop_val:
                            item_id = item["value"]["content"]
                            # period
                            period_name = self._get_wikidata_preferred_label(item_id)
                            period_url = f"https://www.wikidata.org/wiki/{item_id}"
                            place.add_period(
                                name=period_name,
                                uri=period_url,
                            )
                            # timespan
                            item_data = self._get_wikidata_item(item_id)
                            span = []
                            for time_prop in ["P580", "P582"]:  # start time, end time
                                try:
                                    time = [
                                        t["value"]["content"]
                                        for t in item_data["statements"].get(
                                            time_prop, []
                                        )
                                        if t["value"]["content"]["calendarmodel"]
                                        == "Q1985786"
                                    ][0]["time"]
                                except (IndexError, KeyError):
                                    break
                                m = RX_WIKIDATA_TIME.match(time)
                                if m:
                                    span.append(m.group("year"))
                                else:
                                    break
                            if len(span) == 2:
                                place.add_timespan(
                                    start=span[0],
                                    end=span[1],
                                )
                    else:
                        logger.debug(pformat(prop_val, indent=2))
                        raise NotImplementedError(
                            f"Wikidata property '{prop_id}' not implemented yet: {pformat(prop_val)}"
                        )
            #
            elif k == "title":
                raise NotImplementedError(
                    "Wikidata 'title' at top level is not handled yet"
                )
            else:
                logger.debug(pformat(v, indent=2))
                raise NotImplementedError(
                    f"Wikidata key '{k}' not implemented yet: {pformat(v)}"
                )

    def _get_wikidata_country_data(self, country_id: str) -> dict:
        """
        Get Wikidata country data
        """
        if country_id in self._wikidata_country_info:
            return self._wikidata_country_info[country_id]
        raw_country_data = self._get_wikidata_item(country_id)
        country_record = {
            "label": self._get_wikidata_preferred_label(country_id),
            "official_languages": self._get_wikidata_official_languages(
                raw_country_data
            ),
            "official_names": self._get_wikidata_official_names(raw_country_data),
            "continents": self._get_wikidata_continents(raw_country_data),
        }
        try:
            country_code = raw_country_data["statements"]["P297"][0]["value"]["content"]
        except KeyError as err:
            err.add_note(f"Wikidata country {country_id} has no P297 country code")
            raise err
        country_record["country_code"] = country_code
        self._wikidata_country_info[country_id] = country_record
        return country_record

    def _get_wikidata_language_data(self, lang_id: str) -> dict:
        """
        Get Wikidata language data
        """
        if lang_id in self._wikidata_language_info:
            return self._wikidata_language_info[lang_id]
        pref_label = self._get_wikidata_preferred_label(lang_id)  # type: ignore
        language_data = {"label": pref_label, "code": "", "wiki_code": ""}
        item_data = self._get_wikidata_item(lang_id)
        # wiki code P424
        for code_entry in item_data["statements"].get("P424", []):
            code_s = code_entry["value"]["content"]
            language_data["wiki_code"] = code_s
            break
        # iso 639-1 code P218
        for code_entry in item_data["statements"].get("P218", []):
            code_s = code_entry["value"]["content"]
            language_data["code"] = code_s
            break
        self._wikidata_language_info[lang_id] = language_data
        return language_data

    @lru_cache(maxsize=512)
    def _get_wikidata_preferred_label(self, item_id: str) -> str:
        """
        Get Wikidata preferred label
        """
        item_data = self._get_wikidata_item(item_id)
        for lang in WIKIDATA_LABEL_LANGUAGES:
            try:
                label_entry = item_data["labels"][lang]
            except KeyError:
                continue
            return label_entry
        raise RuntimeError("Preferred label not found in expected languages")

    def _get_wikidata_continents(self, item_data: dict) -> dict:
        """
        Get Wikidata continents
        """
        continents = dict()
        for cont_entry in item_data["statements"].get("P30", []):
            cont_id = cont_entry["value"]["content"]
            cont_data = self._get_wikidata_continent_data(cont_id)
            continents[cont_id] = cont_data
        return continents

    def _get_wikidata_countries(self, item_data: dict) -> dict:
        """
        Get Wikidata countries
        """
        countries = dict()
        for country_entry in item_data["statements"].get("P17", []):
            country_id = country_entry["value"]["content"]
            country_data = self._get_wikidata_country_data(country_id)
            countries[country_id] = country_data
        return countries

    @lru_cache()
    def _get_wikidata_continent_data(self, cont_id: str) -> dict:
        """
        Get Wikidata continent data
        """
        if cont_id in self._wikidata_continent_info:
            return self._wikidata_continent_info[cont_id]
        continent_data = {"label": "", "official_names": dict()}
        continent_data["label"] = self._get_wikidata_preferred_label(cont_id)
        item_data = self._get_wikidata_item(cont_id)
        continent_data["official_names"] = self._get_wikidata_official_names(item_data)
        self._wikidata_continent_info[cont_id] = continent_data
        return continent_data

    def _get_wikidata_official_languages(self, item_data: dict) -> dict:
        """
        Get Wikidata official languages
        """
        languages = dict()
        for lang_entry in item_data["statements"].get("P37", []):
            lang_id = lang_entry["value"]["content"]
            lang_data = self._get_wikidata_language_data(lang_id)
            languages[lang_id] = lang_data
        return languages

    def _get_wikidata_official_names(self, item_data: dict) -> dict:
        """
        Get Wikidata official names
        """
        official_names = dict()
        for name_entry in item_data["statements"].get("P1448", []):
            lang_id = name_entry["value"]["content"]["language"]
            official_names[lang_id] = name_entry["value"]["content"]["text"]
        return official_names

    def _get_wikidata_item(self, item_id: str) -> dict:
        """
        Get Wikidata item data
        """
        base_url = "https://www.wikidata.org/w/rest.php/wikibase/v1"
        url = f"{base_url}/entities/items/{item_id}"
        url_parts = urlparse(url)
        interface = web_interfaces[url_parts.netloc]
        r = interface.get(url)
        return r.json()

    def _get_wikidata_place_data(self, place_id: str) -> dict:
        """
        Get Wikidata place data
        """
        if place_id in self._wikidata_place_info:
            return self._wikidata_place_info[place_id]
        item_data = self._get_wikidata_item(place_id)
        place = {"label": "", "official_names": dict(), "countries": dict()}

        # preferred label "labels"
        place["label"] = self._get_wikidata_preferred_label(place_id)

        # official names P1448
        place["official_names"] = self._get_wikidata_official_names(item_data)

        # country
        for country_id, country_data in self._get_wikidata_countries(item_data).items():
            place["countries"][country_id] = country_data["label"]

        self._wikidata_place_info[place_id] = place
        return place

    def _get_wikidata_property(self, prop_id: str) -> dict:
        """
        Get Wikidata property data
        """
        if prop_id in self._wikidata_properties:
            return self._wikidata_properties[prop_id]
        base_url = "https://www.wikidata.org/w/rest.php/wikibase/v1"
        url = f"{base_url}/entities/properties/{prop_id}"
        url_parts = urlparse(url)
        interface = web_interfaces[url_parts.netloc]
        r = interface.get(url)
        prop_data = r.json()
        try:
            formatter_url = prop_data["statements"].get("P1630")[0]["value"]["content"]
        except TypeError as err:
            formatter_url = ""
        else:
            formatter_url = formatter_url.replace("$1", "{}")
        self._wikidata_properties[prop_id] = {
            "title": prop_data.get("labels", {}).get("en", ""),
            "description": prop_data.get("descriptions", {}).get("en", ""),
        }
        if formatter_url:
            self._wikidata_properties[prop_id]["url_template"] = formatter_url
        return self._wikidata_properties[prop_id]

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
        # substitute url for API if needed
        if url_parts.netloc == "www.wikidata.org":
            base_url = "https://www.wikidata.org/w/rest.php/wikibase/v1"
            qid = url_parts.path.split("/")[-1]
            url = f"{base_url}/entities/items/{qid}"
            url_parts = urlparse(url)
            self._wikidata_properties = dict()
            self._wikidata_place_info = dict()
            self._wikidata_country_info = dict()
            self._wikidata_continent_info = dict()
            self._wikidata_continents_by_place = dict()
            self._wikidata_countries_by_place = dict()
            self._wikidata_language_info = dict()
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

    def _get_webpage_title(self, url: str) -> str:
        """
        Get webpage title
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
        html_soup = BeautifulSoup(r.text, "html.parser")
        title_tag = html_soup.find("title")
        if title_tag:
            return normalize_text(title_tag.string)
        else:
            return ""
