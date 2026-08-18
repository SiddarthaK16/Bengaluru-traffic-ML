from src.database.mongo_client import MongoDBClient


mongo_client = MongoDBClient()

data = {
    "location": "silk_board",
    "latitude": 12.914202,
    "longitude": 77.625029,
    "currentSpeed": 21,
    "freeFlowSpeed": 45,
    "currentTravelTime": 180,
    "freeFlowTravelTime": 120,
    "confidence": 1.0,
    "roadClosure": False,
    "frc": "FRC2"
}

inserted_id = mongo_client.insert_one(data)

print("Inserted document ID:", inserted_id)