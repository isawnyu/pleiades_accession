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
from shapely import Point

test_data_path = Path(__file__).parent / "data"


class TestPleiades:
    def test_init(self):
        p = Pleiades(test_data_path / "pleiades_json")
        assert len(p) == 1603

    def test_spatial_index(self):
        p = Pleiades(test_data_path / "pleiades_json")
        assert p._spatial_index is not None
        assert len(p._spatial_index) == 1244
        assert len(p._spatial_index_2_pid) == 1244
        c = Point(32.2592853, 40.0619819)
        results = p.spatial_query(c)
        assert results == [
            "582288341",
        ]
