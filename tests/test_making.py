#
# This file is part of pleiades_accession
# by Tom Elliott for the Institute for the Study of the Ancient World
# (c) Copyright 2025 by New York University
# Licensed under the AGPL-3.0; see LICENSE.txt file.
#

"""
Test the making module
"""
import logging
from pathlib import Path
from pleiades_accession.making import Maker, LPFPlace
from pprint import pprint, pformat

test_data_path = Path(__file__).parent / "data"


class TestMaker:
    def test_init(self):
        m = Maker()
        assert isinstance(m, Maker)

    def test_make_from_wsg(self):
        m = Maker()
        assert isinstance(m, Maker)
        place = m.make(
            sources=[
                "https://whgazetteer.org/api/db/?id=6691895",
            ]
        )
        assert len(m.places) == 1
        assert isinstance(place, LPFPlace)
        assert isinstance(place.id, str)
        logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        s = place.to_dict()
        logger.info(pformat(s, indent=2))
        assert s["type"] == "Feature"
        assert s["links"] == [
            {
                "identifier": "https://whgazetteer.org/api/place/6691895",
                "label": "",
                "type": "citesAsDataSource",
            },
            {
                "identifier": "https://whgazetteer.org/datasets/838/places",
                "label": "An Historical Atlas of Central Asia",
                "type": "member",
            },
        ]
        assert s["properties"]["ccodes"] == ["TM"]
        assert s["properties"]["fclasses"] == ["S"]
        assert s["properties"]["title"] == "Daya-Khatïn"
        assert s["types"] == [
            {"identifier": "aat:300000810", "label": "archaeological site"}
        ]
        assert s["geometry"] == {
            "type": "GeometryCollection",
            "geometries": [{"type": "Point", "coordinates": [62.286987, 40.063667]}],
        }
