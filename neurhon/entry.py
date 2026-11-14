import neurhon.data_aquisition.eeg.livestream as ls
from neurhon.logging.logger import log as log
import neurhon.action.spotify.api as sp
import neurhon.data_aquisition.music.api as lfmp
def run():
    spotify_api = sp.SpotifyApi()
    lastfm_api = lfmp.LastFMApi()
    songs = lastfm_api.get_songs_based_on_tag(1,["gangnam"])
    log.info(songs)
    spotify_api.play_track(songs[0].get_title(), songs[0].get_artist().name)
    #spotify_api.play_track("Gangnam style", "PSY")
    #stream = ls.DataStreamContinuous(device_name="BA MINI 077",timeframe=0.5)
    #stream.start_streaming()
    #stream.kill_yourself()
