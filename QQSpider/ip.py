import json
import datetime

import requests

from QQSpider.settings import user_list


class IpPool(object):
    """
    IP
    """
    def __init__(self, redis_conn):
        self.conn = redis_conn

        self.__update()

    def __update(self):
        ip_date = IpPool.get_ip_data(len(user_list))
        for index, username in enumerate(user_list):
            ip_info = ip_date[index]
            self.set_ip('{}-ip'.format(username), ip_info['ip'], ip_info['port'], ip_info['expire_time'])

    @staticmethod
    def get_ip_data(num):
        """使用收费代理"""
        get_ip_url = "http://webapi.http.zhimacangku.com/getip?" \
                     "num={}&type=2&pro=440000&city=440400&yys=0" \
                     "&port=11&pack=8898&ts=1&ys=0&cs=0&lb=1&sb=0" \
                     "&pb=4&mr=1&regions=".format(num)
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
        return ip_info
