import os

import requests
from dotenv import load_dotenv


load_dotenv()


class TrafficClient:

    def __init__(self):
        self.api_key = os.getenv("TOMTOM_API_KEY")

        if not self.api_key:
            raise ValueError("TOMTOM_API_KEY is not set")

        self.base_url = (
            "https://api.tomtom.com/traffic/services/4/"
            "flowSegmentData/absolute/10/json"
        )

    def get_traffic(self, latitude: float, longitude: float) -> dict:

        params = {
            "key": self.api_key,
            "point": f"{latitude},{longitude}",
            "unit": "KMPH",
        }

        response = requests.get(
            self.base_url,
            params=params,
            timeout=10,
        )

        response.raise_for_status()

        return response.json()