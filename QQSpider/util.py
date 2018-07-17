from hashlib import md5


class SimpleHash(object):
    def __init__(self, cap, seed):
        self.cap = cap
        self.seed = seed

    def hash(self, value):
        ret = 0
        for i in range(len(value)):
            ret += self.seed * ret + ord(value[i])
        return (self.cap - 1) & ret


class BloomFilter(object):
    def __init__(self, redis_conn, block_num=1, key='bloomfilter'):
        """
        Args:
            redis_conn: redis连接
            block_num: 去重块的数量
            key: key name
        """
        self.server = redis_conn
        self.bit_size = 1 << 31
        self.seeds = [5, 7, 11, 13, 31, 37, 61]
        self.key = key
        self.block_num = block_num
        self.hash_func_list = []
        for seed in self.seeds:
            self.hash_func_list.append(SimpleHash(self.bit_size, seed))

    def exists(self, str_input):
        if not str_input:
            return False
        m5 = md5()
        m5.update(str_input)
        str_input = m5.hexdigest()
        ret = True
        name = self.key + str(int(str_input[0:2], 16) % self.block_num)
        for f in self.hash_func_list:
            loc = f.hash(str_input)
            ret = ret & self.server.getbit(name, loc)
        return ret

    def insert(self, str_input):
        m5 = md5()
        m5.update(str_input)
        str_input = m5.hexdigest()
        name = self.key + str(int(str_input[0:2], 16) % self.block_num)
        for f in self.hash_func_list:
            loc = f.hash(str_input)
            self.server.setbit(name, loc, 1)