# data-streaming

A real-time streaming analytics pipeline that processes NYC Green Taxi trip data using Apache Kafka (Redpanda), Apache Flink (PyFlink), and PostgreSQL — all containerized with Docker Compose.

---

## Architecture

```
NYC Taxi Data (Parquet)
        │
        ▼
   src/producer.py
        │  (JSON events)
        ▼
  Kafka / Redpanda
  topic: green-trips
        │
        ├──────────────────────────────────────────────┐
        ▼                                              ▼
  pass_thru_job.py                      tumble / session jobs
  (raw ingest)                          (windowed aggregations)
        │                                              │
        ▼                                              ▼
   processed_rides                   processed_rides_tumble_5min
   (PostgreSQL)                      processed_tips_tumble_1hr
                                     processed_rides_ss_5min
                                     (PostgreSQL)
```

---

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- Python 3.12 (managed via `.python-version`)
- [`uv`](https://github.com/astral-sh/uv) — fast Python package manager

---

## Project Structure

```
data-streaming/
├── src/
│   ├── job/                        # PyFlink streaming jobs
│   │   ├── pass_thru_job.py        # Raw pass-through to PostgreSQL
│   │   ├── tumble_5min_num_trips.py
│   │   ├── tumble_1h_tip_amt_job.py
│   │   └── session_5min_num_trips.py
│   ├── models.py                   # Ride dataclass + JSON serializer
│   ├── producer.py                 # Kafka producer script
│   ├── producer.ipynb              # Interactive producer notebook
│   └── consumer.ipynb              # Interactive consumer notebook
├── docker-compose.yml              # Redpanda, PostgreSQL, Flink cluster
├── Dockerfile.flink                # Custom PyFlink image
├── flink-config.yaml               # Flink memory + network config
├── pyproject.toml                  # Main Python dependencies
└── pyproject.flink.toml            # Flink-specific dependencies
```

---

## Getting Started

### 1. Start the stack

```bash
docker compose up -d
```

This starts:
| Service | Port | Description |
|---|---|---|
| Redpanda (Kafka) | `9092` | Message broker |
| Redpanda Proxy | `8082` | HTTP proxy |
| PostgreSQL | `5432` | Sink database |
| Flink JobManager | `8081` | Web UI + job submission |
| Flink TaskManager | — | Job execution (15 task slots) |

### 2. Install Python dependencies

```bash
uv sync
```

### 3. Produce events

Run the producer to fetch the NYC Green Taxi parquet file and stream events into Kafka:

```bash
uv run src/producer.py
```

This fetches `green_tripdata_2025-10.parquet` from the NYC TLC S3 bucket and publishes each row as a JSON event to the `green-trips` Kafka topic.

### 4. Submit a Flink job

From the Flink JobManager container, submit any job with `flink run`:

```bash
docker compose exec jobmanager flink run \
  --python /src/job/pass_thru_job.py
```

Or use the Flink Web UI at [http://localhost:8081](http://localhost:8081).

---

## Flink Jobs

### `pass_thru_job.py` — Raw Pass-Through

Reads raw events from Kafka and writes them to PostgreSQL with minimal transformation.

- **Source:** `green-trips` Kafka topic
- **Transform:** Parses ISO datetime strings to `TIMESTAMP`, casts `passenger_count` from `DOUBLE` to `INT`
- **Sink:** `processed_rides` table
- **Parallelism:** 1 | **Checkpoint interval:** 10s

---

### `tumble_5min_num_trips.py` — 5-Minute Tumbling Window

Aggregates trip count and total revenue per pickup location in fixed 5-minute windows.

- **Windowing:** `TUMBLE(pickup_datetime, INTERVAL '5' MINUTE)`
- **Group by:** `PULocationID`
- **Aggregations:** `COUNT(*) AS num_trips`, `SUM(total_amount) AS total_revenue`
- **Sink:** `processed_rides_tumble_5min` — primary key `(window_start, PULocationID)`
- **Parallelism:** 3 | **Checkpoint interval:** 10s

---

### `tumble_1h_tip_amt_job.py` — 1-Hour Tumbling Window

Aggregates global tip statistics across all locations in fixed 1-hour windows.

- **Windowing:** `TUMBLE(pickup_datetime, INTERVAL '1' HOUR)`
- **Aggregations:** `COUNT(*) AS num_trips`, `SUM(tip_amount) AS total_tips`
- **Sink:** `processed_tips_tumble_1hr` — primary key `(window_start)`
- **Parallelism:** 3 | **Checkpoint interval:** 10s

---

### `session_5min_num_trips.py` — 5-Minute Session Window

Groups trips per pickup location into activity sessions, closing a session after 5 minutes of inactivity.

- **Windowing:** `SESSION(pickup_datetime, INTERVAL '5' MINUTE)`
- **Group by:** `PULocationID`
- **Aggregations:** `COUNT(*) AS num_trips`
- **Sink:** `processed_rides_ss_5min` — primary key `(window_start, window_end, PULocationID)`
- **Parallelism:** 1 | **Checkpoint interval:** 10s

---

## Data Source

NYC TLC [Green Taxi Trip Records](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) — October 2025 parquet file.

Fields used per event:

| Field | Description |
|---|---|
| `PULocationID` | Pickup taxi zone |
| `DOLocationID` | Dropoff taxi zone |
| `passenger_count` | Number of passengers |
| `trip_distance` | Trip distance (miles) |
| `tip_amount` | Tip amount ($) |
| `total_amount` | Total fare ($) |
| `lpep_pickup_datetime` | Pickup timestamp |
| `lpep_dropoff_datetime` | Dropoff timestamp |

---

## Notes

### Data type conversion
The raw parquet data contains numpy types (`int32`, `int64`, `float64`) that are not directly JSON-serializable. `src/models.py` includes a custom encoder that converts these before publishing to Kafka.

### NaN values
Some rows have `NaN` for `passenger_count`. These are handled in `ride_from_row()` by defaulting to `0`.

### Timezone
All data originates from New York City. Timestamps are stored as-is without timezone conversion — keep this in mind when querying across daylight saving transitions.

---

## Thoughts

This is a solid project for learning the core concepts of stream processing. A few observations:

**What's well done:**
- Using three different windowing strategies (tumbling 5min, tumbling 1hr, session) on the same source topic is a great way to compare their behaviors side by side.
- Redpanda as a Kafka drop-in is a smart choice for local dev — it's faster to start and lighter on resources than a full Kafka+Zookeeper setup.
- The custom numpy JSON encoder in `models.py` is a small but important detail that prevents a whole class of silent serialization bugs.

**Things worth considering as the project grows:**
- The producer replays a static parquet file, which means event timestamps are in the past. Flink's watermarking will advance quickly and late-arrival windows may close before you expect. Replaying with a simulated clock (or using processing time) could make development easier.
- Each job defines its own Kafka source and PostgreSQL sink independently. As you add more jobs, a shared connector config (e.g., a `connectors.py` helper) would reduce duplication and make credential management simpler.
- Session windows are inherently harder to scale than tumbling windows because state per key grows unbounded until the session closes. The current parallelism of 1 for the session job is the safe call — worth keeping an eye on if data volume increases.
- Adding a schema registry (Redpanda has one built in) would make the JSON contract between producer and Flink jobs explicit and catch breaking changes early.
