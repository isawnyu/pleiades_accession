#
# This file is part of pleiades_accession
# by Tom Elliott for the Institute for the Study of the Ancient World
# (c) Copyright 2025 by New York University
# Licensed under the AGPL-3.0; see LICENSE.txt file.
#

"""
Test the candidates module
"""

import json
from pathlib import Path
from platformdirs import user_cache_path
from pleiades_accession.candidates import CandidateDataset, CandidateFeature

test_data_path = Path(__file__).parent / "data"
test_cache_path = user_cache_path("pleiades_accession_test", ensure_exists=True)


class TestCandidatesDataset:
    def test_init(self):
        p = CandidateDataset(test_data_path / "gethin_monasteries.json")


class TestCandidateFeature:
    def test_init(self):
        s = """
            {
                "type": "Feature",
                "@id": "https://whgazetteer.org/api/db/?id=6524428",
                "properties": {
                    "pid": 6524428,
                    "src_id": "wgm5",
                    "title": "Chaul",
                    "ccodes": [
                    "IN"
                    ],
                    "comment": []
                },
                "geometry": {
                    "type": "GeometryCollection",
                    "geometries": [
                    {
                        "type": "MultiPoint",
                        "citation": {
                        "id": "wd:Q1068374",
                        "label": "Wikidata"
                        },
                        "coordinates": [
                        [
                            72.9272,
                            18.5461
                        ]
                        ]
                    },
                    {
                        "type": "Point",
                        "geowkt": "POINT(72.947 18.568)",
                        "coordinates": [
                        72.947,
                        18.568
                        ]
                    }
                    ]
                },
                "names": [
                    {
                    "lang": "",
                    "toponym": "Chaul",
                    "citations": [
                        {
                        "id": "https://doi.org/10.5281/zenodo.998080",
                        "label": "10.5281/zenodo.998080"
                        }
                    ]
                    }
                ],
                "types": [
                    {
                    "label": "",
                    "identifier": "",
                    "sourceLabel": "Buddhist monastery"
                    },
                    {
                    "label": "",
                    "identifier": "",
                    "sourceLabel": "Satavahana"
                    },
                    {
                    "label": "",
                    "identifier": "",
                    "sourceLabel": "Early Historic"
                    }
                ],
                "links": [
                    {
                    "type": "closeMatch",
                    "identifier": "wd:Q1068374"
                    },
                    {
                    "type": "closeMatch",
                    "identifier": "gn:1274503"
                    },
                    {
                    "type": "closeMatch",
                    "identifier": "viaf:245125742"
                    }
                ],
                "when": {
                    "timespans": [
                    {
                        "end": {
                        "latest": "0449"
                        },
                        "start": {
                        "earliest": "0100"
                        }
                    }
                    ]
                }
            }"""
        j = json.loads(s)
        f = CandidateFeature(j)
        assert f.id == "https://whgazetteer.org/api/db/?id=6524428"
        assert f.geometry.geom_type == "GeometryCollection"
        assert f.properties["pid"] == 6524428
