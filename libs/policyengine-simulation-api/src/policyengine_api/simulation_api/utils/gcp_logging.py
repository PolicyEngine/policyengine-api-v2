from google.cloud.logging import Client

logger = Client(project="prod-api-v2-c4d5").logger("prod-api-v2-c4d5")
