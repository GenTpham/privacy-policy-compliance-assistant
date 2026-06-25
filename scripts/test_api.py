import httpx
import asyncio

async def test():
    async with httpx.AsyncClient() as client:
        r = await client.post('http://127.0.0.1:8000/auth/login', json={'username':'admin','password':'admin'})
        print("Login status:", r.status_code)
        if r.status_code != 200:
            print(r.text)
            return
        token = r.json()['access_token']
        
        doc_id = 'eca47643-eb86-4ffa-bb5a-3158ad832e6d'
        
        r3 = await client.get(f'http://127.0.0.1:8000/api/documents/{doc_id}/job_status', headers={'Authorization': f'Bearer {token}'})
        print("Job status response:", r3.status_code)
        print(r3.json())

asyncio.run(test())
