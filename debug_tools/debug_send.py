import asyncio
from web_app.app import send_message, app

async def test():
    with app.test_request_context('/api/send', json={"number": "+48123456789", "text": "Test"}):
        try:
            res = await send_message()
            print("SUCCESS", res)
        except Exception as e:
            import traceback
            traceback.print_exc()

asyncio.run(test())
