# Pleiades Accession

Scripts to try to find possible matches between an external candidate dataset and existing Pleiades data and
to provide functions for facilitating evaluation of same and recording of decisions made about accepting or
rejecting them.

## Install

My .envrc file looks like:

```
layout pyenv 3.13.7
export PLEIADES_DATASET_PATH="~/Documents/files/P/pleiades.datasets/data/json/"
export PLEIADES_NAMES_INDEX_PATH="~/Documents/files/P/pleiades.datasets/data/indexes/name_index.json"
```

Clone pleiades.datasets from https://github.com/isawnyu/pleiades.datasets to your local drive and adjust accordingly.

Then:

```
pip install -U -e .
```

## Operation

Your external candidates need to be in LPF format. Then you use `scripts/match.py` to generate all the possible matches and their weights:

```
python scripts/match.py -h
usage: match.py [-h] [-l LOGLEVEL] [-v] [-w] [-p PLEIADESPATH] [-n NAMESINDEXPATH]
                -c CANDIDATESPATH

Matching script

options:
  -h, --help            show this help message and exit
  -l, --loglevel LOGLEVEL
                        desired logging level (case-insensitive string: DEBUG, INFO,
                        WARNING, or ERROR (default: NOTSET)
  -v, --verbose         verbose output (logging level == INFO) (default: True)
  -w, --veryverbose     very verbose output (logging level == DEBUG) (default: False)
  -p, --pleiadespath PLEIADESPATH
                        path to Pleiades dataset directory (default:
                        /Users/paregorios/Documents/files/P/pleiades.datasets/data/json)
  -n, --namesindexpath NAMESINDEXPATH
                        path to Pleiades names index file (if not in dataset directory)
                        (default: /Users/paregorios/Documents/files/P/pleiades.datasets/
                        data/indexes/name_index.json)
  -c, --candidatespath CANDIDATESPATH
                        path to candidate places LPF GeoJSON file (default: )
```

For example:

```

To work through the possible matches thus generated and record decisions on their disposition, then run `scripts/review.py`:

```
python scripts/review.py -h 
usage: review.py [-h] [-l LOGLEVEL] [-v] [-w] [-o OUTPUTPATH] [-c] [-s] matchfile

Review matches

positional arguments:
  matchfile             path to match JSON file

options:
  -h, --help            show this help message and exit
  -l, --loglevel LOGLEVEL
                        desired logging level (case-insensitive string: DEBUG, INFO,
                        WARNING, or ERROR (default: NOTSET)
  -v, --verbose         verbose output (logging level == INFO) (default: False)
  -w, --veryverbose     very verbose output (logging level == DEBUG) (default: False)
  -o, --outputpath OUTPUTPATH
                        path to output directory (default: ./data/) (default:
                        ./data/output/)
  -c, --continue        continue from last session, loading data from previous run's
                        output files (default: False)
  -s, --skipreciprocal  skip reciprocal link matches (for faster review) (default:
                        False)

```

So like this to continue a previous session:

```
python scripts/review.py -c -s -o ../pleiades_topostext/data/2025-09-29/ ../pleiades_topostext/data/2025-09-29/matches.json 
```

## Design (old)

- Read Pleiades dataset (maybe this should be a separate package)
    - if spatial index and bounding box caches are new as the spatial dataset, then just use cache; otherwise:
        - for each place
            - has > 0 locations?
            - buffer each location by its horizontal accuracy
            - create bounding box around all location buffers
            - store bounding box in cache
            - append pid to pid list
            - insert bounding box into spatial index (queries will return the index number into the pid list)
        - store spatial index to cache

- Read data from LPF JSON file

