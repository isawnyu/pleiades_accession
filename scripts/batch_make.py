#
# This file is part of pleiades_accession
# by Tom Elliott for the Institute for the Study of the Ancient World
# (c) Copyright 2025 by New York University
# Licensed under the AGPL-3.0; see LICENSE.txt file.
#

"""
Make a batch of LPF places from provided resources"""

from airtight.cli import configure_commandline
import json
import logging
from pathlib import Path
from pleiades_accession.making import Maker
from pprint import pformat
from slugify import slugify
import sys

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
    ["-v", "--verbose", False, "verbose output (logging level == INFO)", False],
    [
        "-w",
        "--veryverbose",
        False,
        "very verbose output (logging level == DEBUG)",
        False,
    ],
]
POSITIONAL_ARGUMENTS = [
    # each row is a list with 3 elements: name, type, help
    ["input_file", str, "path to input file containing list of resources"],
    ["output_file", str, "path to output LPF file"],
]


def main(**kwargs):
    """
    main function
    """
    input_path = Path(kwargs["input_file"]).expanduser().resolve()
    output_path = Path(kwargs["output_file"]).expanduser().resolve()
    if output_path.exists():
        if not output_path.is_dir():
            raise FileExistsError(
                f"Output path {output_path} already exists and is not a directory."
            )
    output_path.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(sys._getframe().f_code.co_name)
    with open(input_path, "r", encoding="utf-8") as f:
        uris = [line.strip() for line in f if line.strip()]
    del f
    m = Maker()
    results = dict()
    for uri in uris:
        place = m.make(sources=[uri])
        pd = place.to_dict()
        logger.debug(pformat(pd, indent=2))
        logger.info(f"Generated place with title: {place.title}")
        slug = slugify(place.title)
        try:
            results[slug]
        except KeyError:
            results[slug] = 1
        else:
            count = len([k for k in results.keys() if k.startswith(slug)])
            slug = f"{slug}-{count}"
            results[slug] = 1
        with open(output_path / f"{slug}.json", "w", encoding="utf-8") as f:
            json.dump(pd, f, ensure_ascii=False, indent=2, sort_keys=True)
        del f
    for slug in results.keys():
        print(output_path / f"{slug}.json")


if __name__ == "__main__":
    main(
        **configure_commandline(
            OPTIONAL_ARGUMENTS, POSITIONAL_ARGUMENTS, DEFAULT_LOG_LEVEL
        )
    )
