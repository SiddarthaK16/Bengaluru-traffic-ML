from src.data_collection.traffic_client import TrafficClient


client = TrafficClient()

data = client.get_traffic(
    latitude=12.9176,
    longitude=77.6233
)

print(data)