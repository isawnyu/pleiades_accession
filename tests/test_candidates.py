#
# This file is part of pleiades_accession
# by Tom Elliott for the Institute for the Study of the Ancient World
# (c) Copyright 2025 by New York University
# Licensed under the AGPL-3.0; see LICENSE.txt file.
#

"""
Test the candidates module
"""

from pathlib import Path
from platformdirs import user_cache_path
from pleiades_accession.candidates import CandidateDataset

test_data_path = Path(__file__).parent / "data"
test_cache_path = user_cache_path("pleiades_accession_test", ensure_exists=True)


class TestCandidatesDataset:
    def test_init(self):
        p = CandidateDataset(test_data_path / "gethin_monasteries.json")
