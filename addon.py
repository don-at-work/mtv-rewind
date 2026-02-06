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
from urllib.parse import urlencode, parse_qsl

ADDON = xbmcaddon.Addon()
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_DATA_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
CACHE_FILE = os.path.join(ADDON_DATA_PATH, 'video_metadata_cache.json')

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
        if xbmcvfs.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
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
        
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
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
        log('Loaded {} channels with {} total videos'.format(
            len(PLAYLISTS), sum(len(v) for v in PLAYLISTS.values())))
        return PLAYLISTS
    except Exception as e:
        log('ERROR loading playlists: {}'.format(str(e)))
        return {}

def get_video_info_from_youtube(video_id, force_refresh=False):
    """Holt Video-Metadaten von YouTube via oEmbed API mit Caching."""
    # Prüfe Memory-Cache
    if not force_refresh and video_id in VIDEO_INFO_CACHE:
        return VIDEO_INFO_CACHE[video_id]
    
    try:
        import urllib.request
        
        log('Fetching metadata for video: {}'.format(video_id))
        url = 'https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={}&format=json'.format(video_id)
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            title = data.get('title', '')
            author = data.get('author_name', '')
            
            # Versuche Künstler und Titel zu trennen
            if ' - ' in title:
                parts = title.split(' - ', 1)
                artist = parts[0].strip()
                song = parts[1].strip()
            elif '|' in title:
                parts = title.split('|', 1)
                artist = parts[0].strip()
                song = parts[1].strip()
            else:
                artist = author if author else 'Unknown Artist'
                song = title if title else 'Unknown Title'
            
            # Entferne "(Official Video)" etc.
            for phrase in ['(Official Video)', '(Official Music Video)', '[Official Video]', 
                          '[Official Music Video]', '(Official HD Video)', '[HD]', '(HD)',
                          '(Explicit)', '[Explicit]', '(Audio)', '[Audio]']:
                song = song.replace(phrase, '')
            song = song.strip()
            
            info = {
                'artist': artist,
                'title': song,
                'full_title': title,
                'thumb': 'https://i.ytimg.com/vi/{}/mqdefault.jpg'.format(video_id),
                'poster': 'https://i.ytimg.com/vi/{}/hqdefault.jpg'.format(video_id),
                'plot': '{} - {}'.format(artist, song)
            }
            
            # Speichere im Memory-Cache
            VIDEO_INFO_CACHE[video_id] = info
            return info
            
    except Exception as e:
        log('Could not fetch info for {}: {}'.format(video_id, str(e)))
    
    # Fallback
    fallback = {
        'artist': 'Unknown Artist',
        'title': 'Video {}'.format(video_id[:8]),
        'full_title': video_id,
        'thumb': 'https://i.ytimg.com/vi/{}/mqdefault.jpg'.format(video_id),
        'poster': 'https://i.ytimg.com/vi/{}/hqdefault.jpg'.format(video_id),
        'plot': 'YouTube Video ID: {}'.format(video_id)
    }
    
    VIDEO_INFO_CACHE[video_id] = fallback
    return fallback

def list_channels(handle):
    """Zeigt die Hauptkategorien an."""
    try:
        log('=== LIST CHANNELS START ===')
        
        playlists = get_playlists()
        
        if playlists:
            channel_names = {
                '1stday': '1st Day (1981)',
                '70s': '1970s',
                '80s': '1980s', 
                '90s': '1990s',
                '2000s': '2000s',
                '2010s': '2010s',
                '2020s': '2020s',
                'trl': 'TRL (Total Request Live)',
                'raps': 'Yo! MTV Raps',
                'metal': 'Headbangers Ball',
                '120minutes': '120 Minutes (Alternative)',
                'unplugged': 'MTV Unplugged',
                'club': 'Club MTV / Dance',
                'commercials': 'MTV Commercials',
            }
            
            priority = ['1stday', '70s', '80s', '90s', '2000s', '2010s', '2020s', 'trl', 
                       'raps', 'metal', '120minutes', 'unplugged', 'club', 'commercials']
            
            for channel_id in priority:
                if channel_id in playlists:
                    video_ids = playlists[channel_id]
                    display_name = channel_names.get(channel_id, channel_id.title())
                    
                    list_item = xbmcgui.ListItem(label=display_name)
                    list_item.setInfo('video', {
                        'title': display_name,
                        'genre': 'Music',
                        'plot': '{} Videos verfuegbar'.format(len(video_ids)),
                        'mediatype': 'video'
                    })
                    list_item.setArt({
                        'icon': 'DefaultMusicVideos.png',
                        'fanart': 'DefaultMusicVideos.png'
                    })
                    url = get_url(action='browse', channel=channel_id)
                    xbmcplugin.addDirectoryItem(handle, url, list_item, True)
            
            for channel_id in sorted(playlists.keys()):
                if channel_id not in priority:
                    video_ids = playlists[channel_id]
                    display_name = channel_names.get(channel_id, channel_id.title())
                    
                    list_item = xbmcgui.ListItem(label=display_name)
                    list_item.setInfo('video', {
                        'title': display_name,
                        'genre': 'Music',
                        'plot': '{} Videos'.format(len(video_ids)),
                        'mediatype': 'video'
                    })
                    list_item.setArt({
                        'icon': 'DefaultMusicVideos.png',
                        'fanart': 'DefaultMusicVideos.png'
                    })
                    url = get_url(action='browse', channel=channel_id)
                    xbmcplugin.addDirectoryItem(handle, url, list_item, True)
        else:
            error_item = xbmcgui.ListItem(label='[COLOR red]Keine Daten[/COLOR]')
            xbmcplugin.addDirectoryItem(handle, '', error_item, False)
        
        xbmcplugin.endOfDirectory(handle, succeeded=True)
        log('=== LIST CHANNELS END ===')
        
    except Exception as e:
        log('ERROR: {}'.format(str(e)))
        log(traceback.format_exc())
        xbmcplugin.endOfDirectory(handle, succeeded=False)

def browse_channel(handle, channel_id):
    """Zeigt Videos eines Kanals an."""
    try:
        log('=== BROWSE: {} ==='.format(channel_id))
        
        # Lade Cache beim ersten Aufruf
        if not VIDEO_INFO_CACHE:
            load_cache_from_disk()
        
        # Prüfe Setting
        fetch_metadata = get_setting_bool('fetch_metadata')
        log('Fetch metadata setting: {}'.format(fetch_metadata))
        
        playlists = get_playlists()
        
        if channel_id in playlists:
            video_ids = playlists[channel_id]
            log('Showing {} videos'.format(len(video_ids)))
            
            # Zähle wie viele Videos bereits gecached sind
            cached_count = sum(1 for vid in video_ids if vid in VIDEO_INFO_CACHE)
            
            # Info-Item
            if fetch_metadata:
                if cached_count == len(video_ids):
                    info_text = '[COLOR green]{} Videos - Alle aus Cache[/COLOR]'.format(len(video_ids))
                    info_plot = 'Alle Video-Informationen sind bereits im Cache vorhanden.'
                else:
                    info_text = '[COLOR yellow]{} Videos - {} aus Cache, {} werden geladen...[/COLOR]'.format(
                        len(video_ids), cached_count, len(video_ids) - cached_count)
                    info_plot = 'Fehlende Video-Informationen werden von YouTube geladen und gecached.'
            else:
                info_text = '[COLOR yellow]{} Videos[/COLOR]'.format(len(video_ids))
                info_plot = 'Tipp: Aktiviere "Video-Titel laden" in den Addon-Einstellungen für Künstler & Titel.'
            
            info = xbmcgui.ListItem(label=info_text)
            info.setInfo('video', {'title': 'Info', 'plot': info_plot})
            xbmcplugin.addDirectoryItem(handle, '', info, False)
            
            # Tracking für neue Metadaten
            new_metadata_count = 0
            
            # Videos
            for idx, video_id in enumerate(video_ids, 1):
                if fetch_metadata:
                    # Hole Video-Infos (aus Cache oder von YouTube)
                    was_cached = video_id in VIDEO_INFO_CACHE
                    video_info = get_video_info_from_youtube(video_id)
                    
                    if not was_cached:
                        new_metadata_count += 1
                    
                    label = '{} - {}'.format(video_info['artist'], video_info['title'])
                    title = video_info['title']
                    artist = video_info['artist']
                    plot = video_info['plot']
                    thumb = video_info['thumb']
                    poster = video_info['poster']
                else:
                    # Schnelle Anzeige ohne Metadaten
                    label = 'Music Video #{}'.format(idx)
                    title = label
                    artist = 'Unknown'
                    plot = 'YouTube Video ID: {}'.format(video_id)
                    thumb = 'https://i.ytimg.com/vi/{}/mqdefault.jpg'.format(video_id)
                    poster = 'https://i.ytimg.com/vi/{}/hqdefault.jpg'.format(video_id)
                
                item = xbmcgui.ListItem(label=label)
                item.setInfo('video', {
                    'title': title,
                    'artist': [artist],
                    'genre': 'Music',
                    'mediatype': 'musicvideo',
                    'plot': plot
                })
                item.setArt({
                    'thumb': thumb,
                    'poster': poster
                })
                
                youtube_url = 'plugin://plugin.video.youtube/play/?video_id={}'.format(video_id)
                xbmcplugin.addDirectoryItem(handle, youtube_url, item, False)
                
                # Progress-Log alle 50 Videos
                if fetch_metadata and idx % 50 == 0:
                    log('Processed {} of {} videos ({} new from YouTube)'.format(
                        idx, len(video_ids), new_metadata_count))
            
            # Speichere Cache wenn neue Daten geladen wurden
            if fetch_metadata and new_metadata_count > 0:
                log('Saving cache with {} new entries...'.format(new_metadata_count))
                save_cache_to_disk()
        else:
            error = xbmcgui.ListItem(label='[COLOR red]Kanal nicht gefunden[/COLOR]')
            xbmcplugin.addDirectoryItem(handle, '', error, False)
        
        xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_NONE)
        if fetch_metadata:
            xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_LABEL)
            xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_ARTIST)
        
        xbmcplugin.endOfDirectory(handle, succeeded=True)
        log('=== BROWSE END ===')
        
    except Exception as e:
        log('ERROR: {}'.format(str(e)))
        log(traceback.format_exc())
        xbmcplugin.endOfDirectory(handle, succeeded=False)

def router(paramstring):
    try:
        params = dict(parse_qsl(paramstring))
        handle = int(sys.argv[1])
        
        if not params:
            list_channels(handle)
        elif params.get('action') == 'browse':
            browse_channel(handle, params['channel'])
        else:
            xbmcplugin.endOfDirectory(handle, succeeded=False)
    except Exception as e:
        log('FATAL: {}'.format(str(e)))
        try:
            xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=False)
        except:
            pass

if __name__ == '__main__':
    log('MTV REWIND v1.6.0 - With Disk Cache')
    router(sys.argv[2][1:])
