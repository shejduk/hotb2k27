from neurhon.logging.logger import log as log
from dotenv import load_dotenv
import pylast
import os

class LastFMApi:
    def __init__(self):
        try:
            load_dotenv()
            self._api_endpoint = pylast.LastFMNetwork(api_key=os.environ["LAST_FM_API_KEY"])
            log.info("Initialized LastFM API")

        except:
            log.fatal("Could not connect to LastFM database")
            raise ValueError("Configure LAstFM api please!")

    def get_songs_based_on_tag(self, num_songs : int, tag_list : list):
        result = []
        if len(tag_list) == 0:
            return []
        for t in tag_list:
            tag = self._api_endpoint.get_tag(t)
            result += tag.get_top_tracks(limit=max(1,num_songs // len(tag_list)))

        return [i.item for i in result]



