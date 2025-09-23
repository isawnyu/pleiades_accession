#
# This file is part of pleiades_accession
# by Tom Elliott for the Institute for the Study of the Ancient World
# (c) Copyright 2025 by New York University
# Licensed under the AGPL-3.0; see LICENSE.txt file.
#

"""
Define matcher class for deconfliting candidate places against Pleiades
"""
import logging


class Matcher:
    """
    Manage matching candidate places against Pleiades places
    """

    def __init__(self, pleiades, candidates):
        """Initialize the Matcher."""
        self.pleiades = pleiades
        self.candidates = candidates
        self.matches = dict()
        self.unmatched = dict()

    def match(self):
        """Perform matching of candidate places against Pleiades places."""
        logger = logging.getLogger(f"{__name__}:Matcher.match")
        for cid, candidate in self.candidates.features.items():
            match_votes = dict()
            candidate_geom = candidate.geometry
            spatial_matched_pids = self.pleiades.spatial_query(candidate_geom)
            for pid in spatial_matched_pids:
                match_votes[pid] = {
                    "footprint",
                }
            if not spatial_matched_pids:
                spatial_matched_pids = self.pleiades.spatial_nearest(candidate_geom)
                for pid in spatial_matched_pids:
                    try:
                        match_votes[pid]
                    except KeyError:
                        match_votes[pid] = set()
                    match_votes[pid].add("nearest")
                    # stopped here
            name_matched_pids = set()
            for name_string in candidate.name_strings:
                name_matched_pids.update(
                    self.pleiades.names_index.get(name_string, set())
                )
            matched = spatial_matched_pids.intersection(name_matched_pids)
            if matched:
                self.matches[cid] = matched
                logger.info(f"Candidate {cid} matched Pleiades IDs: {matched}")
            else:
                self.unmatched[cid] = candidate
                logger.info(f"Candidate {cid} had no matches")
