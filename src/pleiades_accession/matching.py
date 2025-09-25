#
# This file is part of pleiades_accession
# by Tom Elliott for the Institute for the Study of the Ancient World
# (c) Copyright 2025 by New York University
# Licensed under the AGPL-3.0; see LICENSE.txt file.
#

"""
Define matcher class for deconfliting candidate places against Pleiades
"""
import functools
import logging
from math import cos, radians
from pprint import pformat
from rapidfuzz import process, fuzz, distance, utils


@functools.lru_cache(maxsize=None)
def meters_to_degrees(m, origin_latitude):
    """
    Convert meters to degrees latitude/longitude at the specified origin latitude
    https://gis.stackexchange.com/questions/2951/algorithm-for-offsetting-latitude-longitude-by-some-amount-of-meters
    """
    lat = m / 111111
    lon = m / (111111 * cos(radians(origin_latitude)))
    return (lat + lon) / 2


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

    def match(self, spatial_buffer=10.0) -> dict:
        """Perform matching of candidate places against Pleiades places."""
        # spatial_buffer is in km
        name_choices = list(self.pleiades.names_index.keys())

        logger = logging.getLogger(f"{__name__}:Matcher.match")
        match_vote_totals = dict()
        for cid, candidate in self.candidates.features.items():
            matched = set()
            match_votes = dict()
            # spatial overlap/intersection/containment
            candidate_geom = candidate.geometry
            lat = candidate_geom.centroid.y
            buffered_geom = candidate_geom.buffer(
                meters_to_degrees(spatial_buffer * 1000, lat)
            )
            spatial_matched_pids = self.pleiades.spatial_query(buffered_geom)
            for pid in spatial_matched_pids:
                match_votes[pid] = {
                    "footprint",
                }
            matched.update(spatial_matched_pids)

            # failing that, spatial proximity
            if not spatial_matched_pids:
                spatial_matched_pids = self.pleiades.spatial_nearest(candidate_geom)
                for pid in spatial_matched_pids:
                    try:
                        match_votes[pid]
                    except KeyError:
                        match_votes[pid] = set()
                    match_votes[pid].add("nearest")
                matched.update(spatial_matched_pids)

            # name string matches within spatial matches
            name_matched_pids = set()
            for name_string in candidate.name_strings:
                name_matched_pids.update(
                    self.pleiades.names_index.get(name_string, set())
                )
            for pid in name_matched_pids:
                try:
                    match_votes[pid]
                except KeyError:
                    match_votes[pid] = set()
                match_votes[pid].add("exact name")
            if spatial_matched_pids:
                matched.update(spatial_matched_pids.intersection(name_matched_pids))
            else:
                matched.update(name_matched_pids)

            # near name string matches within spatial matches
            name_fuzzy_matched_pids = set()
            for name_string in candidate.name_strings:
                fuzzy_matches = process.extract(
                    name_string,
                    name_choices,
                    scorer=fuzz.WRatio,
                    score_cutoff=90,
                    limit=5,
                    processor=utils.default_process,
                )
                for matched_name, score, _ in fuzzy_matches:
                    name_fuzzy_matched_pids.update(
                        self.pleiades.names_index[matched_name]
                    )
            if name_fuzzy_matched_pids:
                if spatial_matched_pids:
                    name_fuzzy_matched_pids = spatial_matched_pids.intersection(
                        name_fuzzy_matched_pids
                    )
                for pid in name_fuzzy_matched_pids:
                    if pid in matched:
                        try:
                            match_votes[pid]
                        except KeyError:
                            match_votes[pid] = set()
                        match_votes[pid].add("fuzzy name")
                matched.update(name_fuzzy_matched_pids)

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
            non_plinks = {link for link in links if "pleiades.stoa.org" not in link}
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

        return match_vote_totals
