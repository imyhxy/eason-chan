#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
from pprint import pprint
from urllib import request


class Lyric(object):
    def __init__(self, lyric_list):
        self.lyric = []
        self.modified = False
        self.singer = ''
        self.composer = ''
        self.songwriter = ''

        for s in lyric_list:
            if s.startswith("作词"):
                s.strip(' 作词： ')
                self.songwriter = s
            elif s.startswith('作曲'):
                s.strip(' 作曲： ')
                self.composer = s
            elif s.startswith('歌手'):
                s.strip(' 歌手： ')
                self.singer = s
            elif '：' in s:
                continue
            else:
                self.lyric.append(s)

    def show(self):
        print('singer: ', self.singer)
        print('composer: ', self.composer)
        print('songwriter: ', self.songwriter)
        pprint(self.lyric)


def get_lyric_by_id(music_id):
    url = 'http://music.163.com/api/song/lyric?os=pc&id=' + str(music_id) + '&lv=-1&kv=-1&tv=-1'
    req = request.Request(url)
    page = request.urlopen(req).read()
    lyric = json.loads(page, encoding='utf-8')['lrc']['lyric']

    pat = re.compile(r'\[[\w\d:.]+\]')
    lyric = re.sub(pat, '', lyric)
    res = [s.strip() for s in lyric.split('\n')]

    return Lyric(res)


if __name__ == '__main__':
    test_id = 27483201
    lyric = get_lyric_by_id(test_id)
    lyric.show()
