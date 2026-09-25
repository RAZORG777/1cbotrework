"""T073: без явного согласия на ПДн запись и перенос не уходят в 1С."""

import pytest

from tests.helpers import auth, booking


@pytest.mark.parametrize("consent", [None, False])
@pytest.mark.parametrize("path", ["/book", "/reschedule"])
async def test_consent_required(client, mocks, consent, path):
    body = booking(consent=consent, old_id="appt-1" if path == "/reschedule" else None)
    r = await client.post(path, json=body, headers=auth(5))
    assert r.status_code == 422 and r.json()["error"] == "PD_CONSENT_REQUIRED"
    assert not mocks["book"].called and not mocks["reschedule"].called
