import json
import time
import datetime
import random
import requests


class IpPool(object):
    """
    IP
    """
    def __init__(self, redis_conn):
        self.conn = redis_conn

        # self.__update()

    def __update(self):
        ip_date = IpPool.get_ip_data(50)
        for ip_info in ip_date:
            self.set_ip('{}-ip'.format(ip_info['ip']), ip_info['ip'], ip_info['port'], ip_info['expire_time'])

    @staticmethod
    def get_ip_data(num):
        """使用收费代理"""
        get_ip_url = "http://*******/getip?num={}&type=2&" \
                     "*******" .format(num)
        res = requests.get(get_ip_url)
        res_json = json.loads(res.text)
        return res_json['data']

    def set_ip(self, key, ip, port, expire_time):
        """
        储存代理ip

        Args:
            key: 标识
            ip: 代理ip地址
            port: 代理端口
            expire_time: 有效时间
        """
        self.conn.hmset(key, {'ip': ip, 'port': port, 'expire_time': expire_time})
        return self.conn.hgetall(key)

    def get_ip(self, key):
        """提取ip"""
        ip_info = self.conn.hgetall(key)
        expire_time = datetime.datetime.strptime(ip_info[b'expire_time'].decode(), '%Y-%m-%d %H:%M:%S')
        if expire_time < datetime.datetime.today():
            ip_info = IpPool.get_ip_data(1)[0]
            ip_info = self.set_ip(key, ip_info['ip'], ip_info['port'], ip_info['expire_time'])
        return "{}:{}".format(ip_info[b'ip'], ip_info[b'port'])

    def get_by_random(self):
        """
        随机获取ip
        """
        keys = self.conn.keys('*-ip')
        key = random.choice(keys)
        key = str(key, 'utf-8')
        ip_info = self.conn.hgetall(key)
        expire_time = datetime.datetime.strptime(ip_info[b'expire_time'].decode(), '%Y-%m-%d %H:%M:%S')
        if expire_time < datetime.datetime.today():
            time.sleep(1)
            try:
                ip_info = IpPool.get_ip_data(1)[0]
                ip_info = self.set_ip(key, ip_info['ip'], ip_info['port'], ip_info['expire_time'])
            except:
                ip_info = self.conn.hgetall(random.choice(keys))
        return "{}:{}".format(ip_info[b'ip'].decode(), ip_info[b'port'].decode())
