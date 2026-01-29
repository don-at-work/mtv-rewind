# -*- coding: utf-8 -*-
import sys
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmc
import traceback
import json
from urllib.parse import urlencode, parse_qsl

ADDON = xbmcaddon.Addon()
ADDON_NAME = ADDON.getAddonInfo('name')

# Cache für Video-Infos
VIDEO_INFO_CACHE = {}

def get_url(**kwargs):
    return '{}?{}'.format(sys.argv[0], urlencode(kwargs))

def log(msg, level=xbmc.LOGINFO):
    xbmc.log('[MTV-REWIND] {}'.format(str(msg)), level)

def get_setting_bool(setting_id):
    """Liest Boolean-Setting aus."""
    return ADDON.getSettingBool(setting_id)

def get_playlists():
    """Gibt die eingebetteten Playlist-Daten zurueck."""
    try:
        from resources.lib.playlists_data import PLAYLISTS
        log('Loaded {} channels with {} total videos'.format(
            len(PLAYLISTS), sum(len(v) for v in PLAYLISTS.values())))
        return PLAYLISTS
    except Exception as e:
        log('ERROR loading playlists: {}'.format(str(e)), level=xbmc.LOGERROR)
        return {}

def get_video_info_from_youtube(video_id):
    """Holt Video-Metadaten von YouTube via oEmbed API."""
    if video_id in VIDEO_INFO_CACHE:
        return VIDEO_INFO_CACHE[video_id]
    
    try:
        import urllib.request
        
        url = 'https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={}&format=json'.format(video_id)
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        
        with urllib.request.urlopen(req, timeout=3) as response:
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
                          '[Official Music Video]', '(Official HD Video)', '[HD]']:
                song = song.replace(phrase, '')
            song = song.strip()
            
            info = {
                'artist': artist,
                'title': song,
                'full_title': title
            }
            
            VIDEO_INFO_CACHE[video_id] = info
            return info
            
    except Exception as e:
        log('Could not fetch info for {}: {}'.format(video_id, str(e)), level=xbmc.LOGWARNING)
    
    # Fallback
    return {
        'artist': 'Unknown Artist',
        'title': 'Video {}'.format(video_id[:8]),
        'full_title': video_id
    }

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
        log('ERROR: {}'.format(str(e)), level=xbmc.LOGERROR)
        log(traceback.format_exc(), level=xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(handle, succeeded=False)

def browse_channel(handle, channel_id):
    """Zeigt Videos eines Kanals an."""
    try:
        log('=== BROWSE: {} ==='.format(channel_id))
        
        # Prüfe Setting
        fetch_metadata = get_setting_bool('fetch_metadata')
        log('Fetch metadata setting: {}'.format(fetch_metadata))
        
        playlists = get_playlists()
        
        if channel_id in playlists:
            video_ids = playlists[channel_id]
            log('Showing {} videos'.format(len(video_ids)))
            
            # Info-Item
            if fetch_metadata:
                info_text = '[COLOR yellow]{} Videos - Metadaten werden geladen...[/COLOR]'.format(len(video_ids))
                info_plot = 'Video-Titel werden von YouTube geladen. Dies kann einige Sekunden dauern.'
            else:
                info_text = '[COLOR yellow]{} Videos[/COLOR]'.format(len(video_ids))
                info_plot = 'Tipp: Aktiviere "Video-Titel laden" in den Addon-Einstellungen für Künstler & Titel.'
            
            info = xbmcgui.ListItem(label=info_text)
            info.setInfo('video', {'title': 'Info', 'plot': info_plot})
            xbmcplugin.addDirectoryItem(handle, '', info, False)
            
            # Videos
            for idx, video_id in enumerate(video_ids, 1):
                if fetch_metadata:
                    # Hole Video-Infos von YouTube
                    video_info = get_video_info_from_youtube(video_id)
                    label = '{} - {}'.format(video_info['artist'], video_info['title'])
                    title = video_info['title']
                    artist = video_info['artist']
                    plot = video_info['full_title']
                else:
                    # Schnelle Anzeige ohne Metadaten
                    label = 'Music Video #{}'.format(idx)
                    title = label
                    artist = 'Unknown'
                    plot = 'YouTube Video ID: {}'.format(video_id)
                
                item = xbmcgui.ListItem(label=label)
                item.setInfo('video', {
                    'title': title,
                    'artist': [artist],
                    'genre': 'Music',
                    'mediatype': 'musicvideo',
                    'plot': plot
                })
                item.setArt({
                    'thumb': 'https://i.ytimg.com/vi/{}/mqdefault.jpg'.format(video_id),
                    'poster': 'https://i.ytimg.com/vi/{}/hqdefault.jpg'.format(video_id)
                })
                
                youtube_url = 'plugin://plugin.video.youtube/play/?video_id={}'.format(video_id)
                xbmcplugin.addDirectoryItem(handle, youtube_url, item, False)
                
                # Progress-Log alle 50 Videos
                if fetch_metadata and idx % 50 == 0:
                    log('Loaded metadata for {} of {} videos'.format(idx, len(video_ids)))
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
        log('ERROR: {}'.format(str(e)), level=xbmc.LOGERROR)
        log(traceback.format_exc(), level=xbmc.LOGERROR)
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
        log('FATAL: {}'.format(str(e)), level=xbmc.LOGERROR)
        try:
            xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=False)
        except:
            pass

if __name__ == '__main__':
    log('MTV REWIND v1.5.0 - With Settings')
    router(sys.argv[2][1:])
