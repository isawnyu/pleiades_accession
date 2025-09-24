#
# This file is part of pleiades_accession
# by Tom Elliott for the Institute for the Study of the Ancient World
# (c) Copyright 2025 by New York University
# Licensed under the AGPL-3.0; see LICENSE.txt file.
#

"""
Code to manage dataset of candidate places for accessioning into Pleiades"""

import functools
import json
import logging
from pathlib import Path
from pprint import pformat
from shapely.geometry import shape
from validators import url as validate_url


class CandidateFeature:
    """
    wrapper for a single candidate feature for accessioning into Pleiades
    """

    def __init__(self, feature: dict):
        """Initialize the CandidateFeature from a GeoJSON feature dictionary."""
        self.feature = feature
        self.id = feature.get("@id")
        self.geometry = shape(feature.get("geometry", dict()))
        self.properties = feature.get("properties", dict())

    @property
    @functools.lru_cache(maxsize=None)
    def name_strings(self) -> set:
        """Return a set containing all name strings for the place."""
        name_strings = set()
        name_strings.add(self.properties["title"].strip())
        name_strings.update({n["toponym"].strip() for n in self.feature["names"]})
        return name_strings

    @property
    @functools.lru_cache(maxsize=None)
    def links(self) -> set:
        """Return a set containing all linked for the place."""
        links = set()
        for link in self.feature.get("links", []):
            if link["type"] == "closeMatch":
                if link["identifier"].startswith("http"):
                    raw_link = link["identifier"]
                else:
                    namespace, identifier = link["identifier"].split(":", 1)
                    if namespace == "pl":
                        raw_link = f"https://pleiades.stoa.org/places/{identifier}"
                    elif namespace == "wd":
                        raw_link = f"https://www.wikidata.org/wiki/{identifier}"
                    elif namespace == "viaf":
                        raw_link = f"https://viaf.org/viaf/{identifier}"
                    elif namespace == "wp":
                        raw_link = f"https://en.wikipedia.org/wiki/{identifier.replace(' ', '_')}"
                    elif namespace == "gn":
                        raw_link = f"https://www.geonames.org/{identifier}"
                    elif namespace == "tgn":
                        raw_link = f"http://vocab.getty.edu/tgn/{identifier}"
                    elif namespace in ["loc", "gnd", "bnf"]:
                        # ignore these links for now
                        continue
                    else:
                        raise NotImplementedError(
                            f"Unrecognized link namespace: {namespace}"
                        )
                (
                    links.add(raw_link)
                    if validate_url(raw_link)
                    else logging.warning(
                        f"IGNORED: Invalid URL found in candidate links: {raw_link}"
                    )
                )
        return links


class CandidateDataset:
    """
    Manage a dataset of candidate places for accessioning into Pleiades
    """

    def __init__(self, candidates_path: Path):
        """Initialize the CandidateDataset manager."""
        self.path = candidates_path
        self.features = dict()
        self._load_candidates()

    def _load_candidates(self):
        """Load candidate places from the specified path."""
        logger = logging.getLogger(f"{__name__}._load_candidates")
        candidates = dict()
        with open(self.path, "r", encoding="utf-8") as f:
            j = json.load(f)
        del f
        self.citation = j.get("citation", dict())
        logger.debug(
            "\n".join(
                [
                    f"Loading candidates from {self.path}:",
                    pformat(self.citation, indent=4),
                ]
            )
        )
        for feature in j.get("features", []):
            try:
                self.features[feature["@id"]]
            except KeyError:
                candidates[feature["@id"]] = CandidateFeature(feature)
            else:
                raise ValueError(f"Duplicate candidate feature ID: {feature['@id']}")
        try:
            expected_feature_count = j["citation"]["record_count"]
        except KeyError:
            pass
        else:
            if expected_feature_count != len(candidates):
                logger.warning(
                    f"FEATURE COUNT MISMATCH: Expected {expected_feature_count} features (see citation:record_count), found {len(candidates)}"
                )
        logger.info(f"Loaded {len(candidates):,} candidate features")
        self.features = candidates

    def __len__(self):
        """Return the number of candidate features in the dataset."""
        return len(self.features)
