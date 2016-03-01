# coding=utf-8
'''
Torrent-tv.ru Playlist Downloader Plugin
http://ip:port/ttv
'''
import re
import logging
import urllib2
import time
import gevent
from modules.PluginInterface import AceProxyPlugin
from modules.PlaylistGenerator import PlaylistGenerator
import config.ttv as config


class Ttv(AceProxyPlugin):

    # ttvplaylist handler is obsolete
    handlers = ('ttv', 'ttvpl')

    logger = logging.getLogger('plugin_ttv')
    playlist = None
    playlisttime = None
    CATEGORIES = {
        '1': 'Фильмы',
        '2': 'Музыка',
        '3': 'Детские',
        '4': 'Спорт',
        '5': 'Общие',
        '6': 'Познавательные',
        '7': 'Новостные',
        '8': 'Развлекательные',
        '9': 'Мужские',
        'a': 'Региональные',
        'b': 'Религиозные',
        'x': 'Для взрослых'
    }
    
    def __init__(self, AceConfig, AceStuff):
        if config.updateevery:
            self.downloadPlaylist()
            gevent.spawn(self.playlistTimedDownloader)

    def playlistTimedDownloader(self):
        while True:
            gevent.sleep(config.updateevery * 60)
            self.downloadPlaylist()

    def downloadPlaylist(self):
        try:
            Ttv.logger.debug('Trying to download playlist for ttv' + config.url)
            req = urllib2.Request(config.url, headers={'User-Agent' : "Magic Browser"})
            Ttv.playlist = urllib2.urlopen(
                req, timeout=10).read()
            Ttv.playlisttime = int(time.time())
        except:
            Ttv.logger.error("Can't download playlist!")
            return False

        return True

    def handle(self, connection):
        # 30 minutes cache
        if not Ttv.playlist or (int(time.time()) - Ttv.playlisttime > 30 * 60):
            if not self.downloadPlaylist():
                connection.dieWithError()
                return

        hostport = connection.headers['Host']

        connection.send_response(200)
        connection.send_header('Content-Type', 'application/x-mpegurl')
        connection.end_headers()

        # Match playlist with regexp
        matches = re.finditer(r',(?P<name>\S.+) \((?P<group>.+)\)\n(?P<url>^.+$)',
                              Ttv.playlist, re.MULTILINE)
        
        add_ts = False
        try:
            if connection.splittedpath[2].lower() == 'ts':
                add_ts = True
        except:
            pass
        
        g_filter = False
        g_name = ''
        try:
            if connection.splittedpath[2].lower()[:1] == 'g':
                Ttv.logger.debug('Group ' + connection.splittedpath[2].lower() + ' - ' + connection.splittedpath[2].lower()[1:2])
                Ttv.logger.debug(Ttv.CATEGORIES['1'])
                g_name = Ttv.CATEGORIES[connection.splittedpath[2].lower()[1:2]]
                g_filter = True
                Ttv.logger.debug('Group name ' + g_name)
        except:
            pass

        playlistgen = PlaylistGenerator()
        for match in matches:
            itemdict = match.groupdict()
            if not(g_filter) or g_name == itemdict['group']:
                name = itemdict.get('name').decode('UTF-8')
                logo = config.logomap.get(name)
                if logo is not None:
                    itemdict['logo'] = logo
                playlistgen.addItem(itemdict)

        header = '#EXTM3U url-tvg="%s" tvg-shift=%d\n' %(config.tvgurl, config.tvgshift)
        connection.wfile.write(playlistgen.exportm3u(hostport, add_ts=add_ts, header=header))
