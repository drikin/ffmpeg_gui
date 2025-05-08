import unittest
from core.speech_segment_extractor import SpeechSegmentExtractor
import tempfile
import os

class TestSpeechSegmentExtractor(unittest.TestCase):
    def setUp(self):
        self.extractor = SpeechSegmentExtractor()
        # テスト用簡易SRT
        self.srt_content = """1\n00:00:01,000 --> 00:00:04,000\nHello world\n\n2\n00:00:05,500 --> 00:00:07,000\nTest segment\n\n"""
        fd, self.srt_path = tempfile.mkstemp(suffix=".srt")
        with open(self.srt_path, "w", encoding="utf-8") as f:
            f.write(self.srt_content)
        os.close(fd)

    def tearDown(self):
        os.remove(self.srt_path)

    def test_parse_srt_segments(self):
        segments = self.extractor.parse_srt_segments(self.srt_path, offset_sec=1.0)
        self.assertEqual(len(segments), 2)
        self.assertAlmostEqual(segments[0][0], 0.0)  # start-offset=0
        self.assertAlmostEqual(segments[0][1], 5.0)  # end+offset=4+1
        self.assertAlmostEqual(segments[1][0], 4.5)  # 5.5-1
        self.assertAlmostEqual(segments[1][1], 8.0)  # 7+1

if __name__ == "__main__":
    unittest.main()
