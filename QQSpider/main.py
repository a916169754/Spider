import time
import json
import redis
import re
import functools
import requests
import asyncio

from threading import Thread
from pymongo import MongoClient

from QQSpider.cookie import Cookie
from QQSpider.ip import IpPool
from QQSpider.parse import parse_profile
from QQSpider.util import BloomFilter
from QQSpider import settings


def get_g_tk(cookie):
    """生成g_tk"""
    hashes = 5381
    for letter in cookie['p_skey']:
        hashes += (hashes << 5) + ord(letter)  # ord()是用来返回字符的ascii码
    return hashes & 0x7fffffff


def get_by_api(cookie):
    """获取说说"""
    url = "https://user.qzone.qq.com/proxy/domain/taotao.qq.com/" \
          "cgi-bin/emotion_cgi_msglist_v6?" \
          "uin=1277715368&ftype=0&sort=0&pos=40&num=20&replynum=100&g_tk={}&callback=_preloadCallback&code_version=1&format=jsonp&need_private_comment=1&qzonetoken={}&g_tk={}"
    username, cookies = cookie.get_by_random()
    qzonetoken = cookies.pop('qzonetoken')
    url = url.format(get_g_tk(cookies), qzonetoken, get_g_tk(cookies))
    jar = requests.cookies.RequestsCookieJar()
    for cookie_key in cookies:
        jar.set(cookie_key, cookies[cookie_key], domain='.qzone.qq.com', path='/')
    headers = {
        'user-agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 12_0 like Mac OS X; zh-CN) AppleWebKit/537.51.1 (KHTML, like Gecko) Mobile/16A5288q UCBrowser/12.0.3.1077 Mobile  AliApp(TUnionSDK/0.1.20.3)'
    }
    res = requests.get(url, cookies=jar, headers=headers)


async def get_html(qq, cookies, loop, ip=None):
    url = "https://h5.qzone.qq.com/mqzone/profile?starttime={}&hostuin={}".format(
        int(round(time.time() * 1000)), qq)

    jar = requests.cookies.RequestsCookieJar()
    for cookie_key in cookies:
        jar.set(cookie_key, cookies[cookie_key], domain='.qzone.qq.com', path='/')
    headers = {
        'user-agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 12_0 like Mac OS X; zh-CN) AppleWebKit/537.51.1 (KHTML, like Gecko) Mobile/16A5288q UCBrowser/12.0.3.1077 Mobile  AliApp(TUnionSDK/0.1.20.3)'
    }
    try:
        if ip:
            proxies = {
                "https": ip  # 代理ip
            }
            func = functools.partial(
                requests.get, url, cookies=jar, headers=headers, proxies=proxies
            )
        else:
            func = functools.partial(
                requests.get, url, cookies=jar, headers=headers
            )
        res = await loop.run_in_executor(None, func)
    except Exception as e:
        return False, e
    finally:
        if "空间主人设置了访问权限" in res.text:
            return False, '403'
        elif "请重新登录" in res.text:
            return False, 'invalid_cookie'
        print('开始解析爬取: ', url)
        return True, res.text


def start_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


async def do_work(qq, cookie, ip_pool, redis_conn, my_set, my_photo, bf, new_loop):
    # 随机获取cookie
    username, cookies = cookie.get_by_random()
    username = username.split('-')[0]
    qzonetoken = cookies.pop('qzonetoken')

    # 获取代理ip
    ip_data = ip_pool.get_ip('{}-ip'.format(username))
    ip = "{}:{}".format(ip_data[b'ip'].decode(), ip_data[b'port'].decode())

    success, html_or_err = await get_html(qq, cookies, new_loop, ip)
    if success:
        # 处理页面
        data = parse_profile(html_or_err)
        # 存储数据
        for summary in data['summary']:
            my_set.insert({'summary': summary})
        for photo_url in data['photo_url']:
            my_photo.insert({'photo_url': photo_url})
        # 将点赞列表添加进待爬队列
        for user in data['likes']:
            if not bf.exists(user.encode('utf8')):
                redis_conn.rpush('user_list', user)
                bf.insert(user.encode('utf8'))
    else:
        if html_or_err == 'invalid_cookie':
            # cookie已失效, 更新该cookie并将qq重现放回待爬队列
            cookie.set_cookie(username, settings.user_list[username])
        redis_conn.rpush('user_list', qq)


def main():
    redis_conn = redis.Redis(host='127.0.0.1', port=6379)
    mongo_conn = MongoClient('127.0.0.1', 27017)
    mongodb = mongo_conn.qqdb
    my_set = mongodb.test_set
    my_photo = mongodb.my_photo

    cookie = Cookie(redis_conn)
    ip_pool = IpPool(redis_conn)
    bf = BloomFilter(redis_conn)

    start_list = ['***', '***', '***']

    for qq in start_list:
        if not bf.exists(qq.encode('utf8')):
            redis_conn.rpush('user_list', qq)
            bf.insert(qq.encode('utf8'))
    # 在子线程中开启事件循环
    new_loop = asyncio.new_event_loop()
    t = Thread(target=start_loop, args=(new_loop,))
    t.setDaemon(True)
    t.start()
    try:
        while True:
            _, qq = redis_conn.blpop("user_list")
            qq = qq.decode('utf8')
            asyncio.run_coroutine_threadsafe(
                do_work(qq, cookie, ip_pool, redis_conn, my_set, my_photo, bf, new_loop),
                new_loop
            )
    except Exception as e:
        print(e)
        new_loop.stop()


if __name__ == "__main__":
    main()
