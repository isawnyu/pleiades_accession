#
# This file is part of pleiades_accession
# by Tom Elliott for the Institute for the Study of the Ancient World
# (c) Copyright 2025 by New York University
# Licensed under the AGPL-3.0; see LICENSE.txt file.
#

"""
Script to convert a pleiades_acccession joins text file to a JSON file for use by the batch_add_references.py script in pleiades3-buildout
"""

from airtight.cli import configure_commandline
import json
import logging
from pathlib import Path
from pprint import pformat
import pywikibot
from pywikibot.exceptions import IsRedirectPageError
import re
from urllib.parse import urlparse
from webiquette.webi import Webi

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
    [
        "-n",
        "--netlocs",
        "www.wikidata.org",
        "additional netlocs to recognize from links in LPF (comma-separated list)",
        False,
    ],
]
POSITIONAL_ARGUMENTS = [
    # each row is a list with 3 elements: name, type, help
    ["joinsfile", str, "path to joins text file"],
    ["lpffile", str, "path to LPF JSON file with additional data for referenced URIs"],
]
WEBI_HEADER = {
    "User-Agent": "pleiades_accession/0.1 (+https://pleiades.stoa.org)",
    "From": "pleiades.admin@nyu.edu",
}

known_netlocs = {
    "topostext.org": {
        "bibliographic_uri": "https://www.zotero.org/groups/2533/items/MC9RGDVB",
        "formatted_citation": '<div class="csl-entry">Kiesling, Brady. <i>ToposText – a Reference Tool for Greek Civilization</i>. Version 2.0. Aikaterini Laskaridis Foundation, 2016. https://topostext.org/.</div>',
        "short_title": "ToposText",
        "type": "citesAsRelated",
    },
    "www.wikidata.org": {
        "bibliographic_uri": "https://www.zotero.org/groups/2533/items/BCQIKDKS",
        "formatted_citation": '<div class="csl-entry"><i>Wikidata: The Free Knowledge Base That Anyone Can Edit</i>. Wikimedia Foundation, 2014. https://www.wikidata.org/.</div>',
        "short_title": "Wikidata",
        "type": "citesAsRelated",
    },
}
apis = {}
webis = dict()
rx_wikidata_item = re.compile(r"^https?://www.wikidata.org/wiki/(Q[0-9]+)$")


def _get_wikidata_item(item_id) -> dict | None:
    """
    get wikidata item
    """
    try:
        apis["www.wikidata.org"]
    except KeyError:
        site = pywikibot.Site("wikidata", "wikidata")
        apis["www.wikidata.org"] = {
            "repo": site.data_repository(),
        }
    try:
        return pywikibot.ItemPage(apis["www.wikidata.org"]["repo"], item_id).get()
    except IsRedirectPageError as err:
        logger.error(f"Wikidata item {item_id} is a redirect: {err}. Skipping.")
        return None


def get_webi(netloc):
    """
    get or create webi for netloc
    """
    webi = webis.get(netloc)
    if webi is None:
        webi = Webi(netloc=netloc, headers=WEBI_HEADER, respect_robots_txt=False)
        webis[netloc] = webi
    return webi


def _get_title_from_www_wikidata_org(uri):
    """
    get title from wikidata item
    """
    m = rx_wikidata_item.match(uri)
    if not m:
        raise ValueError(f"Could not parse Wikidata item ID from {uri}")
    item_id = m.group(1)
    item_d = _get_wikidata_item(item_id)
    if item_d is None:
        return None
    title = item_d["labels"].get("en")
    if title is None:
        labels = {l for l in item_d["labels"].values()}
        if len(labels) == 1:
            title = labels.pop()
        for lang in ("la", "grc", "de", "fr", "it", "es", "el", "tr"):
            try:
                title = item_d["labels"][lang]
            except KeyError:
                pass
            else:
                break
    if title is not None:
        title = f"{title} ({item_id})"
    return title


def get_title_from_web(netloc, uri):
    """
    get title from web page at uri
    """
    title = globals()[f"_get_title_from_{netloc.replace('.', '_')}"](uri)
    # webi = get_webi(netloc)
    # if webi is None:
    #    return None

    return title


def main(**kwargs):
    """
    main function
    """
    # logger = logging.getLogger(sys._getframe().f_code.co_name)
    link_netlocs = {n.strip() for n in kwargs["netlocs"].split(",")}
    joins_path = Path(kwargs["joinsfile"]).expanduser().resolve()
    with open(joins_path, "r", encoding="utf-8") as infile:
        lines = infile.readlines()
    del infile
    lfp_path = Path(kwargs["lpffile"]).expanduser().resolve()
    with open(lfp_path, "r", encoding="utf-8") as infile:
        lpf = json.load(infile)
    del infile
    features = {f["@id"]: f for f in lpf["features"]}

    additions = dict()
    for line in lines:
        external_uri, pid = [p.strip() for p in line.split(": ")]
        logger.debug(f'"external_uri": "{external_uri}", "pid": "{pid}",')
        feature = features.get(external_uri)
        if feature is None:
            raise ValueError(f"feature {external_uri} not found in LPF file {lfp_path}")
        title = feature["properties"].get("title")
        if title is None:
            raise ValueError(
                f"title not found for feature {external_uri} in LPF file {lfp_path}"
            )
        parts = urlparse(external_uri)
        netloc = parts.netloc
        base_ref = known_netlocs.get(netloc)
        if base_ref is None:
            raise RuntimeError(
                f"netloc {netloc} from {external_uri} not found in known_netlocs; please update the script with bibliographic details for this base URI"
            )
        ref = dict(base_ref)
        ref["access_uri"] = external_uri
        ref["citation_detail"] = title.strip()
        additions[f"https://pleiades.stoa.org/places/{pid}"] = [
            ref,
        ]

        # from links
        for link in feature.get("links", []):
            if link["type"] != "closeMatch":
                continue
            link_uri = link["identifier"]
            parts = urlparse(link_uri)
            netloc = parts.netloc
            if netloc == "pleiades.stoa.org":
                continue
            if netloc not in link_netlocs:
                logger.info(
                    f"Encountered new netloc {netloc} from link in {external_uri} LPF. Not supported for addition via the --netloc command-line argument, so skipping."
                )
                continue
            base_ref = known_netlocs.get(netloc)
            if base_ref is None:
                if netloc in kwargs["netlocs"]:
                    logger.warning(
                        f"netloc {netloc} from {link} not found in known_netlocs; please update the script with bibliographic details for this base URI"
                    )
                continue
            title = get_title_from_web(netloc, link_uri)
            if title is None:
                logger.warning(
                    f"Could not retrieve title for {link_uri} from {netloc}; skipping."
                )
                continue
            ref = dict(base_ref)
            ref["access_uri"] = link_uri
            ref["citation_detail"] = title.strip()
            additions[f"https://pleiades.stoa.org/places/{pid}"].append(ref)

    print(json.dumps(additions, indent=2, ensure_ascii=False))
    logger.info(
        f"Processed {len(lines)} joins from {joins_path} using LPF data from {lfp_path}"
    )


if __name__ == "__main__":
    main(
        **configure_commandline(
            OPTIONAL_ARGUMENTS, POSITIONAL_ARGUMENTS, DEFAULT_LOG_LEVEL
        )
    )
