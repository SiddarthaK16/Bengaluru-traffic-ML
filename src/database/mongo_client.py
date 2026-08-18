import os
import sys

from dotenv import load_dotenv
from pymongo import MongoClient

from src.logging.logger import logging
from src.exception.exception import CustomException


load_dotenv()


class MongoDBClient:

    def __init__(self):

        try:
            self.mongo_uri = os.getenv("MONGO_DB_URL")

            if not self.mongo_uri:
                raise ValueError("MONGO_DB_URL is not set")

            self.client = MongoClient(self.mongo_uri)

            self.client.admin.command("ping")

            self.database = self.client["bengaluru_traffic"]
            self.collection = self.database["traffic_data"]

            logging.info(
                "MongoDB Atlas connection established successfully"
            )

        except Exception as e:

            logging.error(
                "Error while connecting to MongoDB Atlas"
            )

            raise CustomException(e, sys)


    def insert_many(self, data: list):

        try:
            result = self.collection.insert_many(data)

            logging.info(
                f"Inserted {len(result.inserted_ids)} documents successfully"
              )

            return result.inserted_ids

        except Exception as e:

            logging.error("Error while inserting documents into MongoDB")

            raise CustomException(e, sys)