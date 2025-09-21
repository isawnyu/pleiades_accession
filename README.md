# Pleiades Accession

## Design

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

