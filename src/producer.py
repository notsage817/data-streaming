from kafka import KafkaProducer
import pandas as pd
from models import json_serializer, ride_from_row
import dataclasses
import time

url = "https://d37ci6vzurychx.cloudfront.net/trip-data/green_tripdata_2025-10.parquet"
raw_df = pd.read_parquet(url)

server = "localhost:9092"
producer = KafkaProducer(
    bootstrap_servers=[server], 
    value_serializer=json_serializer
)

topic_name = "green-trips"
t0 = time.time()
for _, row in raw_df.iterrows():
    ride = ride_from_row(row)
    producer.send(topic_name, dataclasses.asdict(ride))
producer.flush()
t1 = time.time()
print(f"Time taken: {t1 - t0} seconds")