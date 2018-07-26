import time
import random
import redis
import re
import requests
import functools
import asyncio

from threading import Thread

from FictionSpider.ip import IpPool


headers = {
                'user-agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 12_0 like Mac OS X; zh-CN) AppleWebKit/537.51.1 (KHTML, like Gecko) Mobile/16A5288q UCBrowser/12.0.3.1077 Mobile  AliApp(TUnionSDK/0.1.20.3)'
            }


class MyThread (Thread):
    def __init__(self, redis_conn, ip_pool, fiction_url, fiction_title):
        Thread.__init__(self)
        self.redis_conn = redis_conn
        self.ip_pool = ip_pool
        self.fiction_url = fiction_url
        self.fiction_title = fiction_title

    def run(self):
        get_fiction_content(self.redis_conn, self.ip_pool, self.fiction_url, self.fiction_title)


def get_fiction_list(redis_conn, ):
    url = "https://www.00xs.cc/yanqing/{}"
    page = 1
    max_num = 200

    while redis_conn.scard("fiction_list") < max_num:
        res = requests.get(url=url.format(page))
        res.encoding = "gbk"
        pattern = re.compile(r'id="container">(.*?)<div style="border-bottom', re.S)
        match = re.search(pattern, res.text)
        for m in re.finditer(re.compile(r'<div class="box">.+?</div>', re.S), match.group(1)):
            fiction_url = re.search(re.compile(r'<a href="(.+?)"', re.S), m.group())
            title = re.search(re.compile(r'alt="(.+?)"', re.S), m.group())
            print(fiction_url.group(1))
            redis_conn.sadd("fiction_list", "{}--{}".format(title.group(1), fiction_url.group(1)))
        page += 1
        time.sleep(random.randint(1, 3))
    return redis_conn.smembers("fiction_list")


def get_fiction_content(redis_conn, ip_pool, fiction_url, name):
    catal_url = "https://www.00xs.cc{}0/".format(fiction_url)
    res = requests.get(url=catal_url)
    res.encoding = "gbk"
    with open('xiaoshuo/{}.txt'.format(name), 'a', encoding='utf-8') as f:
        for m in re.finditer(re.compile(r'<li><span><a href="/xiaoshuo/(.+?)"', re.S), res.text):
            content_url = "https://www.00xs.cc/xiaoshuo/{}".format(m.group(1))
            if redis_conn.sismember('finish_url', content_url):
                continue
            ip = ip_pool.get_by_random()
            proxies = {
               "https": ip  # 代理ip
            }
            try:
                res = requests.get(url=content_url, headers=headers, proxies=proxies)
            except Exception:  # 代理收费的，失效了就算了
                f.write("\n章节名:" + m.group(1).encode().decode('utf8'))
                f.write("获取失败")
                continue
            res.encoding = "gbk"
            title = re.search(re.compile(r'<h1 class="article-title">(.*?)</h1>', re.S), res.text)
            content = re.search(re.compile(r'<div class="article-con".+?>(.*?)</div>', re.S), res.text)
            try:
                title = title.group(1).encode().decode('utf8')
            except:
                title = " "
            content = content.group(1).encode().decode('utf8').replace('<br />', '')
            f.write("\n章节名:" + title)
            f.write(content)
            print('完成{}-{}'.format(name, title))
            redis_conn.sadd('finish_url', content_url)
    redis_conn.sadd('finish_list', "{}--{}".format(name, fiction_url))
    print('finish: ', name)


async def async_get_fiction_content(redis_conn, ip_pool, fiction_url, name, loop):
    catal_url = "https://www.00xs.cc{}0/".format(fiction_url)
    res = requests.get(url=catal_url)
    res.encoding = "gbk"
    for m in re.finditer(re.compile(r'<li><span><a href="/xiaoshuo/(.+?)"', re.S), res.text):
            content_url = "https://www.00xs.cc/xiaoshuo/{}".format(m.group(1))
            if redis_conn.sismember('finish_url', content_url):
                continue
            with open('xiaoshuo/{}.txt'.format(name), 'a', encoding='utf-8') as f:
                ip = ip_pool.get_by_random()
                proxies = {
                   "https": ip  # 代理ip
                }

                func = functools.partial(
                    requests.get, content_url, headers=headers, proxies=proxies, timeout=3
                )
                try:
                    res = await loop.run_in_executor(None, func)
                    #  res = requests.get(url=content_url, headers=headers, proxies=proxies)
                except Exception:  # 代理收费的，失效了就算了
                    f.write("\n章节名:" + m.group(1).encode().decode('utf8'))
                    f.write("获取失败")
                    continue
                res.encoding = "gbk"
                title = re.search(re.compile(r'<h1 class="article-title">(.*?)</h1>', re.S), res.text)
                content = re.search(re.compile(r'<div class="article-con".+?>(.*?)</div>', re.S), res.text)
                title = title.group(1).encode().decode('utf8')
                content = content.group(1).encode().decode('utf8').replace('<br />', '')
                f.write("\n章节名:" + title)
                f.write(content)
            print('完成{}-{}'.format(name, title))
            redis_conn.sadd('finish_url', content_url)
    redis_conn.sadd('finish_list', "{}--{}".format(name, fiction_url))
    print('finish: ', name)


def start_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


def main():
    redis_conn = redis.Redis(host='127.0.0.1', port=6379)
    ip_pool = IpPool(redis_conn)
    fiction_list = get_fiction_list(redis_conn)
    #  使用协程
    # tasks = []
    # loop = asyncio.get_event_loop()
    # for fiction in fiction_list:
    #     if not redis_conn.sismember('finish_list', fiction):  # 查重
    #         fiction = fiction.decode()
    #         fiction_url = fiction.split('--')[1]
    #         fiction_title = fiction.split('--')[0]
    #         coroutine = get_fiction_content(redis_conn, ip_pool, fiction_url, fiction_title, loop)
    #         tasks.append(asyncio.ensure_future(coroutine))
    # loop.run_until_complete(asyncio.wait(tasks))
    #  使用多线程
    for fiction in fiction_list:
        if not redis_conn.sismember('finish_list', fiction):  # 查重
            fiction = fiction.decode()
            fiction_url = fiction.split('--')[1]
            fiction_title = fiction.split('--')[0]
            thread_one = MyThread(redis_conn, ip_pool, fiction_url, fiction_title)
            thread_one.start()


if __name__ == "__main__":
    main()
