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
        logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        logger.info(pformat(place.to_dict(), indent=2))
