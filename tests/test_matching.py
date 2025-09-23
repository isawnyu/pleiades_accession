#
# This file is part of pleiades_accession
# by Tom Elliott for the Institute for the Study of the Ancient World
# (c) Copyright 2025 by New York University
# Licensed under the AGPL-3.0; see LICENSE.txt file.
#

"""
Test the pleiades module
"""

from pathlib import Path
from pleiades_accession.matching import Matcher
from pleiades_accession.pleiades import Pleiades
from pleiades_accession.candidates import CandidateDataset

test_data_path = Path(__file__).parent / "data"


class TestMatcher:
    def test_init(self):
        pleiades = Pleiades(test_data_path / "pleiades_json")
        candidates = CandidateDataset(test_data_path / "lehning_periplus.json")
        m = Matcher(pleiades, candidates)
        m.match()
