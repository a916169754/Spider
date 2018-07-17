import asyncio
import requests

async def hello1(url):
    print('55555555555555555555')
    loop = asyncio.get_event_loop()
    a = await loop.run_in_executor(None, requests.get, url)
    print(1)
    return 2

async def hello(n,url):
    print("协程" + str(n) +"启动")
    a = await hello1(url)
    print(a)
    print("协程" + str(n) + "结束")
    # await hello2(n)

if __name__ == "__main__":
    tasks = []
    url = 'http://www.baidu.com'
    for i in range(0, 10):
        tasks.append(hello(i,url))

    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.wait(tasks))
    loop.close()