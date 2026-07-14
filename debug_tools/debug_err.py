import asyncio
from web_app.app import get_map_session

async def test():
    try:
        res = await get_map_session()
        print("SUCCESS", res)
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(test())
