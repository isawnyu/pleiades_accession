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
from datetime import datetime
import json
import logging
from pathlib import Path
from pprint import pformat
import pyperclip
import re
import shutil


logger = logging.getLogger(__name__)
rx_compound_cmd = re.compile(r"^(j|m|l)(\d+)$")
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
    [
        "-o",
        "--outputpath",
        "./data/output/",
        "path to output directory (default: ./data/)",
        False,
    ],
    [
        "-c",
        "--continue",
        False,
        "continue from last session, loading data from previous run's output files",
        False,
    ],
    [
        "-s",
        "--skipreciprocal",
        False,
        "skip reciprocal link matches (for faster review)",
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
    outpath = Path(kwargs["outputpath"]).expanduser().resolve()
    outpath.mkdir(parents=True, exist_ok=True)
    accession_ids = set()
    accession_path = outpath / "to_accession.txt"
    followup_ids = set()
    followup_path = outpath / "follow_up.txt"
    joins = dict()
    join_path = outpath / "to_join.txt"
    # backup previous session
    last_modified = datetime.min
    if (accession_path).exists():
        last_modified = datetime.fromtimestamp(accession_path.stat().st_mtime)
    if (followup_path).exists():
        last_modified = max(
            last_modified, datetime.fromtimestamp(followup_path.stat().st_mtime)
        )
    if last_modified > datetime.min:
        previous_path = outpath / "previous" / last_modified.isoformat()
        previous_path.mkdir(parents=True, exist_ok=True)
        if (accession_path).exists():
            shutil.copy(accession_path, previous_path / accession_path.name)
        if (followup_path).exists():
            shutil.copy(followup_path, previous_path / followup_path.name)

    if not kwargs["continue"]:
        print(
            "Starting new review session. Previous output files (if any) will be overwritten. "
            "Use --continue (-c) to resume from previous session."
        )
        s = input("Proceed? (y/n) ")
        if s.lower().strip() not in {"y", "yes"}:
            print("Exiting.")
            exit()
        accession_path.unlink(missing_ok=True)
        followup_path.unlink(missing_ok=True)
    else:
        print(
            "Continuing from previous session. Previous output files (if any) will be appended to."
        )
        if (accession_path).exists():
            with open(accession_path, "r", encoding="utf-8") as f:
                for line in f:
                    accession_ids.add(line.strip())
            del f
            print(
                f"Loaded {len(accession_ids):,} previously accessioned candidates from {accession_path}."
            )
        else:
            print(
                f"No previous accession file found at {accession_path}; starting fresh."
            )
        if (followup_path).exists():
            with open(followup_path, "r", encoding="utf-8") as f:
                for line in f:
                    followup_ids.add(line.strip())
            del f
            print(
                f"Loaded {len(followup_ids):,} previously marked follow-up candidates from {followup_path}."
            )
        else:
            print(
                f"No previous follow-up file found at {followup_path}; starting fresh."
            )
        if (join_path).exists():
            with open(join_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        candidate_id, pid = line.strip().split(": ")
                    except ValueError as err:
                        err.add_note(
                            f"Error parsing line in {join_path}: '{line.strip()}'"
                        )
                        raise err
                    joins[candidate_id.strip()] = pid.strip()
            del f
            print(f"Loaded {len(joins):,} previously marked joins from {join_path}.")
        else:
            print(f"No previous join file found at {join_path}; starting fresh.")

    matchfile_path = Path(kwargs["matchfile"]).expanduser().resolve()
    with open(matchfile_path, "r", encoding="utf-8") as f:
        j = json.load(f)
    del f
    print(f"Loaded {len(j):,} candidates from {kwargs['matchfile']}")

    s = input("Proceed to review? (y/n) ")
    if s.lower().strip() not in {"y", "yes"}:
        print("Exiting.")
        exit()

    candidate_i = 0
    total = len(j)
    for candidate_id, v in j.items():
        candidate_i += 1
        if candidate_id in accession_ids:
            print(
                f"Skipping candidate {candidate_id} (already marked for accessioning)."
            )
            continue
        elif candidate_id in followup_ids:
            print(f"Skipping candidate {candidate_id} (already marked for follow-up).")
            continue
        elif candidate_id in joins.keys():
            print(f"Skipping candidate {candidate_id} (already marked to join).")
            continue
        c = v["candidate"]
        matches = v["matches"]
        if kwargs["skipreciprocal"] and len(matches) == 1:
            match = list(matches.values())[0]
            if "reciprocal link" in match.get("match_types", []):
                print(
                    f"Skipping candidate {candidate_id} due to reciprocal link match."
                )
                continue

        print("\n" * 2)
        print("=" * 80)
        print(f"Candidate {candidate_i} of {total} ({candidate_id})")
        names = sorted(c.get("name_strings", []))
        print(", ".join(names))
        print(candidate_id)
        place_types = sorted(c["properties"].get("place_types", []))
        place_types = ", ".join(place_types)
        if place_types:
            print(f"Place types: {place_types}")
        links = sorted(c.get("links", []))
        for link in links:
            print(f" - {link}")
        weights = [
            {"reciprocal link"},
            {"footprint", "exact name", "first-order link", "place type"},
            {"footprint", "fuzzy name", "first-order link", "place type"},
            {"exact name", "first-order link", "place type"},
            {"fuzzy name", "first-order link", "place type"},
            {"footprint", "exact name", "first-order link"},
            {"footprint", "fuzzy name", "first-order link"},
            {"exact name", "first-order link"},
            {"fuzzy name", "first-order link"},
            {"footprint", "exact name", "second-order link", "place type"},
            {"footprint", "fuzzy name", "second-order link", "place type"},
            {"footprint", "exact name", "second-order link"},
            {"footprint", "fuzzy name", "second-order link"},
            {"footprint", "first-order link", "place type"},
            {"first-order link"},
            {"footprint", "second-order link", "place type"},
            {"second-order link", "place type"},
            {"footprint", "exact name", "place type"},
            {"footprint", "fuzzy name", "place type"},
            {"footprint", "exact name"},
            {"footprint", "fuzzy name"},
            {"exact name", "place type"},
            {"fuzzy name", "place type"},
            {"footprint", "place type"},
            {"exact name"},
            {"fuzzy name"},
            {"footprint"},
        ]
        weighted_matches = sorted(
            [(m, weight(m, weights)) for m in matches.values()], key=lambda x: x[1]
        )
        print(f"\n{len(weighted_matches):,} matches found:")
        for i, weighted_match in enumerate(weighted_matches):
            if i >= 5:
                print(
                    f"... and {len(weighted_matches) - i} more matches (use command '(w)hole' to see all)."
                )
                break
            m, w = weighted_match
            place = m["place"]
            match_types = m.get("match_types", [])
            print("-" * 80)
            print(
                f"{i+1}. {place.get('title', 'NO TITLE')} ({place.get('pid', 'NO PID')})"
            )
            print(place["uri"])
            names = sorted(place.get("name_strings", []))
            print(", ".join(names) if names else "NO NAMES")
            place_types = sorted(place.get("place_types", []))
            place_types = ", ".join(place_types)
            if place_types:
                print(f"Place types: {place_types}")
            print(f"Match types: {', '.join(match_types) if match_types else 'NONE'}")
        while True:
            s = input("> ")
            s = s.lower().strip()
            if s in {"q", "quit", "exit"}:
                print("Exiting.")
                exit()
            if s in ["h", "help", "?"]:
                print("Enter:")
                print("  a, accession to mark candidate for accessioning")
                print("  c, candidate to copy candidate URI to clipboard")
                print(
                    "  centroid     to copy candidate centroid (lat, lon) to clipboard"
                )
                print("  f, followup  to mark candidate for follow-up")
                print("  jN           to join candidate to match N (e.g. j1, j2, ...)")
                print(
                    "  lN           to copy link N from candidate to clipboard (e.g. l1, l2, ...)"
                )
                print(
                    "  mN           to copy match N URI to clipboard (e.g. m1, m2, ...)"
                )
                print("  n, next      to move on to next candidate")
                print("  q, quit      to exit")
                continue
            elif s == {"w", "whole"}:
                for i, weighted_match in enumerate(weighted_matches):
                    m, w = weighted_match
                    place = m["place"]
                    match_types = m.get("match_types", [])
                    print("-" * 80)
                    print(
                        f"{i+1}. {place.get('title', 'NO TITLE')} ({place.get('pid', 'NO PID')})"
                    )
                    print(place["uri"])
                    print(
                        f"Match types: {', '.join(match_types) if match_types else 'NONE'}"
                    )
                    names = sorted(place.get("name_strings", []))
                    print(", ".join(names) if names else "NO NAMES")
                continue
            elif s in {"n", "next", "s", "skip"}:
                break
            elif s in {"a", "accession"}:
                accession_ids.add(candidate_id)
                print(f"Candidate {candidate_id} marked for accessioning.")
                with open(accession_path, "a", encoding="utf-8") as f:
                    f.write(f"{candidate_id}\n")
                del f
                continue
            elif s in {"f", "followup"}:
                followup_ids.add(candidate_id)
                print(f"Candidate {candidate_id} marked for follow-up.")
                with open(followup_path, "a", encoding="utf-8") as f:
                    f.write(f"{candidate_id}\n")
                del f
                continue
            elif s in {"c", "candidate"}:
                uri = candidate_id
                if uri.startswith("https://whgazetteer.org/api/db/?id="):
                    raw_id = uri.split("=", 1)[1]
                    uri = f"https://whgazetteer.org/places/{raw_id}/detail"
                pyperclip.copy(uri)
                print(f"Copied {uri} to clipboard.")
                continue
            elif s == "centroid":
                lat, lon = c.get("centroid_latlon", (None, None))
                if lat is not None and lon is not None:
                    pyperclip.copy(f"{lat}, {lon}")
                    print(f"Copied {lat}, {lon} to clipboard.")
                else:
                    print("No centroid available for this candidate.")
                continue
            elif len(s) > 1:
                m = rx_compound_cmd.match(s)
                if m:
                    cmd, val = m.groups()
                    idx = int(val) - 1
                    if not (0 <= idx < len(weighted_matches)):
                        print("Invalid match number.")
                        continue
                    match cmd:
                        case "j":
                            this_match, _ = weighted_matches[idx]
                            try:
                                joins[candidate_id]
                            except KeyError:
                                joins[candidate_id] = this_match["place"]["pid"]
                                with open(join_path, "a", encoding="utf-8") as f:
                                    f.write(
                                        f"{candidate_id}: {this_match['place']['pid']}\n"
                                    )
                                print(
                                    f"Marked candidate {candidate_id} to join {joins[candidate_id]}."
                                )
                            else:
                                print(
                                    f"ERROR: Candidate {candidate_id} is already marked to join a different Pleiades place {joins[candidate_id]}. No changes made."
                                )
                        case "m":
                            this_match, _ = weighted_matches[idx]
                            uri = this_match["place"].get("uri", "")
                            pyperclip.copy(uri)
                            print(f"Copied {uri} to clipboard.")
                        case "l":
                            try:
                                this_link = links[idx]
                            except IndexError:
                                print("Invalid link number.")
                                continue
                            pyperclip.copy(this_link)
                            print(f"Copied {this_link} to clipboard.")
                        case _:
                            print(f"Unrecognized command prefix '{cmd}' in '{s}'.")
                else:
                    print(f"Unrecognized command '{s}'.")
                continue


if __name__ == "__main__":
    main(
        **configure_commandline(
            OPTIONAL_ARGUMENTS, POSITIONAL_ARGUMENTS, DEFAULT_LOG_LEVEL
        )
    )
