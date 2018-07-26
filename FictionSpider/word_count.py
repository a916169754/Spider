# -*- coding:UTF-8 -*-
import os
import asyncio

from threading import Thread
from pyspark import SparkContext
from pyspark import SparkConf


class Counter:
    def __init__(self):
        conf = SparkConf().setMaster("local").setAppName("words count")
        self.sc = SparkContext(conf=conf)

    # 读取文件
    async def loadFile(self, filePath):
        self.inputRDD = self.sc.textFile(filePath)
        return True  # 使用协程以标明加载完毕

    # 针对输入word计数
    def count(self, word):
        linesRdd = self.inputRDD.filter(lambda line: word in line)
        sum = 0
        for line in linesRdd.collect():
            sum += line.count(word)
        return sum


async def run(counterWord, file_name, word, result_dict):
    file_path = 'hdfs://localhost:9000/xiaoshuo/ww/{}'.format(file_name)
    await counterWord.loadFile(file_path)
    result_dict.update({file_name: counterWord.count(word)})


def start_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


if __name__ == '__main__':
    counterWord = Counter()
    word = input('What word do you want to count? :')

    rootdir = '/usr/local/ww'
    dir_list = os.listdir(rootdir)
    tasks = []
    result_dict = {}
    for i in range(0, len(dir_list)):
        path = os.path.join(rootdir,dir_list[i])
        if os.path.isfile(path):
            #print('The result is ' + str(run(counterWord, 'hdfs://localhost:9000/xiaoshuo/ww/{}'.format(dir_list[i]), word)))
            coroutine = run(counterWord, dir_list[i], word, result_dict)
            tasks.append(asyncio.ensure_future(coroutine))
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.wait(tasks))
    print(result_dict)
