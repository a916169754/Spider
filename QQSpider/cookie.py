# -*- coding: UTF-8 -*-
import time
import json
import re
import requests
import random
import cv2
import numpy as np

from PIL import Image
from io import BytesIO

from QQSpider import settings

# from pynput.mouse import Button, Controller

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import ActionChains
from selenium.common.exceptions import TimeoutException


# mouse = Controller()
# mouse.move(0, 0)

def get_track(distance):
    ''' 不可行
        拿到移动轨迹，模仿人的滑动行为，先匀加速后匀减速
        匀变速运动基本公式：
        ①v=v0+at
        ②s=v0t+(1/2)at²
        ③v²-v0²=2as

        :param distance: 需要移动的距离
        :return: 存放每0.2秒移动的距离
    '''
    # 初速度
    v = 0
    # 单位时间为0.2s来统计轨迹，轨迹即0.2内的位移
    t = 0.1
    # 位移/轨迹列表，列表内的一个元素代表0.2s的位移
    tracks = []
    # 当前的位移
    current = 0
    # 到达mid值开始减速
    mid = distance * 4 / 5

    distance += 0  # 先滑过一点，最后再反着滑动回来

    while current < distance:
        if current < mid:
            # 加速度越小，单位时间的位移越小,模拟的轨迹就越多越详细
            a = 2  # 加速运动
        else:
            a = -3  # 减速运动

        # 初速度
        v0 = v
        # 0.2秒时间内的位移
        s = v0 * t + 0.5 * a * (t ** 2)
        # 当前的位置
        current += s
        # 添加到轨迹列表
        tracks.append(round(s))

        # 速度已经达到v,该速度作为下次的初速度
        v = v0 + a * t

    return tracks


def ease_out_quad(x):
    return 1 - (1 - x) * (1 - x)


def ease_out_quart(x):
    return 1 - pow(1 - x, 4)


def ease_out_expo(x):
    if x == 1:
        return 1
    else:
        return 1 - pow(2, -10 * x)


def get_tracks(distance, seconds, ease_func):
    """
    生成滑动轨迹
    """
    tracks = [0]
    offsets = [0]
    for t in np.arange(0.0, seconds, 0.1):
        ease = globals()[ease_func]
        offset = round(ease(t / seconds) * distance)
        tracks.append(offset - offsets[-1])
        offsets.append(offset)
    return offsets, tracks


def get_image_position(template_url, block_url):
    """
    通过open cv获取坐标
    """
    block = cv2.imread(template_url, 0)
    template = cv2.imread(block_url, 0)

    cv2.imwrite('template_1.jpg', template)
    cv2.imwrite('block_1.jpg', block)
    block = cv2.imread('block_1.jpg')
    block = cv2.cvtColor(block, cv2.COLOR_BGR2GRAY)
    block = abs(255 - block)
    cv2.imwrite('block_1.jpg', block)

    block = cv2.imread('block_1.jpg')
    template = cv2.imread('template_1.jpg')

    result = cv2.matchTemplate(block, template, cv2.TM_CCOEFF_NORMED)
    x, y = np.unravel_index(result.argmax(), result.shape)
    return x, y


class Cookie(object):
    """
    维护cookie池
    """
    def __init__(self, redis_conn):
        self.conn = redis_conn

        self.options = webdriver.ChromeOptions()
        self.options.add_argument('lang=zh_CN.UTF-8')
        self.options.add_argument(
            'user-agent=" Mozilla/5.0 (iPhone; CPU iPhone OS 12_0 like Mac OS X; zh-CN) AppleWebKit/537.51.1 (KHTML, like Gecko) Mobile/16A5288q UCBrowser/12.0.3.1077 Mobile  AliApp(TUnionSDK/0.1.20.3)"')
        for username, password in settings.user_list.items():
            if self.conn.exists('{}-cookies'.format(username)):
                continue
            self.set_cookie(username, password)

    def set_cookie(self, username, password):
        """
        设置cookie，若已存在会强制覆盖

        Args:
            username: qq号
            password: 密码

        """
        driver = webdriver.Chrome(chrome_options=self.options)
        # 设置隐式等待
        driver.implicitly_wait(10)
        driver.set_window_size(1366, 768)
        driver.delete_all_cookies()

        driver.get(settings.login_url)
        driver.find_element_by_id('u').click()
        driver.find_element_by_id('u').send_keys(username)
        driver.find_element_by_id('p').click()
        driver.find_element_by_id('p').send_keys(password)
        driver.find_element_by_id('go').click()
        is_frame = False

        while True:
            try:
                WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.ID, "nav_bar_main"))
                )
            except TimeoutException:
                if not is_frame:
                    driver.switch_to.frame('tcaptcha_iframe')
                    is_frame = True

                driver.find_element_by_id('reload').click()
                time.sleep(2)
                self.__captcha(driver)
            else:
                cookies = {}
                for item in driver.get_cookies():
                    cookies[item['name']] = item['value']

                #  获取 qzonetoken
                html = driver.page_source
                g_qzonetoken = re.search('window\.shine0callback = \(function\(\)\{ try\{return (.*?);\} catch\(e\)',
                                         html)  # 从网页源码中提取g_qzonetoken
                g_qzonetoken = str(g_qzonetoken.group(1))
                cookies['qzonetoken'] = g_qzonetoken
                self.conn.set('{}-cookies'.format(username), json.dumps(cookies))
                driver.quit()
                break

    def __captcha(self, driver):
        try:
            WebDriverWait(driver, 300).until(
                EC.presence_of_element_located((By.ID, "bkBlock"))
            )
        finally:
            template = driver.find_element_by_id('bkBlock').get_attribute('src')
            targ = driver.find_element_by_id('slideBlock').get_attribute('src')

            headers = {
                'user-agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 11_0 like Mac OS X) AppleWebKit/604.1.38 (KHTML, like Gecko) Version/11.0 Mobile/15A372 Safari/604.1'}

            template_res = requests.get(template, headers=headers)
            Image.open(BytesIO(template_res.content)).save('template.png')

            targ_res = requests.get(targ, headers=headers)
            Image.open(BytesIO(targ_res.content)).save('targ.png')
            x, y = get_image_position('template.png', 'targ.png')

            button = driver.find_element_by_id('tcaptcha_drag_thumb')
            print(button.location)
            # 操作真实鼠标滑动
            # mouse.position = int(button.location['x'] + 40), int(button.location['y'] + 170)
            # mouse.press(Button.left)
            # offsets, track = get_tracks((y * 0.4 - 0), 12, 'ease_out_expo')
            # for i in track:
            #     mouse.move(i, 0)
            #     time.sleep(random.randint(1, 7) / 100)
            # mouse.release(Button.left)
            # 模拟鼠标滑动
            action = ActionChains(driver)
            action.move_to_element(button).perform()

            action.click_and_hold(button).perform()
            action.reset_actions()
            track = get_tracks((y * 0.4 - 0), 12, 'ease_out_expo')
            for i in track:
                action.move_by_offset(xoffset=i, yoffset=0).perform()
                action.reset_actions()
                time.sleep(random.randint(1, 7) / 100)
            time.sleep(0.5)
            action.release().perform()

    def get_by_id(self, num):
        """
        通过qq号获取cookie
        """
        return json.loads(str(self.conn.get(str(num) + '-cookies'), 'utf-8'))

    def get_by_random(self):
        """
        随机获取cookie
        """
        keys = self.conn.keys('*-cookies')
        key = random.choice(keys)
        key = str(key, 'utf-8')
        cookie = json.loads(str(self.conn.get(key), 'utf-8'))
        return key, cookie
