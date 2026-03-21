from typing import Optional
import pandas as pd
import math
from dataclasses import dataclass
import json
from kafka import KafkaProducer
import dataclasses
from datetime import timezone
from zoneinfo import ZoneInfo

@dataclass
class Ride:
    PULocationID: int
    DOLocationID: int
    passenger_count:Optional[float]
    trip_distance: float
    tip_amount:float
    total_amount: float
    lpep_pickup_datetime: str #epoch milliseconds
    lpep_dropoff_datetime: str # epoch milliseconds

def ride_from_row(row):
    return Ride(
        PULocationID=row.PULocationID,
        DOLocationID=row.DOLocationID,
        passenger_count=None if math.isnan(row.passenger_count) else row.passenger_count,
        trip_distance=row.trip_distance,
        total_amount=abs(row.total_amount),
        tip_amount=row.tip_amount,
        lpep_pickup_datetime= row.lpep_pickup_datetime.isoformat(timespec='seconds'),
        lpep_dropoff_datetime= row.lpep_dropoff_datetime.isoformat(timespec='seconds')
    )

def numpy_encoder(obj):
    if hasattr(obj, 'item'): # This safely catches numpy int32, int64, float64, etc.
        return obj.item()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

def json_serializer(data):
    return json.dumps(data, default=numpy_encoder).encode("utf-8")

def json_deserializer(data):
    json_str = data.decode("utf-8")
    ride_dict = json.loads(json_str)
    return Ride(**ride_dict)