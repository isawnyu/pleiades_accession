#
# This file is part of pleiades_accession
# by Tom Elliott for the Institute for the Study of the Ancient World
# (c) Copyright 2025 by New York University
# Licensed under the AGPL-3.0; see LICENSE.txt file.
#

"""
Code to manage dataset of candidate places for accessioning into Pleiades"""

import json
import logging
from pathlib import Path
from pprint import pformat
from shapely.geometry import shape

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
