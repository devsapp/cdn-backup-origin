# -*- coding: utf-8 -*-

import logging
import os
import re
import time
import urllib.parse
import urllib.request
from functools import reduce
import oss2
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
from aliyunsdkcore.auth.credentials import AccessKeyCredential
from aliyunsdkcore.auth.credentials import StsTokenCredential

LOGGER = logging.getLogger()

# 正则表达式预编译
# 这里涉及到了非贪婪匹配
# "" or ''
# ?: 取消分组
# ?表示懒惰匹配，尽可能匹配少的字符
# ((?:/[a-zA-Z0-9.]*?)*)
# ((?:/[a-zA-Z0-9.]*)*?)
REG_URL = r'^(https?://|//)?((?:[a-zA-Z0-9-_]+\.)+(?:[a-zA-Z0-9-:]+))((?:/[-.a-zA-Z0-9]*?)*)((?<=/)[-_a-zA-Z0-9]+(?:\.([a-zA-Z0-9]+))+)?((?:\?[a-zA-Z0-9%&=]*)*)$'
REG_RESOURCE_TYPE = r'(?:href|src|data\-original|data\-src)=["\'](.+?\.(?:html|htm|shtml|js|css|jpg|jpeg|png|gif|svg|ico|ttf|woff2|asp|jsp|php|perl|cgi))[a-zA-Z0-9\?\=\.]*["\']'

reg_url = re.compile(REG_URL)
reg_resource = re.compile(REG_RESOURCE_TYPE, re.S)

# 去重，避免重复下载
downloaded_list = []

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
        full_path = res.group(1) + res.group(2) + res.group(3)

        if not path.endswith('/'):
            path = path + '/'
            full_path = full_path + '/'
        return dict(
            base_url=res.group(1) + res.group(2),
            full_path=full_path,
            protocol=res.group(1),
            domain=res.group(2),
            path=path,
            file_name=res.group(4),
            ext=res.group(5),
            params=res.group(6)
        )


'''
解析URL 页面
'''


def parse_page(page_path):
    if not page_path.endswith(('.html', '.htm', '.shtml')) \
            or not os.path.exists(page_path):
        return

    resource_list = []
    with open(page_path, 'r', encoding='utf-8', errors='ignore') as f:
        # 分析网页内容
        content = f.read()
        LOGGER.info('> %s 网站内容读取完毕，内容长度：%d' % (page_path, len(content)))

        # 解析网页内容，获取有效的链接
        content_list = re.split(r'\s+', content)
        for line in content_list:
            res_list = reg_resource.findall(line)
            if res_list is not None:
                resource_list = resource_list + res_list
    # 去重
    return reduce(lambda x, y: y in x and x or x + [y], resource_list, [])


'''
下载文件
'''


def download_file(src_url, dist_path):
    try:
        response = urllib.request.urlopen(src_url)
        if response is None or response.status != 200:
            return LOGGER.info('> 请求异常：%s' % src_url)
        data = response.read()

        f = open(dist_path, 'wb')
        f.write(data)
        f.close()

        LOGGER.info('>>>: %s 下载成功' % src_url)

    except Exception as e:
        LOGGER.info('下载报错：%s, %s' % (src_url, e))
        return False

    return True


'''
解析和备份URL 相关静态资源
'''


def parse_and_download_page(url, level):
    global downloaded_list
    global max_level

    # # 达到最大抓取层级，终止递归
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
    domain_dir = '/tmp/' + re.sub(r':', '-', domain)
    page_dir = domain_dir + url_dict['path']
    if not os.path.exists(page_dir):
        os.makedirs(page_dir)
    page_path = page_dir + page_name
    # 已下载或者下载出错，终止递归
    if page_path not in downloaded_list and download_file(url, page_path):
        downloaded_list.append(page_path)
    else:
        return

    # 解析备份入口页面内容，提取待备份的资源列表
    resource_list = parse_page(page_path)
    if not resource_list:
        return

    # 下载资源，要区分目录，不存在的话就创建
    for resource_url in resource_list:
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
        resource_path = resource_dir + resource_url_dict['file_name']

        # 已经下载过的内容忽略
        if resource_path in downloaded_list:
            continue

        # 递归解析 html/htm/shtml
        if resource_url_dict['ext'] in ['html', 'htm', 'shtml']:
            LOGGER.info("parse_and_download_page, level {}".format(level))
            parse_and_download_page(resource_url, level)

        if not os.path.exists(resource_dir):
            os.makedirs(resource_dir)

        # 下载文件
        if download_file(resource_url, resource_path):
            downloaded_list.append(resource_path)


# a decorator for LOGGER.info the excute time of a function
def print_excute_time(func):
    def wrapper(*args, **kwargs):
        local_time = time.time()
        ret = func(*args, **kwargs)
        LOGGER.info('current Function [%s] excute time is %.2f' %
                    (func.__name__, time.time() - local_time))
        return ret

    return wrapper


@print_excute_time
def handler(event, context):
    # 定时触发器，事件内容没啥实际意义
    LOGGER.info(event)
    # 每次任务均需重置
    global downloaded_list
    downloaded_list = []

    global max_level
    if "MAX_FETCH_LEVEL" in os.environ:
        max_level = int(os.environ['MAX_FETCH_LEVEL'])
    else:
        max_level = 0

    # 备份源站（域名入口）
    # url = 'http://www.cgbchina.com.cn/index.html'
    # url = 'http://www.peersafe.cn/index.html'
    url = os.environ['ORIGIN']
    parse_and_download_page(url, 0)
    LOGGER.info('总共下载了 %d 个资源' % len(downloaded_list))

    # 解析下载网页后备份和预热
    if (len(downloaded_list) > 0):
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
        # backup
        for tmp_file in downloaded_list:
            # /tmp/www.cgbchina.com.cn/index.html -> www.cgbchina.com.cn/index.html
            object_name = tmp_file[5:]
            LOGGER.info(
                "start to backup matched file = {}".format(object_name))
            if bucket is not None:
                bucket.put_object_from_file(object_name, tmp_file)

            # 预热目标到CDN域名
            if "WARMUP_DOMAIN" in os.environ and os.environ["WARMUP_DOMAIN"] != "unknown":
                cdn_domain = os.environ["WARMUP_DOMAIN"]
                cdn_auth = StsTokenCredential(
                    creds.access_key_id,
                    creds.access_key_secret,
                    creds.security_token)
                client = AcsClient(region_id=context.region,
                                   credential=cdn_auth)

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

    return dict(download_num=len(downloaded_list), success=True)
