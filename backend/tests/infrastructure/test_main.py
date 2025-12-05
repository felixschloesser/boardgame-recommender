from boardgames_api.app import app
from fastapi.testclient import TestClient

# Legacy tests rely on TestClient import side effects; use fixture in other modules.
client = TestClient(app)
