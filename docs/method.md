# Method

## Definitions

- **Out of reach:** the nearest service of a category is farther than a threshold (default 5 km) in a straight line.
- **Essential services:** pharmacy, doctor or hospital, school, grocery, post office. Train stations are shown but not counted.
- **Residents:** modelled population, see below.

## Pipeline

1. **Buildings.** Overture buildings between 20 and 60,000 m2 (footprint area from the bounding box), excluding outbuilding
   classes, are counted per H3 cell at resolutions 8 and 9. Only bounding-box columns are read.
2. **Places.** Open Overture places mapped to service categories through the Overture taxonomy.
3. **Administrative areas.** Each resolution-8 cell is assigned to a province, region and locality by its centre. Overture has no
   province level for Valle d'Aosta, so cells there fall back to the region polygon.
4. **Pharmacies.** The Ministry of Health register (active entries, with coordinates when present, otherwise the
   building-weighted centre of the comune) is merged with Overture pharmacies. An Overture pharmacy farther than 300 m from every
   register entry is added. A place is called isolated only if neither source has a pharmacy nearby.
5. **Distances.** Great-circle distance from each cell centre to the nearest service, using a KD-tree on unit vectors. For pharmacies,
   the distance to each source alone is stored as well.
6. **Residents.** GHS-POP pixels (about 1 km) are spread over the resolution-9 cells they contain in proportion to building counts,
   then summed into resolution-8 cells. Allocating on resolution 9 matters: a resolution-8 cell centre does not fall in every pixel.
7. **Export.** Aggregates are resident-weighted and written as JSON and binary files for the web client.
8. **Candidate sites.** For a category and radius R, unserved cells are those whose nearest service is farther than R. Each
   unserved cell centre is a candidate; its gain is the unserved residents within R. A greedy maximum-coverage search picks the best
   site, marks its catchment served and repeats (lazy re-evaluation of marginal gains).
9. **Road validation.** The top 25 candidates per category are re-scored with a 15-minute car isoline from Amazon Location Service.
   The road gain is the unserved residents whose cell centre lies inside the isoline. Sites are ranked by road gain.
10. **Lakehouse check.** The cell table is loaded as an Apache Iceberg table partitioned by region. Athena recomputes the headline
    numbers, which must equal the DuckDB result. This checks that the two engines agree on the same table; it does not validate the
    population model.

## Validation performed

- Pharmacy sources compared: only about 50% of the register's pharmacies have an Overture pharmacy within 300 m, and 9% have none
  within 3 km. The register also contains entries with misplaced coordinates. This is why both are used.
- Road versus straight line: the median ratio of residents gained by road isoline to residents gained by the straight-line radius
  is 0.86 for pharmacies, 0.98 for doctors and 1.04 for schools.
- Population: the allocation places 57.9 million residents in Italy. City totals are plausible (Rome 2.77 M, Naples 0.92 M, Turin 0.90 M) but
  were not compared with ISTAT.

## Results at the default threshold

| Measure | Residents |
|---------|-----------|
| Total modelled | 57,906,237 |
| Far from at least one essential service | 4,513,824 (7.8%) |
| Far from three or more | 301,186 |
| Far from all five | 31,151 |
| Far from a pharmacy, both sources agree | 159,193 |
| Far from a pharmacy, register alone | 533,173 |
| Far from a pharmacy, Overture alone | 539,380 |

Sites: 25 new pharmacies would bring 31,529 residents (19.7% of the 159,905 unserved) within 15 minutes; 25 doctors or hospitals
194,990 (8.4%); 25 schools 284,712 (8.3%).

## Known limits

Straight-line distance understates travel in mountains. The road time shown on click is to the service nearest in a straight line.
Doctor and school layers are not validated against an official register. Overture and the register both have errors, so any single
locality should be read as a candidate to verify, not as a finding.
