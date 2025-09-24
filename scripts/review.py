#
# This file is part of pleiades_accession
# by Tom Elliott for the Institute for the Study of the Ancient World
# (c) Copyright 2025 by New York University
# Licensed under the AGPL-3.0; see LICENSE.txt file.
#

"""
Review matches
"""

from airtight.cli import configure_commandline
import json
import logging
import pyperclip

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
    ["matchfile", str, "path to match JSON file"],
]


def weight(match, weights):
    """
    assign a weight to a match based on its match types and the given weights list
    """
    match_types = set(match.get("match_types", []))
    for i, weight_set in enumerate(weights):
        if weight_set.issubset(match_types):
            return i
    return len(weights)


def main(**kwargs):
    """
    main function
    """
    # logger = logging.getLogger(sys._getframe().f_code.co_name)
    with open(kwargs["matchfile"], "r", encoding="utf-8") as f:
        j = json.load(f)
    del f
    for candidate_id, v in j.items():
        c = v["candidate"]
        matches = v["matches"]
        print("=" * 80)
        names = sorted(c.get("name_strings", []))

        print(", ".join(names))
        print(candidate_id)
        weights = [
            {"footprint", "exact name", "first-order link"},
            {"footprint", "fuzzy name", "first-order link"},
            {"footprint", "exact name", "second-order link"},
            {"footprint", "fuzzy name", "second-order link"},
            {"footprint", "exact name"},
            {"footprint", "fuzzy name"},
            {"footprint", "first-order link"},
            {"first-order link"},
            {"footprint"},
            {"exact name"},
            {"fuzzy name"},
        ]
        weighted_matches = sorted(
            [(m, weight(m, weights)) for m in matches.values()], key=lambda x: x[1]
        )
        print(f"{len(weighted_matches):,} matches found:")
        for i, weighted_match in enumerate(weighted_matches):
            m, w = weighted_match
            place = m["place"]
            match_types = m.get("match_types", [])
            print("-" * 80)
            print(
                f"{i+1}. {place.get('title', 'NO TITLE')} ({place.get('pid', 'NO PID')})"
            )
            print(place["uri"])
            print(f"Match types: {', '.join(match_types) if match_types else 'NONE'}")
            names = sorted(place.get("name_strings", []))
            print(", ".join(names) if names else "NO NAMES")
            desc = place.get("description", "")
            if desc:
                if len(desc) > 200:
                    desc = desc[:197] + "..."
                print(desc)
            location = place.get("location", {})
            if location:
                lat = location.get("lat")
                lon = location.get("lon")
                if lat and lon:
                    print(f"Location: {lat}, {lon}")
            links = place.get("links", [])
            if links:
                print("Links:")
                for link in links:
                    print(f"  - {link}")
        while True:
            s = input("> ")
            s = s.lower().strip()
            if s in {"q", "quit", "exit"}:
                print("Exiting.")
                exit()
            if s == "c":
                id = candidate_id.split("=")[-1]
                uri = f"https://whgazetteer.org/places/{id}/detail"
                pyperclip.copy(uri)
                print(f"Copied {uri} to clipboard.")
            elif s.startswith("m"):
                val = "".join(list(s)[1:])
                if val.isdigit():
                    idx = int(val) - 1
                    if 0 <= idx < len(weighted_matches):
                        m, _ = weighted_matches[idx]
                        uri = m["place"].get("uri", "")
                        if uri:
                            pyperclip.copy(uri)
                            print(f"Copied {uri} to clipboard.")
                        else:
                            print("No URI to copy.")
                    else:
                        print("Invalid match number.")
            elif s == "":
                break


if __name__ == "__main__":
    main(
        **configure_commandline(
            OPTIONAL_ARGUMENTS, POSITIONAL_ARGUMENTS, DEFAULT_LOG_LEVEL
        )
    )
