# Real-time streaming Pipeline
In this pipeline, there are event handler that push and read data per-event to kafka.

### Producer
The raw data contains numpy data types such as int32/int64/float64, which doesn't play nice with python libraries.

For each event we double check the data types before push it to kafka.

### Consumer
Read data from kafka
Raw data can be saved into lists before being transformed into dataframe

Moreover, load data into postgreSQL

Process data with Flink

### PostgreSQL
Add a volume to keep the table created

### Timezone issue

### NaN values issue