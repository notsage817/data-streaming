from pyflink.datastream import StreamExecutionEnvironment
from pyflink.table import StreamTableEnvironment, EnvironmentSettings

def create_events_source_kafka(t_env):
    table_name = "events"
    source_ddl = f"""
        CREATE TABLE {table_name} (
            PULocationID INT,
            DOLocationID INT,
            passenger_count DOUBLE,
            trip_distance DOUBLE,
            total_amount DOUBLE,
            tip_amount DOUBLE,
            lpep_pickup_datetime STRING,
            lpep_dropoff_datetime STRING
        ) WITH (
            'connector' = 'kafka',
            'properties.bootstrap.servers' = 'redpanda:29092',
            'topic' = 'green-trips',
            'scan.startup.mode' = 'latest-offset',
            'properties.auto.offset.reset' = 'latest',
            'format' = 'json',
            'json.ignore-parse-errors' = 'true'
        );
        """
    t_env.execute_sql(source_ddl)
    return table_name

def create_processed_events_sink_postgres(t_env):
    table_name = "processed_rides"
    sink_ddl = f"""
        CREATE TABLE {table_name} (
            PULocationID INT,
            DOLocationID INT,
            passenger_count INT,
            trip_distance DOUBLE,
            total_amount DOUBLE,
            tip_amount DOUBLE,
            pickup_datetime TIMESTAMP,
            dropoff_datetime TIMESTAMP
        ) WITH (
            'connector' = 'jdbc',
            'url' = 'jdbc:postgresql://postgres:5432/postgres',
            'table-name' = '{table_name}',
            'username' = 'postgres',
            'password' = 'postgres'
        );
        """
    t_env.execute_sql(sink_ddl)
    return table_name

def log_processing():
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(1)
    env.enable_checkpointing(10000)  # Checkpoint every 10 seconds

    settings = EnvironmentSettings.new_instance().in_streaming_mode().build()
    t_env = StreamTableEnvironment.create(env, environment_settings=settings)

    source_table = create_events_source_kafka(t_env)
    postgres_sink = create_processed_events_sink_postgres(t_env)

    t_env.execute_sql(
        f"""
        INSERT INTO {postgres_sink}
        SELECT PULocationID, 
            DOLocationID, 
            CAST(passenger_count AS INT) AS passenger_count, 
            trip_distance, 
            total_amount, 
            tip_amount, 
            TRY_CAST(TO_TIMESTAMP(lpep_pickup_datetime, 'yyyy-MM-dd''T''HH:mm:ss') AS TIMESTAMP(6)) AS pickup_datetime,
            TRY_CAST(TO_TIMESTAMP(lpep_dropoff_datetime, 'yyyy-MM-dd''T''HH:mm:ss') AS TIMESTAMP(6)) AS dropoff_datetime
        FROM {source_table}
        """
    ).wait()

if __name__ == "__main__":
    log_processing()