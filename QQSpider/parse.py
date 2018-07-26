import re


def parse_profile(text: str) -> dict:
    """
    解析qq空间主页说说以及所带图片

    Args:
        text: 网页内容

    Returns:
        {
            'likes': [xxx, ...],  # 点赞列表
            'summary': [xxx, ...], # 内容主体
            'photo_url': [xxx, ...] # 图片
        }

    """
    return_dict = dict()
    photo_url_list = []
    summary_list = []
    likeman_list = []

    pattern = re.compile(r'"mine",data\s+:(.*),times', re.S)
    match = re.search(pattern, text.replace('\n', ''))

    text = re.sub(re.compile(r',(\s+)"'), r',"', match.group(1))
    text = re.sub(re.compile(r'{(\s+)"'), r'{"', text)
    text = text.replace('},{"cell_template"', '},end{"cell_template"')

    for m in re.finditer(re.compile(r'{"cell_template".+?},end', re.S), text):
        # 获取动态
        summary = re.search(re.compile(r'"summary":{"summary":"(.+?)"}', re.S), m.group())
        if summary:
            summary = re.sub(re.compile(r'\[em].+?[/em]]'), r' ', summary.group(1))
            summary_list.append(summary)
            # 查找点赞列表
            likeman = re.search(re.compile(r'"like":{(.*)},"operation"', re.S), m.group())
            if likeman:
                for uin in re.finditer(re.compile(r'"uin":"(.*?)"', re.S), likeman.group(1)):
                    likeman_list.append(uin.group(1))
        # 获取图片
        for photo in re.finditer(re.compile(r'"photourl":(.*?){"busi_param"', re.S), m.group()):
            url = re.search(re.compile(r'"url":"(.*?)"', re.S), photo.group())
            photo_url_list.append(url.group(1))

    return_dict['likes'] = likeman_list
    return_dict['summary'] = summary_list
    return_dict['photo_url'] = photo_url_list

    return return_dict
