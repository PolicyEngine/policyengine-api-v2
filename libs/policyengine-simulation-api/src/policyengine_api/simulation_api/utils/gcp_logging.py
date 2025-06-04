from google.cloud.logging import Client

logger = Client().logger("prod-api-v2-c4d5")
