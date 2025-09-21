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
from pleiades_accession.pleiades import Pleiades

test_data_dir = Path(__file__).parent / "data"


class TestPleiades:
    def test_init(self):
        p = Pleiades(test_data_dir / "pleiades_json")
        assert len(p) == 6545
