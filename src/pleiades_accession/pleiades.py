#
# This file is part of pleiades_accession
# by Tom Elliott for the Institute for the Study of the Ancient World
# (c) Copyright 2025 by New York University
# Licensed under the AGPL-3.0; see LICENSE.txt file.
#

"""
Manage Pleiades data and queries
"""

from pathlib import Path
from pleiades_local.filesystem import PleiadesFilesystem


class Pleiades:
    """
    Manage Pleiades data and queries
    """

    def __init__(self, root_path: Path):
        self.fs = PleiadesFilesystem(root_path)

    def __len__(self):
        return len(self.fs)
