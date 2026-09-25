import httpx

class OneCClient:
    def __init__(self, base_url: str, auth: tuple):
        self.base_url = base_url
        self.auth = auth

    async def _make_request(self, method: str, endpoint: str, params=None, json=None):
        async with httpx.AsyncClient(auth=self.auth, timeout=10.0) as client:
            url = f"{self.base_url}/{endpoint}"
            response = await client.request(method, url, params=params, json=json)
            response.raise_for_status()
            return response.json()

    async def get_doctors(self, branch: str = None, date: str = None):
        params = {}
        if branch: params["branch"] = branch
        if date: params["date"] = date
        return await self._make_request("GET", "doctors", params=params)

    async def get_services(self, doctor_id: str = None):
        params = {}
        if doctor_id: 
            params["doctor_id"] = doctor_id
        return await self._make_request("GET", "services", params=params)

    # ✅ ИСПРАВЛЕНО: добавлены start_date и end_date
    async def get_schedule(self, doctor_id: str, date: str = None, branch: str = None, start_date: str = None, end_date: str = None):
        params = {"doctor_id": doctor_id}
        if branch: params["branch"] = branch
        
        if start_date and end_date:
            params["start_date"] = start_date
            params["end_date"] = end_date
        elif date:
            params["date"] = date
            
        return await self._make_request("GET", "schedule", params=params)

    async def create_booking(self, data: dict):
        return await self._make_request("POST", "book", json=data)

    async def cancel_booking(self, appointment_id: str):
        payload = {"appointment_id": appointment_id}
        return await self._make_request("POST", "cancel", json=payload)