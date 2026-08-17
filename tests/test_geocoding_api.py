from src.data_collection.geocoding_client import GeocodingClient


client = GeocodingClient()

data = client.geocode("silk_board")

print(data)