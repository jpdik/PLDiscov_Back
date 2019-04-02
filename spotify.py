from spotipy.oauth2 import SpotifyClientCredentials
from spotipy import Spotify
import pprint

client_id = "f19c9ae55396441baf723bc14dc43cd3"
client_secret = "8dd8734e6c9345bca9980ce1e99b1ed2"

client_credentials_manager = SpotifyClientCredentials(client_id, client_secret)
sp = Spotify(client_credentials_manager=client_credentials_manager)

def search_music(song_name, artist='', url='', genre=0):
    results = []
    
    result = sp.search(q='track:{}:artist:{}'.format(song_name, artist))
    for item in result['tracks']['items']:
        music = {}
        #print(item)
        music['album'] = item['album']['name']  # Parse json dictionary
        music['artista'] = item['album']['artists'][0]['name']
        music['musica'] = item['name']
        music['genero'] = genre
        music['album_art'] = item['album']['images'][0]['url']
        music['preview_url'] = item['external_urls']['spotify'].replace('/track/', '/embed/track/')
        music['lyrics_url'] = url
        #print(item)
        results.append(music)

    if results:
        return results[0]
    else:
        music = {}
        music['album'] = ''
        music['artista'] = artist
        music['musica'] = song_name
        music['genero'] = genre
        music['preview_url'] = 'Indisponível'
        music['lyrics_url'] = url
        return music