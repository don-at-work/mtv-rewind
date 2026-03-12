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

# Memory Cache
VIDEO_INFO_CACHE = {}

def get_url(**kwargs):
    return '{}?{}'.format(sys.argv[0], urlencode(kwargs))

def log(msg):
    xbmc.log('[MTV-REWIND] {}'.format(str(msg)), xbmc.LOGINFO)

def get_setting_bool(setting_id):
    return ADDON.getSettingBool(setting_id)

def load_cache_from_disk():
    global VIDEO_INFO_CACHE
    # Prüfe beide möglichen Pfade (User Data oder Addon Pfad)
    paths = [
        os.path.join(ADDON_DATA_PATH, 'video_metadata_cache.json'),
        os.path.join(ADDON_PATH, 'resources', 'cache', 'video_metadata_cache.json')
    ]
    for path in paths:
        try:
            if xbmcvfs.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    VIDEO_INFO_CACHE = json.load(f)
                    log('Cache loaded from: {}'.format(path))
                    return True
        except: continue
    return False

def get_playlists():
    try:
        from resources.lib.playlists_data import PLAYLISTS
        return PLAYLISTS
    except:
        return {}

def get_video_info(video_id):
    if video_id in VIDEO_INFO_CACHE:
        return VIDEO_INFO_CACHE[video_id]
    return {
        'artist': 'Unknown',
        'title': 'Video ' + video_id,
        'thumb': 'https://i.ytimg.com/vi/{}/mqdefault.jpg'.format(video_id)
    }

def list_channels(handle):
    """Hauptmenü."""
    # 1. Suche
    search_item = xbmcgui.ListItem(label='[COLOR yellow][ Suche... ][/COLOR]')
    search_item.setArt({'icon': 'DefaultAddonsSearch.png'})
    xbmcplugin.addDirectoryItem(handle, get_url(action='search'), search_item, True)

    # 2. Kategorien
    playlists = get_playlists()
    channel_names = {
        '1stday': '1st Day (1981)', '70s': '1970s', '80s': '1980s', '90s': '1990s',
        '2000s': '2000s', '2010s': '2010s', '2020s': '2020s', 'trl': 'TRL',
        'raps': 'Yo! MTV Raps', 'metal': 'Headbangers Ball', 'unplugged': 'MTV Unplugged'
    }
    
    for cid in sorted(playlists.keys()):
        name = channel_names.get(cid, cid.title())
        item = xbmcgui.ListItem(label=name)
        item.setArt({'icon': 'DefaultMusicVideos.png'})
        xbmcplugin.addDirectoryItem(handle, get_url(action='browse', channel=cid), item, True)
    
    xbmcplugin.endOfDirectory(handle)

def browse_channel(handle, channel_id, custom_vids=None):
    if not VIDEO_INFO_CACHE:
        load_cache_from_disk()
        
    if custom_vids:
        video_ids = custom_vids
        is_search = True
    else:
        playlists = get_playlists()
        video_ids = playlists.get(channel_id, [])
        is_search = False

    if video_ids:
        # Shuffle Button
        v_ids_str = ','.join(video_ids) if is_search else ''
        u = get_url(action='play_shuffle', channel=channel_id, vids=v_ids_str)
        item = xbmcgui.ListItem(label='[COLOR orange]➔ SHUFFLE ALL[/COLOR]')
        xbmcplugin.addDirectoryItem(handle, u, item, False)

    for vid in video_ids:
        info = get_video_info(vid)
        label = '{} - {}'.format(info['artist'], info['title'])
        item = xbmcgui.ListItem(label=label)
        item.setArt({'thumb': info.get('thumb')})
        item.setInfo('video', {'title': info['title'], 'artist': [info['artist']]})
        url = 'plugin://plugin.video.youtube/play/?video_id={}'.format(vid)
        xbmcplugin.addDirectoryItem(handle, url, item, False)

    xbmcplugin.endOfDirectory(handle)

def run_search(handle):
    """Suche über xbmc.Keyboard."""
    # KORREKTUR: xbmc.Keyboard statt xbmcgui.Keyboard
    kb = xbmc.Keyboard('', 'MTV Rewind Suche (Künstler oder Titel)')
    kb.doModal()
    
    if not kb.isConfirmed():
        return
    
    query = kb.getText().lower()
    if not query:
        return

    if not VIDEO_INFO_CACHE:
        load_cache_from_disk()

    results = []
    for vid, info in VIDEO_INFO_CACHE.items():
        artist = info.get('artist', '').lower()
        title = info.get('title', '').lower()
        if query in artist or query in title:
            results.append(vid)

    if results:
        browse_channel(handle, 'search_results', custom_vids=results)
    else:
        xbmcgui.Dialog().ok(ADDON_NAME, 'Keine Videos für "{}" im Cache gefunden.'.format(query))

def play_shuffle(channel_id, vids_str=''):
    if vids_str:
        vids = vids_str.split(',')
    else:
        playlists = get_playlists()
        vids = list(playlists.get(channel_id, []))
    
    if not vids: return
    random.shuffle(vids)
    
    playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
    playlist.clear()
    
    for vid in vids:
        url = 'plugin://plugin.video.youtube/play/?video_id={}'.format(vid)
        info = get_video_info(vid)
        item = xbmcgui.ListItem(label='{} - {}'.format(info['artist'], info['title']))
        playlist.add(url, item)
    
    xbmc.Player().play(playlist)

def router(paramstring):
    params = dict(parse_qsl(paramstring))
    handle = int(sys.argv[1])
    
    if not params:
        list_channels(handle)
    elif params.get('action') == 'browse':
        browse_channel(handle, params['channel'])
    elif params.get('action') == 'search':
        run_search(handle)
    elif params.get('action') == 'play_shuffle':
        play_shuffle(params.get('channel'), params.get('vids', ''))

if __name__ == '__main__':
    router(sys.argv[2][1:])