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

Your external candidates need to been in LPF format.

So, e.g. download a copy of this dataset to `~/scratch/`, unpack it and rename the JSON "lehning_periplus.json".


```
python scripts/match.py -c ~/scratch/lehning_periplus.json > ~/scratch/matches.json
```

To work through the possible matches thus generated and record decisions on their disposition, then run:

```
python scripts/review.py ~/scratch/matches.json
```

Note that adding `-h` to either of the scripts will give you help, including (for review.py) a list of possible commands, currently:

```
python scripts/review.py -h
usage: review.py [-h] [-l LOGLEVEL] [-v] [-w] [-o OUTPUTPATH] [-c] matchfile

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

