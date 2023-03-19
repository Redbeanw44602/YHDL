import os
import requests
import re
import base64
import shutil
import time
import math
import sys

from pathlib import PurePosixPath
from urllib.parse import urlparse
from lxml import etree

SAVE_PATH = 'downloads'
TEMP_PATH = 'temp'

def terminate(str:str = None):
    if str:
        print(str)
    os.system('pause')
    exit(-1)

def printLogo():
    print("""┌──────────────────────────┐
│     YHPDM Downloader     │
└──────────────────────────┘
Version: 1.0.0
Author: RedbeanW
Tested: http://www.dm590.com/
""")

def initDirs():
    os.makedirs(SAVE_PATH, exist_ok=True)
    initTemp()

def initTemp():
    shutil.rmtree(TEMP_PATH, ignore_errors=True)
    os.makedirs(TEMP_PATH, exist_ok=True)

class YHPDM():

    """ Use the play link of the drama (the HTML contains playJs information) to get the video m3u8 download link. """
    def getUrl(self, singleChapterPlayLink: str):
        request = requests.get(singleChapterPlayLink)
        content = request.content.decode()

        playJs = re.search(r'var paly_js = "(.*?)";', content)
        # videoType = re.search(r'var bjtype = "(.*?)";', content)
        # itemId = re.search(r'var itemid = "(.*?)";', content)

        if playJs:
            playJs = playJs.group(1)
        else:
            return None

        return base64.b64decode(
            playJs.replace('_', '+')
            .replace('.', '=')
            .replace('-', 'a')).decode()
    
    """ Parses a website page, and returns the obtained drama information and playback links. """
    def parse(self, fullWorkPlayLink: str):
        request = requests.get(fullWorkPlayLink)
        content = request.content.decode()

        page = etree.HTML(content, parser=etree.HTMLParser(encoding='utf-8'))
        
        # requiredData
        try:
            info = page.xpath('//div[@class="info"]')[0]
            name = info.xpath('//dt[@class="name"]/text()')[0]
            status = info.xpath('//dt[@class="name"]/span[1]/text()')[0]
            channelWithPlaylist = page.xpath('//ul[@class="urlli"]/div')[0]
        except:
            return None

        # metaData
        try:
            type = info.xpath('//dd[1]/text()')[0]
            era = info.xpath('//dd[2]/text()')[0]
            describe = info.xpath('//div[@class="des2"]/text()')[1]
            tags = info.xpath('//dd[3]/text()')[1]
            if tags.find('...') != -1:
                tags = tags[:tags.find('...')]
            if describe.find('\n') != -1:
                describe = describe[:describe.find('\n')]
        except:
            pass
        
        playinfo = []
        
        # structure: playinfo -> channels -> playlist -> entity
        for channel in channelWithPlaylist: # <ul> ul_playlist_1, channel 1
            chal = {}
            for full in channel:
                for entity in full:
                    chal[entity.xpath('text()')[0]] = entity.xpath('@href')[0]
            playinfo.append(chal)
        
        return {
            'name': name,
            'status': status,
            'metainfo': {
                'type': type,
                'era': era,
                'describe': describe,
                'tags': tags
            },
            'playinfo': playinfo
        }

def parentUrl(url: str):
    return str(PurePosixPath(url).parent).replace(':/', '://')

id = 0
def getId():
    global id
    id += 1
    return id

def getAllTs(url: str) -> list:
    ret = []
    source = requests.get(url).content.decode()
    base = parentUrl(url)
    ignoring = None
    for line in source.split('\n'):
        if line.startswith('#EXT-X-DISCONTINUITY'):
            ignoring = True if not ignoring else False
        if ignoring == False: # ignore `None`
            continue
        durl = base + '/' + line
        if durl.lower().endswith('.m3u8'):
            ret += getAllTs(durl)
        elif durl.lower().endswith('.ts'):
            ret.append(durl)
    return ret

def saveFullM3U8(url: str, saveName: str):
    if not url.lower().endswith('m3u8'):
        print('non-m3u8 video download is not supported at the moment, please contact the author.')
        print('url = %s' % url)
        return None

    orderedTs = getAllTs(url)
    count = 0
    allcount = len(orderedTs)
    tsIdList = []
    blockNum = 30
    
    initTemp()
    for ts in orderedTs:
        success = False
        while not success:
            try:
                count += 1
                status = '正在下载(%s/%s)' % (count, allcount)
                prog = math.floor(count / allcount * blockNum)
                print('\r%s -> %s %s%s' % (saveName, status, '▰' * prog, '▱' * (blockNum - prog)), end=' ')
                sys.stdout.flush()
                id = getId()
                tsIdList.append('%s/%s.ts' % (TEMP_PATH, id))
                session = requests.session()
                response = session.get(ts, stream=True)
                with open('%s/%s.ts' % (TEMP_PATH, id), 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024 * 1024): # 1Mb
                        f.write(chunk)
                session.close()
                time.sleep(0.5)
                success = True
            except:
                print('出错了！将在 30s 后重新下载该块。',' ' * 15)
                time.sleep(30)
    
    print('\r%s -> %s %s' % (saveName, '正在合并', '▰' * blockNum), end=' ' * 30)
    os.system('ffmpeg.exe -nostdin -i "concat:%s" -c copy "%s/%s.mp4" 2>nul' % ('|'.join(_ for _ in tsIdList), SAVE_PATH, saveName))
    print('\r%s -> %s %s%s' % (saveName, '下载完成', '▰' * blockNum, ' ' * 15))

if __name__ == '__main__':

    printLogo()
    initDirs()

    pdm = YHPDM()

    link = input('请输入番剧链接，请注意是包含选集、简介等信息的页面，而不是某一集的播放页面: ')
    # link = ''

    if not os.path.exists('ffmpeg.exe'):
        terminate('# 请将FFmpeg与本软件放在同一目录！')

    print('# 正在解析数据...')
    drama = pdm.parse(link)
    if not drama:
        terminate('# 番剧信息解析失败！')
    
    tmp = urlparse(link)
    website = '%s://%s' % (tmp.scheme, tmp.netloc)

    print('# 番剧信息解析成功！')
    print("""
————————————————————————————————————————————————————————————————
作品名: %s (%s)
类型: %s
年代: %s
标签: %s
剧情: %s
————————————————————————————————————————————————————————————————
""" % (drama['name'], drama['status'], drama['metainfo']['type'], drama['metainfo']['era'], drama['metainfo']['tags'], drama['metainfo']['describe']))

    lines = len(drama['playinfo'])
    channel = int(input('获取到 {0} 条播放线路，使用 (1-{0}): '.format(lines)))
    if channel > lines or channel < 1:
        terminate('# 请输入 1 ~ %d 以内的数字！' % lines)

    full = drama['playinfo'][channel]
    print('# 可用 (%d个): %s。\n' % (len(full), ','.join(_ for _ in full)))
    chosed = input('请输入需要下载的内容，多个使用逗号分割 (如: 第1集,第2集)，直接回车以全部下载: ').replace('，',',').split(',')
    if not (len(chosed) == 1 and chosed[0] == ''):
        for i in list(full):
            if i not in chosed:
                full.pop(i)

    for name, plink in full.items():
        dlink = pdm.getUrl(website + plink)
        fullName = '%s %s' % (drama['name'], name)
        if not dlink:
            print('# 获取下载链接失败 -> %s' % fullName)
            continue
        saveFullM3U8(dlink, fullName)
        time.sleep(1)
