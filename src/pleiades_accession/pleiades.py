#
# This file is part of pleiades_accession
# by Tom Elliott for the Institute for the Study of the Ancient World
# (c) Copyright 2025 by New York University
# Licensed under the AGPL-3.0; see LICENSE.txt file.
#

"""
Manage Pleiades data and queries
"""
import logging
from pathlib import Path
from pleiades_local.filesystem import PleiadesFilesystem


class Pleiades:
    """
    Manage Pleiades data and queries
    """

    def __init__(self, root_path: Path):
        """Initialize the Pleiades filesystem manager, which will generate a catalog of
        JSON files if needed."""
        logger = logging.getLogger(f"{__name__}:Pleiades.__init__")
        self.fs = PleiadesFilesystem(root_path)
        logger.info(f"Loaded {len(self.fs):,} Pleiades place resources.")

    def __len__(self):
        """Return the number of places in the Pleiades data set"""
        return len(self.fs)
