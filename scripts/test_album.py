from scripts.spider import Album
from unittest import TestCase

class TestAlbum(TestCase):
    def setUp(self):
        self.album_id = 2261058

    def test_album(self):
        self.assertTrue(Album(self.album_id))
        
