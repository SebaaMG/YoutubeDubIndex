from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import Settings
from app.youtube import YouTubeService


class YouTubeServiceConfigurationTests(unittest.TestCase):
    def test_ytdlp_inspection_opts_have_bounded_network_retries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings(project_root=Path(temp_dir))
            with patch("app.youtube.ensure_yt_dlp_import", return_value=object()):
                service = YouTubeService(settings)

        opts = service.base_opts

        self.assertLessEqual(int(opts["socket_timeout"]), 12)
        self.assertLessEqual(int(opts["extractor_retries"]), 1)
        self.assertLessEqual(int(opts["retries"]), 1)
        self.assertEqual(opts["extractor_args"]["youtube"]["player_client"], ["web_embedded", "web"])

    def test_inspection_does_not_call_ytdlp_only_to_probe_original_audio(self) -> None:
        payload = {
            "videoDetails": {
                "title": "A dubbed video",
                "author": "Channel",
                "channelId": "channel-1",
                "lengthSeconds": "120",
                "viewCount": "1234",
                "thumbnail": {"thumbnails": [{"url": "https://example.invalid/thumb.jpg"}]},
            },
            "microformat": {"playerMicroformatRenderer": {"publishDate": "2026-05-20"}},
            "captions": {
                "playerCaptionsTracklistRenderer": {
                    "audioTracks": [
                        {"audioTrackId": "en.0"},
                        {"audioTrackId": "es.1"},
                    ]
                }
            },
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings(project_root=Path(temp_dir))
            with patch("app.youtube.ensure_yt_dlp_import", return_value=object()):
                service = YouTubeService(settings)
        with (
            patch.object(service, "fetch_watch_page", return_value="watch html"),
            patch.object(service, "extract_player_response", return_value=payload),
            patch.object(service, "extract_video_info", side_effect=AssertionError("unexpected yt-dlp call")) as info,
        ):
            result = service.inspect_video("abc12345678")

        info.assert_not_called()
        self.assertEqual(result.audio_languages, ["en", "es"])
        self.assertEqual(result.dub_kind, "manual")
        self.assertTrue(result.dub_evidence["spanish_non_original_inferred"])


if __name__ == "__main__":
    unittest.main()
