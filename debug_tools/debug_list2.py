import asyncio
from web_app.app import list_messages, app

async def test():
    with app.test_request_context('/api/messages'):
        try:
            res = await list_messages()
            print("SUCCESS", res[0].data)
        except Exception as e:
            import traceback
            traceback.print_exc()

asyncio.run(test())
