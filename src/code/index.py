# -*- coding: utf-8 -*-

# -*- coding: utf-8 -*-

import logging
import os
import re
import threading
import shutil
import time
import urllib.parse
import urllib.request
import oss2
from bs4 import BeautifulSoup
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
from aliyunsdkcore.auth.credentials import AccessKeyCredential
from aliyunsdkcore.auth.credentials import StsTokenCredential
from queue import Queue


LOGGER = logging.getLogger()

DOWNLOADED_FILE_LIST = list()
path_set = set()

LOCAL_PATH = '/tmp/'

PRODUCER_NUM = 20
CONSUMER_NUM = 10


# 正则表达式预编译
# 这里涉及到了非贪婪匹配
# "" or ''
# ?: 取消分组
# ?表示懒惰匹配，尽可能匹配少的字符
# ((?:/[a-zA-Z0-9.]*?)*)
# ((?:/[a-zA-Z0-9.]*)*?)
REG_URL = r'^(https?://|//)?((?:[a-zA-Z0-9-_]+\.)+(?:[a-zA-Z0-9-_:]+))((?:/[-.a-zA-Z0-9_]*?)*)((?<=/)[-_a-zA-Z0-9]+(?:\.([a-zA-Z0-9]+))+)?((?:\?[a-zA-Z0-9%&=]*)*)$'
REG_RESOURCE_TYPE = r'(?:href|src|data\-original|data\-src)=["\'](.+?\.(?:html|htm|shtml|js|css|jpg|jpeg|png|gif|svg|ico|ttf|woff2|asp|jsp|php|perl|cgi))[a-zA-Z0-9\?\=\.]*["\']'
REG_CSS = "(?<=url\\()[^\\)]+"

reg_url = re.compile(REG_URL)
reg_resource = re.compile(REG_RESOURCE_TYPE, re.S)
reg_css = re.compile(REG_CSS)

def valild_resource(resource):
    if resource is not None and resource != "" and resource != '/':
        return True
    return False


'''
解析URL地址
'''


def parse_url(url):
    if not url:
        return
    res = reg_url.search(url)
    # 在这里，我们把192.168.1.109:8080的形式也解析成域名domain，实际过程中www.baidu.com等才是域名，192.168.1.109只是IP地址
    # ('http://', '192.168.1.109:8080', '/abc/images/111/', 'index.html', 'html', '?a=1&b=2')
    if res is not None:
        path = res.group(3)
        protocol = res.group(1) if res.group(1) is not None else 'http://'
        full_path = protocol + res.group(2) + res.group(3)

        if not path.endswith('/'):
            path = path + '/'
            full_path = full_path + '/'
        return dict(
            base_url=protocol + res.group(2),
            full_path=full_path,
            protocol=protocol,
            domain=res.group(2),
            path=path,
            file_name=res.group(4),
            ext=res.group(5),
            params=res.group(6)
        )


'''
解析下载好的 URL 页面, 同时支持 css
'''


def parse_page(page_path):
    if not page_path.endswith(('.html', '.htm', '.shtml', '.css')) \
            or not os.path.exists(page_path):
        LOGGER.error('> %s 网站内容不读取' % (page_path))
        return

    resource_list = []


    with open(page_path, 'r', encoding='utf-8', errors='ignore') as f:
        # 分析网页内容
        content = f.read()
        # LOGGER.info('> %s 网站内容读取完毕，内容长度：%d' % (page_path, len(content)))

        if page_path.endswith(".css"):
            resource_list = [r.strip("'") for r in reg_css.findall(content)]
            
        else:
            soup = BeautifulSoup(content, 'html.parser')
            for link in soup.findAll():
                if valild_resource(link.get('href')):
                    resource_list.append(link.get('href'))
                    # LOGGER.info('> %s 网站链接读取完成' % (link.get('href')))
                if valild_resource(link.get('src')):
                    resource_list.append(link.get('src'))
                    # LOGGER.info('> %s 网站链接读取完成' % (link.get('src')))
                if valild_resource(link.get('data-src')):
                    resource_list.append(link.get('data-src'))
                    # LOGGER.info('> %s 网站链接读取完成' % (link.get('data-src')))
                if valild_resource(link.get('data-original')):
                    resource_list.append(link.get('data-original'))
                    # LOGGER.info('> %s 网站链接读取完成' % (link.get('data-original')))

            # 解析网页内容，获取有效的链接
            # content_list = re.split(r'\s+', content)
            # for line in content_list:
            #     # print(f'content_list {line}')
            #     res_list = reg_resource.findall(line)
            #     if len(res_list) > 0:
            #         resource_list = resource_list + res_list
            #         LOGGER.info('> %s 网站链接读取完成' % (res_list))
    # 去重
    return list(set(resource_list))


'''
下载文件
'''


def download_file(src_url, dist_path):
    if os.path.exists(dist_path):
        return True
    try:
        response = urllib.request.urlopen(src_url)
        if response is None or response.status != 200:
            return LOGGER.error('> 请求异常：%s' % src_url)
        data = response.read()

        dist_dir = "/".join(dist_path.split("/")[0:-1])
        if not os.path.exists(dist_dir):
            os.makedirs(dist_dir)

        f = open(dist_path, 'wb')
        f.write(data)
        f.close()
        DOWNLOADED_FILE_LIST.append(src_url) # append 线程安全
        # LOGGER.info('>>>: %s 下载成功' % src_url)

    except Exception as e:
        LOGGER.error('下载报错：%s, %s' % (src_url, e))
        return False

    return True


def parse_root_resource_url(root_url: str, max_level: int, download_queue: Queue) -> dict:

    def parse_resource_url(url, level):
        if max_level > 0 and level > max_level:
            LOGGER.info("max fetch level {0} reached".format(max_level))
            return

        level += 1
        url_dict = parse_url(url)
        domain = url_dict['domain']

        # 把网站的内容写下来
        page_name = ''
        if url_dict['file_name'] is None:
            page_name = 'index.html'
            url = url_dict['full_path'] + page_name
        else:
            page_name = url_dict['file_name']

        # 临时存储页面至本地
        # 如果是192.168.1.1:8000等形式，变成192.168.1.1-8000，:不可以出现在文件名中
        domain_dir = LOCAL_PATH + re.sub(r':', '-', domain)
        page_dir = domain_dir + url_dict['path']
        page_path = page_dir + page_name
        # 已保存路径，则退出递归
        # url 必然以 html 等为结尾
        if page_path not in path_set and download_file(url, page_path):
            download_queue.put((url, page_path))
            path_set.add(page_path)
        else:
            return

        # 解析备份入口页面内容，提取待备份的资源列表
        resource_list = parse_page(page_path)
        if not resource_list:
            return
        # 下载资源，要区分目录，不存在的话就创建
        for resource_url in resource_list:
            # HTML2RESOURCE[url].append(resource_url)

            # ../js/js
            # ./static/js/index.js
            # //abc.cc/static/js
            # /static/js/index.js
            # http://www.baidu/com/static/index.js
            # static/js/index.js
            if resource_url.startswith('../'):
                resource_url = urllib.parse.urljoin(
                    url_dict['full_path'], resource_url)
            elif resource_url.startswith('./'):
                resource_url = urllib.parse.urljoin(
                    url_dict['full_path'], resource_url)
            elif resource_url.startswith('//'):
                resource_url = 'https:' + resource_url
            elif resource_url.startswith('/'):
                resource_url = url_dict['base_url'] + resource_url
            elif resource_url.startswith('http') or resource_url.startswith('https'):
                # 带域名情况，非相对路径，直接处理该URL
                pass
            elif not (resource_url.startswith('http') or resource_url.startswith('https')):
                # static/js/index.js这种情况
                resource_url = url_dict['full_path'] + resource_url
            else:
                LOGGER.info('> 未知resource url: %s' % resource_url)

            # 解析文件URL，查看文件路径
            resource_url_dict = parse_url(resource_url)
            if not resource_url_dict:
                LOGGER.info('> 解析文件出错：%s' % resource_url)
                continue

            if resource_url_dict['domain'] != domain:
                LOGGER.info('> 该资源非同域名，不下载，不备份：%s' % resource_url)
                continue

            resource_dir = domain_dir + resource_url_dict['path']
            if resource_url_dict['file_name'] is None:
                resource_path = resource_dir + 'index.html'
            else:
                resource_path = resource_dir + resource_url_dict['file_name']

            # 已经放到队列里的忽略
            if resource_path in path_set:
                continue

            # 递归解析 html/htm/shtml
            if resource_url_dict['ext'] in ['html', 'htm', 'shtml', 'css']:
                # LOGGER.info("parse_resource_url, level {}".format(level))
                parse_resource_url(resource_url, level)

            path_set.add(resource_path)
            download_queue.put((resource_url, resource_path))

    parse_resource_url(root_url, 0)

# producer 
# 1. 从 download_queue 中获取要下载的文件
# 2. 下载文件
# 3. 将要上传的文件 put 到 upload_queue 
def producer(file_queue: Queue, download_queue: Queue, producer_idx: int):
    while True:
        if download_queue.empty():
            continue
        src, dst = download_queue.get()
        download_file(src, dst)
        file_queue.put(dst)
        download_queue.task_done()


# consumer
# 1. 从 upload_queue 中获取要上传到 OSS 的文件
# 2. 上传到 OSS
# 3. 预热目标文件
def consumer(file_queue: Queue, bucket: oss2.Bucket, client: AcsClient):
    while True:
        if file_queue.empty():
            continue 
        file_path = file_queue.get()
        object_name = file_path[len(LOCAL_PATH):]
        # LOGGER.info(
        #     "start to backup matched file = {}".format(object_name))
        if not os.path.exists(file_path):
            LOGGER.error(f"备份文件{file_path}不存在")
        if bucket is not None and os.path.exists(file_path):
            # LOGGER.info(f"备份成功:{object_name}")
            bucket.put_object_from_file(object_name, file_path)

        # 预热目标到CDN域名
        if client is not None and "WARMUP_DOMAIN" in os.environ and os.environ["WARMUP_DOMAIN"] != "unknown":
            cdn_domain = os.environ["WARMUP_DOMAIN"]
            request = CommonRequest()
            request.set_accept_format('json')
            request.set_domain('cdn.aliyuncs.com')
            request.set_method('POST')
            request.set_protocol_type('https')  # https | http
            request.set_version('2018-05-10')
            request.set_action_name('PushObjectCache')
            cdn_url = cdn_domain + \
                urllib.parse.urlparse('http://' + object_name).path
            request.add_query_param('ObjectPath', cdn_url)

            response = client.do_action(request)
            LOGGER.info('PushObjectCache: ' + cdn_url +
                        ', and returned: ' + str(response, encoding='utf-8'))
        file_queue.task_done()


# a decorator for LOGGER.info the excute time of a function
def print_excute_time(func):
    def wrapper(*args, **kwargs):
        local_time = time.time()
        ret = func(*args, **kwargs)
        LOGGER.info('current Function [%s] excute time is %.2fs' %
                    (func.__name__, time.time() - local_time))
        return ret

    return wrapper

def init_bucket_and_client(context):
    creds = context.credentials

    oss_auth = oss2.StsAuth(
        creds.access_key_id,
        creds.access_key_secret,
        creds.security_token)
    # 备份目标到OSS
    backup_origin = os.environ['BACKUP_ORIGIN']
    m = re.search(r'(.*).oss-(.*).aliyuncs.com', backup_origin)
    if m is None:
        LOGGER.error(
            "Backup origin {} is not a valid oss domain".format(backup_origin))
        raise ValueError(
            "Backup origin {} is not a valid oss domain".format(backup_origin))

    bucket_name = m.group(1)
    region = m.group(2)
    endpoint = 'oss-' + region + '.aliyuncs.com:'
    # endpoint = 'oss-cn-hangzhou-internal.aliyuncs.com'
    bucket = oss2.Bucket(oss_auth, endpoint, bucket_name)
    client = None
    if "WARMUP_DOMAIN" in os.environ and os.environ["WARMUP_DOMAIN"] != "unknown":
        cdn_domain = os.environ["WARMUP_DOMAIN"]
        cdn_auth = StsTokenCredential(
            creds.access_key_id,
            creds.access_key_secret,
            creds.security_token)
        client = AcsClient(region_id=context.region,
                           credential=cdn_auth)
    return bucket, client



@print_excute_time
def handler(event, context):
    # 定时触发器，事件内容没啥实际意义
    LOGGER.info(event)
    # 每次任务均需重置
    global path_set, DOWNLOADED_FILE_LIST
    path_set.clear()
    DOWNLOADED_FILE_LIST.clear()

    if "MAX_FETCH_LEVEL" in os.environ:
        max_level = int(os.environ['MAX_FETCH_LEVEL'])
    else:
        max_level = 0
    
    bucket, client = init_bucket_and_client(context)


    # 备份源站（域名入口）
    # url = 'http://www.cgbchina.com.cn/index.html'
    # url = 'http://www.peersafe.cn/index.html'
    url = os.environ['ORIGIN']
    root_path = urllib.parse.urljoin(LOCAL_PATH, parse_url(url)['domain'])
    if os.path.exists(root_path):
        shutil.rmtree(root_path)

    download_queue = Queue()
    upload_queue = Queue()

    parse_root_resource_url(url, max_level, download_queue)

    # 开始生产
    for idx in range(PRODUCER_NUM):
        t = threading.Thread(target=producer, args=(upload_queue, download_queue, idx))
        t.setDaemon(True)
        t.start()

    # 开始消费
    for _ in range(CONSUMER_NUM):
        t = threading.Thread(target=consumer, args=(upload_queue, bucket, client))
        t.setDaemon(True)
        t.start()
    
    
    download_queue.join()
    LOGGER.info("Download Queue Join Done!")
    upload_queue.join()
    LOGGER.info("Upload Queue Join Done!")

    return dict(download_num=len(set(DOWNLOADED_FILE_LIST)), success=True, remain_num=upload_queue.qsize())