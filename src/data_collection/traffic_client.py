import os
import sys

import requests
from dotenv import load_dotenv

from src.logging.logger import logging
from src.exception.exception import CustomException


load_dotenv()


class TrafficClient:

    def __init__(self):
        try:
            self.api_key = os.getenv("TOMTOM_API_KEY")

            if not self.api_key:
                raise ValueError("TOMTOM_API_KEY is not set")

            self.base_url = (
                "https://api.tomtom.com/traffic/services/4/"
                "flowSegmentData/absolute/10/json"
            )

            logging.info("TrafficClient initialized successfully")

        except Exception as e:
            logging.error("Error while initializing TrafficClient")
            raise CustomException(e, sys)

    def get_traffic(self, latitude: float, longitude: float) -> dict:

        try:
            logging.info(
                f"Fetching traffic data for "
                f"latitude={latitude}, longitude={longitude}"
            )

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

            data = response.json()

            logging.info("Traffic data fetched successfully")

            return data

        except Exception as e:
            logging.error("Error while fetching traffic data")
            raise CustomException(e, sys)