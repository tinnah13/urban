# Cleaning Log

## Raw input
- 7,667,792 trips
- 265 taxi zones
-263 spatial polygons

## Cleaning decisions and rationale

### Duplicates 
Removed 0 rows. The TLC dataset did not include exact-duplicate trip records in this monthly snapshot.

### Missing critical fields
Remove 0 rows. All rows had valid pickup and dropoff timestamps and locatio IDs. This is unusual and suggests the TLC filters these before publishing.

### Tempral anomalies
Removed 6.299 rows where trip_duration was <= 0 minutes (clock skew or meter errors) or > 24 hours (likely forgetten meters left running).

### Distance anomalies
Removed 48,832 rows with trip_distance == 0 (pickup and dropoff same location often a no-show) or > 100 miles (GPS erroes, not realistic for a yellow-taxi trip within NYC) . 

### Fare anomalies
Removed 5,704 rows where fare_amount was negative, above $500, or where total_amount < fare_amount (inconsistent metering). 

### passenger anomalies
Removed 1 row where passenger_count exceed 8 (physically impossible in a yellow cab).

### Final retention
7,606,956 / 7,667,792 = 99.2% retained.
