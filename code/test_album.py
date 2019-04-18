from src.spider import Album
from unittest import TestCase

class TestAlbum(TestCase):
    def setUp(self):
        self.album_id = 34961173

    def test_album(self):
        self.assertTrue(Album(self.album_id))
        
