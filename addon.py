# -*- coding: utf-8 -*-
import sys
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmc
import xbmcvfs
import traceback
import json
import os
import random
from urllib.parse import urlencode, parse_qsl

ADDON = xbmcaddon.Addon()
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('path'))
ADDON_DATA_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))

# Cache-Dateien
USER_CACHE_FILE = os.path.join(ADDON_DATA_PATH, 'video_metadata_cache.json')
PREBUILT_CACHE_FILE = os.path.join(ADDON_PATH, 'resources', 'cache', 'video_metadata_cache.json')

# Memory Cache
VIDEO_INFO_CACHE = {}

def get_url(**kwargs):
    return '{}?{}'.format(sys.argv[0], urlencode(kwargs))

def log(msg):
    xbmc.log('[MTV-REWIND] {}'.format(str(msg)), xbmc.LOGINFO)

def get_setting_bool(setting_id):
    """Liest Boolean-Setting aus."""
    return ADDON.getSettingBool(setting_id)

def ensure_addon_data_folder():
    """Stellt sicher dass der addon_data Ordner existiert."""
    if not xbmcvfs.exists(ADDON_DATA_PATH):
        xbmcvfs.mkdirs(ADDON_DATA_PATH)
        log('Created addon_data folder: {}'.format(ADDON_DATA_PATH))

def load_cache_from_disk():
    """Lädt den Metadaten-Cache von der Festplatte."""
    global VIDEO_INFO_CACHE
    try:
        if xbmcvfs.exists(PREBUILT_CACHE_FILE):
            with open(PREBUILT_CACHE_FILE, 'r', encoding='utf-8') as f:
                VIDEO_INFO_CACHE = json.load(f)
                log('Loaded {} cached video metadata entries from disk'.format(len(VIDEO_INFO_CACHE)))
                return True
    except Exception as e:
        log('Error loading cache: {}'.format(str(e)))
    return False

def save_cache_to_disk():
    """Speichert den Metadaten-Cache auf die Festplatte."""
    try:
        ensure_addon_data_folder()
        with open(PREBUILT_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(VIDEO_INFO_CACHE, f, ensure_ascii=False, indent=2)
        log('Saved {} video metadata entries to cache'.format(len(VIDEO_INFO_CACHE)))
        return True
    except Exception as e:
        log('Error saving cache: {}'.format(str(e)))
        return False

def get_playlists():
    """Gibt die eingebetteten Playlist-Daten zurueck."""
    try:
        from resources.lib.playlists_data import PLAYLISTS
        return PLAYLISTS
    except Exception as e:
        log('ERROR loading playlists: {}'.format(str(e)))
        return {}

def get_video_info_from_youtube(video_id, force_refresh=False):
    """Holt Video-Metadaten von YouTube via oEmbed API mit Caching."""
    if not force_refresh and video_id in VIDEO_INFO_CACHE:
        return VIDEO_INFO_CACHE[video_id]
    
    try:
        import urllib.request
        url = 'https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={}&format=json'.format(video_id)
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            title = data.get('title', '')
            author = data.get('author_name', '')
            
            if ' - ' in title:
                parts = title.split(' - ', 1)
                artist, song = parts[0].strip(), parts[1].strip()
            else:
                artist, song = author, title
            
            for phrase in ['(Official Video)', '(Official Music Video)', '[Official Video]', '(HD)', '(Explicit)']:
                song = song.replace(phrase, '')
            
            info = {
                'artist': artist,
                'title': song.strip(),
                'thumb': 'https://i.ytimg.com/vi/{}/mqdefault.jpg'.format(video_id),
                'poster': 'https://i.ytimg.com/vi/{}/hqdefault.jpg'.format(video_id),
                'plot': '{} - {}'.format(artist, song.strip())
            }
            VIDEO_INFO_CACHE[video_id] = info
            return info
    except:
        return {'artist': 'Unknown', 'title': 'Video ' + video_id, 'thumb': '', 'poster': '', 'plot': ''}

def list_channels(handle):
    """Zeigt die Hauptkategorien an."""
    playlists = get_playlists()
    channel_names = {
        '1stday': '1st Day (1981)', '70s': '1970s', '80s': '1980s', '90s': '1990s',
        '2000s': '2000s', '2010s': '2010s', '2020s': '2020s', 'trl': 'TRL',
        'raps': 'Yo! MTV Raps', 'metal': 'Headbangers Ball', 'unplugged': 'MTV Unplugged'
    }
    
    for cid in sorted(playlists.keys()):
        name = channel_names.get(cid, cid.title())
        item = xbmcgui.ListItem(label=name)
        item.setInfo('video', {'title': name, 'plot': '{} Videos'.format(len(playlists[cid]))})
        xbmcplugin.addDirectoryItem(handle, get_url(action='browse', channel=cid), item, True)
    
    xbmcplugin.endOfDirectory(handle)

def browse_channel(handle, channel_id):
    """Zeigt Videos eines Kanals an inklusive Shuffle-Option."""
    if not VIDEO_INFO_CACHE:
        load_cache_from_disk()
        
    playlists = get_playlists()
    if channel_id not in playlists:
        return

    video_ids = playlists[channel_id]

    # 1. Shuffle Button hinzufügen
    shuffle_item = xbmcgui.ListItem(label='[COLOR orange]➔ SHUFFLE ALL (Zufallswiedergabe)[/COLOR]')
    shuffle_item.setArt({'icon': 'DefaultMusicVideos.png'})
    shuffle_url = get_url(action='play_shuffle', channel=channel_id)
    xbmcplugin.addDirectoryItem(handle, shuffle_url, shuffle_item, False)

    # 2. Videos auflisten
    fetch_meta = get_setting_bool('fetch_metadata')
    for video_id in video_ids:
        if fetch_meta:
            info = get_video_info_from_youtube(video_id)
            label = '{} - {}'.format(info['artist'], info['title'])
        else:
            label = 'Video {}'.format(video_id)
            info = {'thumb': 'https://i.ytimg.com/vi/{}/mqdefault.jpg'.format(video_id), 'artist': 'VA', 'title': label}

        item = xbmcgui.ListItem(label=label)
        item.setArt({'thumb': info.get('thumb')})
        item.setInfo('video', {'title': info.get('title'), 'artist': [info.get('artist')]})
        url = 'plugin://plugin.video.youtube/play/?video_id={}'.format(video_id)
        xbmcplugin.addDirectoryItem(handle, url, item, False)

    xbmcplugin.endOfDirectory(handle)

def play_shuffle(channel_id):
    """Mischt die Videos und startet die Wiedergabe."""
    playlists = get_playlists()
    if channel_id not in playlists:
        return

    vids = list(playlists[channel_id])
    random.shuffle(vids)
    
    playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
    playlist.clear()
    
    for vid in vids:
        url = 'plugin://plugin.video.youtube/play/?video_id={}'.format(vid)
        item = xbmcgui.ListItem(label='Video ' + vid)
        if vid in VIDEO_INFO_CACHE:
            info = VIDEO_INFO_CACHE[vid]
            item.setLabel('{} - {}'.format(info['artist'], info['title']))
        playlist.add(url, item)
    
    xbmc.Player().play(playlist)

def router(paramstring):
    params = dict(parse_qsl(paramstring))
    handle = int(sys.argv[1])
    
    if not params:
        list_channels(handle)
    elif params.get('action') == 'browse':
        browse_channel(handle, params['channel'])
    elif params.get('action') == 'play_shuffle':
        play_shuffle(params['channel'])

if __name__ == '__main__':
    router(sys.argv[2][1:])