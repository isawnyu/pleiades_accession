#
# This file is part of pleiades_accession
# by Tom Elliott for the Institute for the Study of the Ancient World
# (c) Copyright 2025 by New York University
# Licensed under the AGPL-3.0; see LICENSE.txt file.
#

"""
Matching script
"""

from airtight.cli import configure_commandline
import logging
from os import environ
from pathlib import Path
from pleiades_accession.matching import Matcher
from pleiades_accession.pleiades import Pleiades
from pleiades_accession.candidates import CandidateDataset

default_pleiades_dataset_path = (
    Path(environ.get("PLEIADES_DATASET_PATH", "")).expanduser().resolve()
)
default_pleiades_names_index_path = (
    Path(environ.get("PLEIADES_NAMES_INDEX_PATH", "")).expanduser().resolve()
)

logger = logging.getLogger(__name__)

DEFAULT_LOG_LEVEL = logging.WARNING
OPTIONAL_ARGUMENTS = [
    [
        "-l",
        "--loglevel",
        "NOTSET",
        "desired logging level ("
        + "case-insensitive string: DEBUG, INFO, WARNING, or ERROR",
        False,
    ],
    ["-v", "--verbose", True, "verbose output (logging level == INFO)", False],
    [
        "-w",
        "--veryverbose",
        False,
        "very verbose output (logging level == DEBUG)",
        False,
    ],
    [
        "-p",
        "--pleiadespath",
        str(default_pleiades_dataset_path),
        "path to Pleiades dataset directory",
        False,
    ],
    [
        "-n",
        "--namesindexpath",
        str(default_pleiades_names_index_path),
        "path to Pleiades names index file (if not in dataset directory)",
        False,
    ],
    [
        "-c",
        "--candidatespath",
        "",
        "path to candidate places LPF GeoJSON file",
        True,
    ],
]
POSITIONAL_ARGUMENTS = [
    # each row is a list with 3 elements: name, type, help
]


def main(**kwargs):
    """
    main function
    """
    # logger = logging.getLogger(sys._getframe().f_code.co_name)
    pleiades = Pleiades(kwargs["pleiadespath"], kwargs["namesindexpath"])
    candidates = CandidateDataset(kwargs["candidatespath"])


if __name__ == "__main__":
    main(
        **configure_commandline(
            OPTIONAL_ARGUMENTS, POSITIONAL_ARGUMENTS, DEFAULT_LOG_LEVEL
        )
    )
