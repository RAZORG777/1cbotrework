from tests.helpers import auth


async def test_healthz(client):
    r = await client.get("/max/healthz")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


async def test_doctors_proxied_from_onec(client, mocks):
    r = await client.get("/max/doctors", params={"branch": "Профсоюзная"}, headers=auth(1))
    assert r.status_code == 200
    assert r.json()[0]["id"] == "doc-1"
    assert mocks["doctors"].called


async def test_index_served(client):
    r = await client.get("/max/")
    assert r.status_code == 200 and "<html" in r.text.lower()
