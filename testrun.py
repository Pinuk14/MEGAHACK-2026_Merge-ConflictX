from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)
response = client.post('/analyze', json={
    'text': 'The Ministry shall publish compliance rules within 60 days. All operators must submit quarterly reports and may face penalties. Citizens should receive transparent notices about data use. The regulator will conduct annual audits.'
})
print(response.status_code)
print(response.json())