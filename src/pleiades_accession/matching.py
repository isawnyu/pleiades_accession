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
from pprint import pformat


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
        match_vote_totals = dict()
        for cid, candidate in self.candidates.features.items():
            match_votes = dict()
            # spatial overlap/intersection/containment
            candidate_geom = candidate.geometry
            spatial_matched_pids = self.pleiades.spatial_query(candidate_geom)
            for pid in list(spatial_matched_pids)[:10]:  # limit to first 10 matches
                match_votes[pid] = {
                    "footprint",
                }

            # failing that, spatial proximity
            if not spatial_matched_pids:
                spatial_matched_pids = self.pleiades.spatial_nearest(candidate_geom)
                for pid in spatial_matched_pids:
                    try:
                        match_votes[pid]
                    except KeyError:
                        match_votes[pid] = set()
                    match_votes[pid].add("nearest")

            # name string matches within spatial matches
            name_matched_pids = set()
            for name_string in candidate.name_strings:
                name_matched_pids.update(
                    self.pleiades.names_index.get(name_string, set())
                )
            matched = spatial_matched_pids.intersection(name_matched_pids)
            for pid in matched:
                try:
                    match_votes[pid]
                except KeyError:
                    match_votes[pid] = set()
                match_votes[pid].add("exact name")

            # near name string matches
            # TBD: implement fuzzy matching

            # link matches
            links = candidate.links
            plinks = {link for link in links if "pleiades.stoa.org" in link}
            for puri in plinks:
                pid = [p for p in puri.split("/") if p][-1]
                try:
                    match_votes[pid]
                except KeyError:
                    match_votes[pid] = set()
                match_votes[pid].add("first-order link")
                matched.add(pid)

            # second-order link matches
            non_plinks = links.difference(plinks)
            for uri in non_plinks:
                pids = self.pleiades.get_pid_by_link(uri)
                if not pids:
                    continue
                for pid in pids:
                    try:
                        match_votes[pid]
                    except KeyError:
                        match_votes[pid] = set()
                    match_votes[pid].add("second-order link")
                    if pid in spatial_matched_pids:
                        matched.add(pid)

            match_vote_totals[cid] = match_votes

            # debugging report
            if matched:
                self.matches[cid] = matched
                logger.debug(f"Candidate {cid} matched Pleiades IDs: {matched}")
            else:
                self.unmatched[cid] = candidate
                logger.debug(f"Candidate {cid} had no matches")

        logger.debug(f"Match votes: {pformat(match_vote_totals, indent=4)}")
