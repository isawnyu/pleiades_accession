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
from pleiades_accession.making import Maker

test_data_path = Path(__file__).parent / "data"


class TestMaker:
    def test_init(self):
        m = Maker()
        assert isinstance(m, Maker)
