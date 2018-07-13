import time
import json
import redis
import re
import requests

from pymongo import MongoClient

from QQSpider.cookie import Cookie
from QQSpider.ip import IpPool
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


def get_page(url, cookies, ip):
    print(url)
    jar = requests.cookies.RequestsCookieJar()
    for cookie_key in cookies:
        jar.set(cookie_key, cookies[cookie_key], domain='.qzone.qq.com', path='/')
    headers = {
        'user-agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 12_0 like Mac OS X; zh-CN) AppleWebKit/537.51.1 (KHTML, like Gecko) Mobile/16A5288q UCBrowser/12.0.3.1077 Mobile  AliApp(TUnionSDK/0.1.20.3)'
    }
    if ip:
        proxies = {
            "https": ip  # 代理ip
        }
        res = requests.get(url, cookies=jar, headers=headers, proxies=proxies)
    else:
        res = requests.get(url, cookies=jar, headers=headers)
    return res


def get_by_html(conn, cookie, qq, mongodb, ip_pool=None):
    my_set = mongodb.test_set
    my_photo = mongodb.my_photo

    bf = BloomFilter()
    url = "https://h5.qzone.qq.com/mqzone/profile?starttime={}&hostuin={}".format(
        int(round(time.time() * 1000)), qq)
    username, cookies = cookie.get_by_random()
    username = username.split('-')[0]
    qzonetoken = cookies.pop('qzonetoken')
    if ip_pool:
        ip_data = ip_pool.get_ip('{}-ip'.format(username))
        ip = "{}:{}".format(ip_data[b'ip'].decode(), ip_data[b'port'].decode())
    else:
        ip = None
    try:
        res = get_page(url, cookies, ip)
    except:
        return
    if "空间主人设置了访问权限" in res.text:
        print('{} 设置了访问权限'.format(qq))
        return
    if "请重新登录" in res.text:
        print('登录失效', username)
        # cookie已失效
        cookie.set_cookie(username, settings.user_list[username])
        cookies = cookie.get_by_id(username)
        qzonetoken = cookies.pop('qzonetoken')
        res = get_page(url, cookies, '')
    pattern = re.compile(r'"mine",data\s+:(.*),times', re.S)
    match = re.search(pattern, res.text.replace('\n', ''))

    text = re.sub(re.compile(r',(\s+)"'), r',"', match.group(1))
    text = re.sub(re.compile(r'{(\s+)"'), r'{"', text)
    # print(res.text)
    text = text.replace('},{"cell_template"', '},end{"cell_template"')
    likemans = []
    for m in re.finditer(re.compile(r'{"cell_template".+?},end', re.S), text):
        # 获取动态
        summary = re.search(re.compile(r'"summary":{"summary":"(.+?)"}', re.S), m.group())
        if summary:
            print(summary.group(1))
            summary = re.sub(re.compile(r'\[em].+?[/em]]'), r' ', summary.group(1))
            my_set.insert({'summary': summary})
            # print(summary)
            # 查找点赞列表
            # print(m.group())
            likeman = re.search(re.compile(r'"like":{(.*)},"operation"', re.S), m.group())
            # print(likeman.group(1))
            # print('\n')
            if likeman:
                for uin in re.finditer(re.compile(r'"uin":"(.*?)"', re.S), likeman.group(1)):
                    likemans.append(uin.group(1))
        # 获取图片
        for photo in re.finditer(re.compile(r'"photourl":(.*?){"busi_param"', re.S), m.group()):
            url = re.search(re.compile(r'"url":"(.*?)"', re.S), photo.group())
            my_photo.insert({'photo_url': url.group(1)})
            print(url.group(1))
    # print(summary)

    print('\n')
    print(likemans)
    for user in likemans:
        if not bf.exists(user.encode('utf8')):
            conn.rpush('user_list', user)
            bf.insert(user.encode('utf8'))


def main():
    redis_conn = redis.Redis(host='127.0.0.1', port=6379)
    cookie = Cookie()
    ip_pool = IpPool()

    conn = MongoClient('127.0.0.1', 27017)
    mongodb = conn.qqdb

    start_url = ['2239509957', '1145391165', '648683283']
    for qq in start_url:
        get_by_html(redis_conn, cookie, qq, mongodb)

    while True:
        qq = redis_conn.lpop("user_list")
        qq = qq.decode('utf8')
        get_by_html(redis_conn, cookie, qq, mongodb, ip_pool)


if __name__ == "__main__":
    main()
    # proxies = {
    #     "http": "http://118.190.95.26:9001"  # 代理ip
    # }
    # headers = {
    #     "User_Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.1 (KHTML, like Gecko) Chrome/22.0.1207.1 Safari/537.1",
    #     "Referer": "http://www.baidu.com"
    # }
    #
    # http_url = "http://icanhazip.com"
    # res = requests.get(url=http_url, headers=headers, proxies=proxies, timeout=30)
    # if res.status_code == 200:
    #     print("访问网页成功: ", res.content)
    # else:
    #     print("代理ip错误: ", res.status_code)

