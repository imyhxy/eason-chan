#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import pickle
import re
from base64 import encodebytes, decodebytes
from collections import namedtuple
from pprint import pprint
from time import sleep
from urllib import request
from urllib.error import URLError
from urllib.request import Request

from bs4 import BeautifulSoup

CURR_FOLDER = os.path.dirname(__file__)


class NetEase(object):
    head = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3626.121 Safari/537.36'}

    def get_url(self, url, decode=True):
        urlfile = self.url_to_file(url)
        urlpath = os.path.join(CURR_FOLDER, 'cached', urlfile)
        if os.path.exists(urlpath):
            with open(urlpath, 'rb') as f:
                url_bytes = pickle.load(f)
                if decode:
                    return url_bytes.decode('utf-8')
                else:
                    return url_bytes

        self.req = Request(url, headers=self.head)
        ret = ''
        for _ in range(3):
            try:
                ret = request.urlopen(self.req).read()

                urlfolder = os.path.join(CURR_FOLDER, 'cached')
                if not os.path.exists(urlfolder):
                    os.makedirs(urlfolder)

                with open(urlpath, 'wb') as f:
                    pickle.dump(ret, f, pickle.HIGHEST_PROTOCOL)
                break
            except URLError:
                print('WARNING: timeout at {:s}'.format(url))
                sleep(30)
        if decode:
            return ret.decode('utf-8')
        else:
            return ret

    def to_json(self):
        raise NotImplementedError

    def url_to_file(self, url):
        table = str.maketrans(':&/=?%+-*#$@!`~[]{}|<>,.', '________________________')
        return url.translate(table)

    @staticmethod
    def _to_filename(name):
        name = str(name)
        ret = []
        _flag = False
        for s in name.lower().strip():
            if ord(s) < 256:
                if not 97 <= ord(s) <= 122:
                    if not _flag:
                        ret.append('_')
                        _flag = True
                    continue
            ret.append(s)
            _flag = False

        return ''.join(ret)


class Singer(NetEase):
    def __init__(self, singer_id, eager=True):
        self.id = singer_id
        if eager:
            self.get_info()
            self.get_all_albums()

    def get_info(self):
        self.url = 'https://music.163.com/artist?id=' + str(self.id)
        soup = BeautifulSoup(self.get_url(self.url), 'html.parser')
        self.name = soup.find('h2', id='artist-name').text.strip()
        if soup.find('h3', id='artist-alias').text.strip():
            self.alias = soup.find('h3', id='artist-alias').text.strip()
        else:
            self.alias = self.name

    def get_all_albums(self):
        self.get_all_albums_id()

        self.albums = []
        num_albums = len(self._album_ids)
        for idx, album_id in enumerate(self._album_ids):
            album = Album(album_id, eager=False)
            print('Analyzed album: {:s} ({:d}/{:d}).'.format(album.name, idx + 1, num_albums))
            album.get_info()
            self.albums.append(album)

    def get_all_albums_id(self):
        self._album_ids = []
        url = 'http://music.163.com/artist/album?id=' + \
              str(self.id) + '&limit=999&offset=0'
        content = self.get_url(url)
        soup = BeautifulSoup(content, 'html.parser')

        curr_albums = soup.find_all(
            'div', attrs={'class': 'u-cover u-cover-alb3'})

        for album in curr_albums:
            albums_id = int(album.find('a', attrs={'class': 'msk'})[
                                'href'].split('=')[-1])
            self._album_ids.append(albums_id)

    def to_json(self):
        return {
            'id': self.id,
            'url': self.url,
            'name': self.name,
            'alias': self.alias,
            'albums': [al.to_json() for al in self.albums],
            'album_ids': self._album_ids
        }

    @classmethod
    def from_json(cls, json_con):
        si = cls(0, eager=False)
        si.id = json_con['id']
        si.url = json_con['url']
        si.name = json_con['name']
        si.alias = json_con['alias']
        si.albums = [Album.from_json(al) for al in json_con['albums']]
        si._album_ids = json_con['album_ids']

        return si

    def build_doc(self):
        self.doc_root = os.path.join(CURR_FOLDER, '..',
                                     'docs', self._to_filename(self.alias))

        if not os.path.exists(self.doc_root):
            os.makedirs(self.doc_root)

        self.templates = self._read_template()
        self._build_singer()

    def _build_singer(self):
        with open(os.path.join(self.doc_root, 'README.md'), 'w') as f:
            f.write(self.templates.get(self._to_filename(self.alias), ''))
            f.write('\n## Albums\n\n')
            for al in self.albums:
                al_readme = os.path.join('albums',
                                         self._to_filename(al.name) + f'_{al.id}',
                                         'README.md')
                al._build_album(self.doc_root)
                f.write('* [{:s}]({:s})\n'.format(al.name, al_readme))

    def _read_template(self, folder='template'):
        template_root = os.path.join(CURR_FOLDER, folder)

        templates = {}
        for f in os.listdir(template_root):
            with open(os.path.join(template_root, f)) as fp:
                templates[f.split('.')[0]] = fp.read()
        return templates


class Album(NetEase):
    def __init__(self, album_id, eager=True, rebuild=False):
        if not rebuild:
            self.id = album_id
            self.url = 'https://music.163.com/album?id=' + str(self.id)
            content = self.get_url(self.url)
            self.soup = BeautifulSoup(content, 'html.parser')
            self.name = self.soup.find('h2', attrs={'class': 'f-ff2'}).text.strip()

            if eager:
                self.get_info()

    def get_info(self):
        self._img_link = self.soup.find('meta', attrs={'property': 'og:image'})['content']
        self._img_type = self._img_link.split('.')[-1]
        self.img = self.get_url(self._img_link, decode=False)
        self.singers = [s.strip() for s in self.soup.find(
            'b', text='歌手：').next_sibling['title'].split('/')]

        try:
            self.time = self.soup.find('b', text='发行时间：').next_sibling.strip()
        except AttributeError:
            self.time = ''

        try:
            self.company = self.soup.find('b', text='发行公司：').next_sibling.strip()
        except AttributeError:
            self.company = ''

        if self.soup.find('div', attrs={'id': 'album-desc-more'}):
            self.description = [s.text.strip() for s in self.soup.find(
                'div', attrs={'id': 'album-desc-more'}).find_all('p')]
        elif self.soup.find('div', attrs={'id': 'album-desc-dot'}):
            self.description = [s.text.strip() for s in self.soup.find(
                'div', attrs={'id': 'album-desc-dot'}).find_all('p')]
        else:
            self.description = ''
        self.num_comments = int(self.soup.find('span', id='cnt_comment_count').text.strip())
        self.num_shared = int(self.soup.find('a', attrs={'class': 'u-btni u-btni-share'})['data-count'])
        self.num_songs = int(self.soup.find('span', class_='sub s-fc3',
                                            text=re.compile('\d+.{2}')).text.strip()[:-2])

        jsong = json.loads(self.soup.find('textarea', id='song-list-pre-data').text)
        SongInfo = namedtuple('SongInfo', ['id', 'duration', 'score'])
        self._songs_info = [SongInfo(s['id'], s['duration'], s['score']) for s in jsong]
        self._get_all_songs()

    def _get_all_songs(self):
        self.songs = []

        num_song = len(self._songs_info)
        for idx, s in enumerate(self._songs_info):
            song = Song(s.id, s.duration, s.score, self.time)
            self.songs.append(song)
            print('\tFetched song: {:s} ({:d}/{:d}).'.format(song.name, idx + 1, num_song))

    def to_json(self):
        return {
            'id': self.id,
            'url': self.url,
            'img': encodebytes(self.img).decode('ascii'),
            'img_link': self._img_link,
            'name': self.name,
            'singers': self.singers,
            'company': self.company,
            'time': self.time,
            'description': self.description,
            'num_comments': self.num_comments,
            'num_shared': self.num_shared,
            'num_song': self.num_songs,
            'songs_info': [s._asdict() for s in self._songs_info],
            'songs': [so.to_json() for so in self.songs]
        }

    @classmethod
    def from_json(cls, json_con):
        SongInfo = namedtuple('SongInfo', ['id', 'duration', 'score'])
        al = cls(0, rebuild=True)
        al.id = json_con['id']
        al.url = json_con['url']
        al.img = decodebytes(json_con['img'].encode('ascii'))
        al._img_link = json_con['img_link']
        al.name = json_con['name']
        al.singers = json_con['singers']
        al.company = json_con['company']
        al.time = json_con['time']
        al.description = json_con['description']
        al.num_comments = json_con['num_comments']
        al.num_shared = json_con['num_shared']
        al.num_songs = json_con['num_song']
        al._songs_info = [SongInfo(s['id'], s['duration'], s['score']) for s in json_con['songs_info']]
        al.songs = [Song.from_json(s) for s in json_con['songs']]

        return al

    def _build_album(self, singer_root):
        al_root = os.path.join(singer_root, 'albums',
                               self._to_filename(self.name) + '_{:d}'.format(self.id))
        al_readme = os.path.join(al_root, 'README.md')

        # for album image
        al_imgs_folder = os.path.join(al_root, 'imgs')
        if not os.path.exists(al_imgs_folder):
            os.makedirs(al_imgs_folder)

        al_img_path = os.path.join(al_imgs_folder, self._to_filename(self.name) + '.jpg')
        with open(al_img_path, 'wb') as fp:
            fp.write(self.img)

        # for songs
        al_songs = os.path.join(al_root, 'songs')
        if not os.path.exists(al_songs):
            os.makedirs(al_songs)

        with open(al_readme, 'w') as f:
            f.write('<p align=\"center\">\n'
                    '\t<img src=\"{:s}\" alt=\"album_img\" />\n'
                    '</p>\n\n'.format(os.path.join('imgs', os.path.basename(al_img_path))))
            f.write(f'# [{self.name}]({self.url})\n\n')
            f.write(f'* 时间：{self.time}\n')
            f.write('* 歌手：{:s}\n'.format('，'.join(self.singers)))
            f.write(f'* 唱片公司：{self.company}\n')

            f.write('## Songs\n\n')
            for so in self.songs:
                so_path = os.path.join('songs', self._to_filename(so.name) + f'_{so.id}')
                so._build_song(al_songs)
                f.write('* [{:s}]({:s})\n'.format(so.name, os.path.join(so_path, 'README.md')))

            f.write('## Appendix\n\n')
            f.write('### Description\n\n')
            f.write('\n\n'.join(self.description))
            f.write('\n\n')

            f.write('### Score\n\n')
            f.write('|歌曲数|评论数|分享数|\n')
            f.write('|:---:|:---:|:---:|\n')
            f.write(f'|{self.num_songs}|{self.num_comments}|{self.num_shared}|\n\n')

            f.write('|歌名|分数|\n')
            f.write('|:---:|:---:|\n')
            sorted_songs = sorted(self.songs, key=lambda x: x.score, reverse=True)
            for so in sorted_songs:
                f.write(f'|{so.name}|{so.score}\n')


class Song(NetEase):
    def __init__(self, s, duration=0, score=0, time=None, eager=True):
        self.id = s
        if eager:
            self.url = 'https://music.163.com/song?id=' + str(s)
            soup = BeautifulSoup(self.get_url(self.url), 'html.parser')

            self.name = soup.find('em', class_='f-ff2').text
            self.duration = duration
            self.score = score
            self.singers = [s.text.strip() for s in
                            soup.find_all('a', class_='s-fc7', href=re.compile(r'/artist\?id.*'))]
            self.album = soup.find('a', class_='s-fc7', href=re.compile(r'/album\?id.*')).text.strip()
            self.time = time or json.loads(soup.find('script',
                                                     class_='application/ld+json').text)['pubDate'].split('T')[0]
            self.ric = Lyric(self.id)

    def to_json(self):
        return {
            'id': self.id,
            'url': self.url,
            'name': self.name,
            'time': self.time,
            'score': self.score,
            'album': self.album,
            'singers': self.singers,
            'duration': self.duration,
            'ric': self.ric.to_json(),
        }

    def _build_song(self, album_root):
        song_root = os.path.join(album_root, self._to_filename(self.name) + f'_{self.id}')

        if not os.path.exists(song_root):
            os.makedirs(song_root)

        so_readme = os.path.join(song_root, 'README.md')

        with open(so_readme, 'w') as f:
            ric = self.ric
            f.write(f'# [{self.name}]({self.url})\n\n')
            if ric.singer:
                f.write(f'* 歌手：{ric.singer}\n')
            if ric.songwriter:
                f.write(f'* 作词：{ric.songwriter}\n')
            if ric.composer:
                f.write(f'* 作曲：{ric.composer}\n')
            if ric.arrangement:
                f.write(f'* 编曲：{ric.arrangement}\n')

            flag = False
            for line in ric.lyric:
                if not line:
                    if flag:
                        flag = False
                        continue
                    else:
                        flag = True
                f.write('* {:s}\n'.format(line.strip()))

            f.write('\n\n---\n\n')
            f.write('## Appendix\n\n')
            f.write('|歌名|分数|时长|时间|\n')
            f.write('|:---|:---:|---:|---:|\n')
            f.write(f'|{self.name}|{self.score}|{self.elapse}|{self.time}\n\n')

            f.write('*modified: {:s}*'.format(str(self.ric.modified)))


    @property
    def elapse(self):
        sec = self.duration // 1000
        return '{:d}:{:d}'.format(*divmod(sec, 60))

    @classmethod
    def from_json(cls, json_con):
        so = Song(0, eager=False)
        so.id = json_con['id']
        so.url = json_con['url']
        so.name = json_con['name']
        so.duration = json_con['duration']
        so.score = json_con['score']
        so.singers = json_con['singers']
        so.album = json_con['album']
        so.time = json_con['time']
        so.ric = Lyric.from_json(json_con['ric'])

        return so


class Lyric(NetEase):
    def __init__(self, music_id, eager=True):
        self.id = music_id
        if eager:
            self.lyric = []
            self.modified = False
            self.singer = ''
            self.composer = ''
            self.songwriter = ''
            self.arrangement = ''

            self.url = 'http://music.163.com/api/song/lyric?os=pc&id=' + \
                       str(music_id) + '&lv=-1&kv=-1&tv=-1'
            content = self.get_url(self.url)
            if json.loads(content).get('nolyric', False):
                lyric = '纯音乐'
            elif json.loads(content).get('uncollected', False):
                lyric = '无歌词'
            else:
                lyric = json.loads(content)['lrc']['lyric']

            pat = re.compile(r'\[[\w\d:.]+\]')
            lyric = re.sub(pat, '', lyric)
            res = [s.strip() for s in lyric.split('\n')]

            for s in res:
                if s.startswith("作词"):
                    s = s.strip(' 作词:： ')
                    self.songwriter = s
                elif s.startswith('作曲'):
                    s = s.strip(' 作曲:： ')
                    self.composer = s
                elif s.startswith('歌手'):
                    s = s.strip(' 歌手:： ')
                    self.singer = s
                elif s.startswith('编曲'):
                    s = s.strip(' 编曲:： ')
                    self.arrangement = s
                elif '：' in s:
                    continue
                else:
                    self.lyric.append(s)

    def to_json(self):
        return {
            'id': self.id,
            'url': self.url,
            'modified': self.modified,
            'singer': self.singer,
            'composer': self.composer,
            'songwriter': self.songwriter,
            'arrangement': self.arrangement,
            'lyric': self.lyric
        }

    @classmethod
    def from_json(cls, json_con):
        ly = cls(0, eager=False)
        ly.id = json_con['id']
        ly.url = json_con['url']
        ly.modified = json_con['modified']
        ly.singer = json_con['singer']
        ly.composer = json_con['composer']
        ly.songwriter = json_con['songwriter']
        ly.arrangement = json_con['arrangement']
        ly.lyric = json_con['lyric']

        return ly

    def show(self):
        print('singer: ', self.singer)
        print('composer: ', self.composer)
        print('songwriter: ', self.songwriter)
        pprint(self.lyric)


def self_check(con):
    for key, val in con.items():
        if isinstance(val, dict):
            self_check(val)
        elif isinstance(val, list):
            for v in val:
                if isinstance(v, dict):
                    self_check(v)
        elif isinstance(val, bytes):
            print(key)

def main(singer_id, fetch=True, build_doc=True):
    if not fetch:
        assert os.path.exists(os.path.join(CURR_FOLDER, 'json_src', str(singer_id) + '.json'))

    json_src = os.path.join(CURR_FOLDER, 'json_src')
    if not os.path.exists(json_src):
        os.makedirs(json_src)

    if fetch:
        singer = Singer(singer_id)
        with open(os.path.join(json_src, f'{singer_id}.json'), 'w') as fp:
            json.dump(singer.to_json(), fp, indent=4, sort_keys=True)
    else:
        with open(os.path.join(CURR_FOLDER, 'json_src', str(singer_id) + '.json')) as f:
            json_con = json.load(f)
            singer = Singer.from_json(json_con)
    if build_doc:
        singer.build_doc()



if __name__ == '__main__':
    singer_id = 2116  # eason chan
    # singer_id = 5781  # chou
    main(singer_id, fetch=False)

