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
from os import environ
from pathlib import Path
from pprint import pformat, pprint
import pywikibot
from pywikibot.exceptions import IsRedirectPageError
import re
from requests.exceptions import HTTPError
from urllib.parse import urlparse
from validators import url as valid_url
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
    "en.wikipedia.org": {
        "bibliographic_uri": "https://www.zotero.org/groups/2533/items/CI6F6W7W",
        "formatted_citation": '<div class="csl-entry"><i>Wikipedia: The Free Encyclopedia That Anyone Can Edit</i>. Wikimedia Foundation, 2001-. https://en.wikipedia.org.</div>',
        "short_title": "Wikipedia (English)",
        "type": "seeFurther",
    },
    "www.geonames.org": {
        "bibliographic_uri": "https://www.zotero.org/groups/2533/items/IIFE4W6M",
        "formatted_citation": '<div class="csl-entry">Marc Wick, and Christophe Boutreux. <i>GeoNames</i>, 2005-. https://www.geonames.org/.</div>',
        "short_title": "GeoNames",
        "type": "citesAsRelated",
    },
    "topostext.org": {
        "bibliographic_uri": "https://www.zotero.org/groups/2533/items/MC9RGDVB",
        "formatted_citation": '<div class="csl-entry">Kiesling, Brady. <i>ToposText – a Reference Tool for Greek Civilization</i>. Version 2.0. Aikaterini Laskaridis Foundation, 2016-. https://topostext.org/.</div>',
        "short_title": "ToposText",
        "type": "citesAsRelated",
    },
    "vocab.getty.edu": {
        # assumption is we are using the TGN
        "bibliographic_uri": "https://www.zotero.org/groups/2533/items/ZLJQ5AZJ",
        "formatted_citation": '<div class="csl-entry"><i>Getty Thesaurus of Geographic Names® Online</i>, n.d. https://www.getty.edu/research/tools/vocabularies/tgn/.</div>',
        "short_title": "TGN",
        "type": "citesAsRelated",
    },
    "whgazetteer.org": {
        "bibliographic_uri": "https://www.zotero.org/groups/2533/items/RHX229R6",
        "formatted_citation": '<div class="csl-entry">Mostern, Ruth, Alexandra Straub, Stephen Gadd, Karl Grossner, and David Ruvolo, eds. <i>World Historical Gazetteer: Linking Knowledge about the Past via Place</i>. Pittsburgh, PA: The World History Center at University of Pittsburgh, 2017-. http://whgazetteer.org/.</div>',
        "short_title": "WHG",
        "type": "citesAsRelated",
    },
    "www.wikidata.org": {
        "bibliographic_uri": "https://www.zotero.org/groups/2533/items/BCQIKDKS",
        "formatted_citation": '<div class="csl-entry"><i>Wikidata: The Free Knowledge Base That Anyone Can Edit</i>. Wikimedia Foundation, 2014-. https://www.wikidata.org/.</div>',
        "short_title": "Wikidata",
        "type": "citesAsRelated",
    },
}
apis = {}
webis = dict()
rx_geonames_id = re.compile(r"^https?://(www\.)?geonames\.org/([0-9]+)(/.*)?$")
rx_tgn_id = re.compile(r"^https?://vocab\.getty\.edu/tgn/([0-9]+)$")
rx_wikidata_item = re.compile(r"^https?://www.wikidata.org/wiki/(Q[0-9]+)$")
rx_whg_alias_netloc = re.compile(r"^([^\s]+):(.+)$")


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


def _get_title_from_en_wikipedia_org(uri):
    """
    get title from wikipedia page
    """
    parts = urlparse(uri)
    title = parts.path.split("/wiki/")[-1].replace("_", " ")
    return title


def _get_title_from_www_geonames_org(uri):
    """
    get title from geonames page
    """
    m = rx_geonames_id.match(uri)
    if not m:
        logger.error(f"Could not parse GeoNames ID from {uri}")
        return None
    geoname_id = m.group(2)
    webi = get_webi("www.geonames.org")
    base_url = f"http://api.geonames.org/"
    endpoint = "getJSON"
    params = {
        "username": environ.get("GEONAMES_API_USERNAME"),
        "geonameId": geoname_id,
    }
    try:
        r = webi.get(base_url + endpoint, params=params)
    except HTTPError as err:
        logger.error(f"GeoNames API request for ID {geoname_id} failed: {err}")
        return None
    if r.status_code != 200:
        logger.error(
            f"GeoNames API request for ID {geoname_id} failed with status code {r.status_code}: {r.text}"
        )
        return None
    title = r.json().get("toponymName")
    return title


def _get_title_from_vocab_getty_edu(uri):
    """
    get title from TGN page
    """
    m = rx_tgn_id.match(uri)
    if not m:
        logger.error(f"Could not parse TGN ID from {uri}")
        return None
    tgn_id = m.group(1)
    webi = get_webi("vocab.getty.edu")
    try:
        r = webi.get(f"http://vocab.getty.edu/tgn/{tgn_id}.json")
    except HTTPError as err:
        logger.error(f"TGN request for ID {tgn_id} failed: {err}")
        return None
    if r.status_code != 200:
        logger.error(
            f"TGN request for ID {tgn_id} failed with status code {r.status_code}: {r.text}"
        )
        return None
    j = r.json()
    title = [node for node in j.get("identified_by") if node.get("type") == "Name"][0][
        "content"
    ].strip()
    return title


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
        if external_uri.startswith("https://whgazetteer.org/api/db/?id="):
            m = re.match(
                r"^https?://whgazetteer\.org/api/db/\?id=([0-9]+)$", external_uri
            )
            if not m:
                logger.error(f"Could not parse WHG ID from {external_uri}")
                continue
            whg_id = m.group(1)
            external_uri = f"http://whgazetteer.org/places/{whg_id}/detail"
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
            if not valid_url(link_uri):
                m = rx_whg_alias_netloc.match(link_uri)
                if m:
                    netloc = m.group(1)
                    identifier = m.group(2)
                    if netloc == "gn":
                        link_uri = f"https://www.geonames.org/{identifier}"
                    elif netloc == "pl":
                        link_uri = f"https://pleiades.stoa.org/places/{identifier}"
                    elif netloc == "tgn":
                        link_uri = f"http://vocab.getty.edu/tgn/{identifier}"
                    elif netloc == "wd":
                        link_uri = f"https://www.wikidata.org/wiki/{identifier}"
                    elif netloc == "wp":
                        link_uri = f"https://en.wikipedia.org/wiki/{identifier}"
                    else:
                        logger.warning(
                            f"Unrecognized WHG netloc alias '{netloc}' in link '{pformat(link, indent=4)}' in {external_uri} LPF; skipping."
                        )
                        continue
            parts = urlparse(link_uri)
            netloc = parts.netloc
            if netloc == "pleiades.stoa.org":
                continue
            if netloc not in link_netlocs:
                logger.info(
                    f"Encountered new netloc '{netloc}' from link '{pformat(link, indent=4)}' in {external_uri} LPF. Not supported for addition via the --netloc command-line argument, so skipping."
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
