#
# This file is part of pleiades_accession
# by Tom Elliott for the Institute for the Study of the Ancient World
# (c) Copyright 2025 by New York University
# Licensed under the AGPL-3.0; see LICENSE.txt file.
#

"""
Functions for dealing with text
"""
from functools import lru_cache
import textnorm


@lru_cache(maxsize=5000)
def normalize_text(s: str) -> str:
    """
    Normalize text using textnorm
    """
    if not isinstance(s, str):
        raise TypeError("Input must be a string")
    return textnorm.normalize_space(textnorm.normalize_unicode(s))
