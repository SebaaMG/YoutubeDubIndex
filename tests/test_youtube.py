from __future__ import annotations

import unittest

from app.youtube import InspectionResult, YouTubeService


class YouTubeHelpersTests(unittest.TestCase):
    def test_extract_audio_languages_from_formats(self) -> None:
        info = {
            "formats": [
                {"language": "en-US", "acodec": "opus", "vcodec": "none"},
                {"language": "es-419", "acodec": "opus", "vcodec": "none"},
                {"language": "en-US", "acodec": "opus", "vcodec": "none"},
                {"language": "en-US", "acodec": "none", "vcodec": "avc1"},
            ]
        }
        self.assertEqual(YouTubeService.extract_audio_languages(info), ["en-US", "es-419"])

    def test_extract_original_audio_languages_from_info(self) -> None:
        info = {
            "formats": [
                {
                    "language": "es-US",
                    "acodec": "opus",
                    "vcodec": "none",
                    "format_note": "Spanish (US) original (default), low",
                    "language_preference": 10,
                },
                {
                    "language": "en-US",
                    "acodec": "opus",
                    "vcodec": "none",
                    "format_note": "English, low",
                    "language_preference": -1,
                },
            ]
        }

        self.assertEqual(YouTubeService.extract_original_audio_languages_from_info(info), ["es-US"])
        self.assertEqual(YouTubeService.extract_auto_dubbed_languages_from_info(info), [])

    def test_extract_original_audio_languages_from_nested_audio_track_metadata(self) -> None:
        info = {
            "formats": [
                {
                    "language": "es-US",
                    "acodec": "opus",
                    "vcodec": "none",
                    "audioTrack": {"id": "es-US.4", "displayName": "Spanish (US) original"},
                },
                {
                    "language": "en-US",
                    "acodec": "opus",
                    "vcodec": "none",
                    "audioTrack": {"id": "en-US.3", "displayName": "English"},
                },
            ]
        }

        self.assertEqual(YouTubeService.extract_original_audio_languages_from_info(info), ["es-US"])

    def test_extract_audio_languages_ignores_descriptive_audio_tracks(self) -> None:
        info = {
            "formats": [
                {"language": "en", "acodec": "opus", "vcodec": "none"},
                {"language": "en-desc", "acodec": "opus", "vcodec": "none"},
            ]
        }

        self.assertEqual(YouTubeService.extract_audio_languages(info), ["en"])
        self.assertFalse(InspectionResult(audio_languages=["en", "en-desc"]).has_dubbing)

    def test_extract_audio_tracks_from_watch_html(self) -> None:
        html = """
        <html><script>
        var ytInitialPlayerResponse = {
          "captions": {
            "playerCaptionsTracklistRenderer": {
              "audioTracks": [
                {"audioTrackId": "en-US.4"},
                {},
                {"audioTrackId": "es-419.3"},
                {"audioTrackId": "en-US.5"}
              ]
            }
          }
        };
        </script></html>
        """
        self.assertEqual(
            YouTubeService.extract_audio_tracks_from_watch_html(html),
            ["en-US", "es-419"],
        )

    def test_classifies_auto_dubbed_marker_and_default_manual_dubs(self) -> None:
        self.assertEqual(InspectionResult(audio_languages=["en", "es-US"]).dub_kind, "manual")
        self.assertEqual(InspectionResult(audio_languages=["en"]).dub_kind, "none")
        self.assertEqual(
            YouTubeService.classify_dub_kind(
                ["en", "es-US"],
                "",
                {
                    "captions": {
                        "playerCaptionsTracklistRenderer": {
                            "audioTracks": [
                                {"audioTrackId": "en.4"},
                                {"audioTrackId": "es.3", "isAutoDubbed": True},
                            ]
                        }
                    }
                },
            ),
            "automatic",
        )

    def test_merge_video_metadata_replaces_invalid_placeholder_values(self) -> None:
        primary = {
            "title": "zRtGL0-5rg4",
            "channel": "Last To Leave Grocery Store, Wins $250,000",
            "channel_id": "UCX6OQ3DkcsbYNE6H8uQQuVA",
        }
        fallback = {
            "title": "Last To Leave Grocery Store, Wins $250,000",
            "channel": "MrBeast",
            "channel_id": "UCX6OQ3DkcsbYNE6H8uQQuVA",
        }

        self.assertEqual(
            YouTubeService.merge_video_metadata(primary, fallback, video_id="zRtGL0-5rg4"),
            fallback,
        )
        self.assertEqual(
            YouTubeService.classify_dub_kind(
                ["en", "es-US"],
                "",
                {
                    "captions": {
                        "playerCaptionsTracklistRenderer": {
                            "audioTracks": [
                                {"audioTrackId": "en.4"},
                                {"audioTrackId": "es.3", "displayName": "Spanish automatically dubbed"},
                            ]
                        }
                    }
                },
            ),
            "automatic",
        )

    def test_large_multiaudio_language_sets_stay_manual_without_auto_marker(self) -> None:
        languages = ["ar", "bn", "de", "en", "es", "fr", "hi", "id", "it", "ja"]

        self.assertEqual(YouTubeService.classify_dub_kind(languages, "", {}), "manual")

    def test_global_auto_dubbed_text_does_not_classify_video_as_automatic(self) -> None:
        languages = ["en", "es-US"]
        html = "<html><script>var PLAYER_LABEL = 'Auto-dubbed';</script></html>"
        payload = {"messages": {"AUTO_DUBBED": "Auto-dubbed"}}

        self.assertEqual(YouTubeService.classify_dub_kind(languages, html, payload), "manual")

    def test_automatic_captions_and_dubbed_audio_tags_do_not_mean_auto_dub(self) -> None:
        languages = ["ar", "bn", "de", "en", "es", "fr", "hi", "id", "it", "ja"]
        info = {
            "automatic_captions": {"es": [{"url": "https://example.invalid/caption"}]},
            "formats": [
                {
                    "url": "https://example.invalid/audio?xtags=acont%3ddubbed%3alang%3des",
                    "language": "es",
                    "acodec": "opus",
                    "vcodec": "none",
                }
            ],
        }

        self.assertEqual(YouTubeService.classify_dub_kind(languages, "", {}, info), "manual")

    def test_classifies_streaming_audio_track_auto_dub_marker_as_automatic(self) -> None:
        payload = {
            "captions": {
                "playerCaptionsTracklistRenderer": {
                    "audioTracks": [
                        {"audioTrackId": "en.4", "displayName": "English"},
                        {"audioTrackId": "es.3", "displayName": "Spanish"},
                    ]
                }
            },
            "streamingData": {
                "adaptiveFormats": [
                    {
                        "mimeType": 'audio/mp4; codecs="mp4a.40.2"',
                        "audioTrack": {
                            "id": "es.3",
                            "displayName": "Spanish",
                            "isAutoDubbed": True,
                        },
                    }
                ]
            },
        }

        self.assertEqual(YouTubeService.extract_audio_tracks_from_payload(payload), ["en", "es"])
        self.assertEqual(YouTubeService.classify_dub_kind(["en", "es"], "", payload), "automatic")

    def test_extracts_spanish_auto_dub_marker_without_classifying_every_language(self) -> None:
        payload = {
            "captions": {
                "playerCaptionsTracklistRenderer": {
                    "audioTracks": [
                        {"audioTrackId": "en.4", "displayName": "English original"},
                        {"audioTrackId": "es.3", "displayName": "Spanish"},
                        {"audioTrackId": "fr.2", "displayName": "French"},
                    ]
                }
            },
            "streamingData": {
                "adaptiveFormats": [
                    {
                        "mimeType": 'audio/mp4; codecs="mp4a.40.2"',
                        "audioTrack": {
                            "id": "es.3",
                            "displayName": "Spanish dubbed-auto",
                            "isAutoDubbed": True,
                        },
                    },
                    {
                        "mimeType": 'audio/mp4; codecs="mp4a.40.2"',
                        "audioTrack": {"id": "fr.2", "displayName": "French"},
                    },
                ]
            },
        }

        self.assertEqual(
            YouTubeService.extract_auto_dubbed_languages_from_payload(payload),
            ["es"],
        )

    def test_ytdlp_spanish_auto_dub_marker_is_extracted_from_formats(self) -> None:
        info = {
            "formats": [
                {"language": "en", "acodec": "opus", "vcodec": "none"},
                {
                    "language": "es",
                    "acodec": "opus",
                    "vcodec": "none",
                    "audioTrack": {"id": "es.3", "displayName": "Spanish dubbed-auto"},
                },
                {
                    "language": "fr",
                    "acodec": "opus",
                    "vcodec": "none",
                    "audioTrack": {"id": "fr.2", "displayName": "French"},
                },
            ]
        }

        self.assertEqual(YouTubeService.extract_auto_dubbed_languages_from_info(info), ["es"])

    def test_ytdlp_extracts_auto_dub_marker_from_format_url_xtags(self) -> None:
        info = {
            "formats": [
                {
                    "language": "en-US",
                    "acodec": "opus",
                    "vcodec": "none",
                    "format_note": "English (US) original (default), medium",
                    "url": "https://example.invalid/audio?xtags=acont%3Doriginal%3Alang%3Den-US",
                },
                {
                    "language": "es-US",
                    "acodec": "opus",
                    "vcodec": "none",
                    "format_note": "Spanish (US), medium",
                    "url": "https://example.invalid/audio?xtags=acont%3Ddubbed-auto%3Alang%3Des-US",
                },
            ]
        }

        self.assertEqual(YouTubeService.extract_auto_dubbed_languages_from_info(info), ["es-US"])
        self.assertEqual(YouTubeService.classify_dub_kind(["en-US", "es-US"], "", {}, info), "automatic")

    def test_ytdlp_non_original_spanish_without_auto_marker_stays_manual(self) -> None:
        info = {
            "formats": [
                {
                    "language": "en-US",
                    "format_note": "English (US) original (default), low",
                    "language_preference": 10,
                    "acodec": "opus",
                    "vcodec": "none",
                },
                {
                    "language": "es-US",
                    "format_note": "Spanish (US), low",
                    "language_preference": -1,
                    "acodec": "opus",
                    "vcodec": "none",
                },
            ]
        }

        audio_languages = YouTubeService.extract_audio_languages(info)
        self.assertEqual(YouTubeService.extract_auto_dubbed_languages_from_info(info), [])
        self.assertEqual(YouTubeService.classify_dub_kind(audio_languages, "", {}, info), "manual")

    def test_ytdlp_keeps_spanish_original_audio_out_of_ai_filter(self) -> None:
        info = {
            "formats": [
                {
                    "language": "es-US",
                    "format_note": "Spanish (US) original (default), low",
                    "language_preference": 10,
                    "acodec": "opus",
                    "vcodec": "none",
                },
                {
                    "language": "en-US",
                    "format_note": "English (US), low",
                    "language_preference": -1,
                    "acodec": "opus",
                    "vcodec": "none",
                },
            ]
        }

        self.assertEqual(YouTubeService.extract_auto_dubbed_languages_from_info(info), [])

    def test_classifies_ytdlp_nested_audio_track_auto_dub_marker_as_automatic(self) -> None:
        info = {
            "formats": [
                {"language": "en", "acodec": "opus", "vcodec": "none"},
                {
                    "language": "es",
                    "acodec": "opus",
                    "vcodec": "none",
                    "audioTrack": {"id": "es.3", "displayName": "Spanish", "isAutoDubbed": True},
                },
            ]
        }

        audio_languages = YouTubeService.extract_audio_languages(info)

        self.assertEqual(audio_languages, ["en", "es"])
        self.assertEqual(YouTubeService.classify_dub_kind(audio_languages, "", {}, info), "automatic")

    def test_streaming_dubbed_auto_xtags_classifies_as_automatic(self) -> None:
        payload = {
            "streamingData": {
                "adaptiveFormats": [
                    {
                        "xtags": "ChQKBWFjb250EgtkdWJiZWQtYXV0bwoLCgRsYW5nEgNlcy0",
                        "audioTrack": {"id": "es.3", "displayName": "Spanish", "audioIsDefault": False},
                    }
                ]
            }
        }

        self.assertEqual(YouTubeService.classify_dub_kind(["en", "es"], "", payload), "automatic")

    def test_streaming_dubbed_xtags_without_auto_marker_stays_manual(self) -> None:
        payload = {
            "streamingData": {
                "adaptiveFormats": [
                    {
                        "xtags": "Cg8KBWFjb250EgZkdWJiZWQKCgoEbGFuZxICZXM",
                        "audioTrack": {"id": "es.3", "displayName": "Spanish", "audioIsDefault": False},
                    }
                ]
            }
        }

        self.assertEqual(YouTubeService.classify_dub_kind(["en", "es"], "", payload), "manual")

    def test_extracts_video_metadata_from_player_payload(self) -> None:
        payload = {
            "videoDetails": {
                "title": "Demo",
                "author": "Demo Channel",
                "channelId": "chan1",
                "lengthSeconds": "42",
                "thumbnail": {"thumbnails": [{"url": "small.jpg"}, {"url": "large.jpg"}]},
            }
        }

        self.assertEqual(
            YouTubeService.extract_video_metadata_from_payload(payload),
            {
                "title": "Demo",
                "channel": "Demo Channel",
                "channel_id": "chan1",
                "duration_seconds": 42,
                "thumbnail_url": "large.jpg",
            },
        )

    def test_extract_upload_metadata_from_watch_html_fallbacks(self) -> None:
        html = """
        <html>
          <meta itemprop="datePublished" content="2026-04-20T18:34:03-07:00">
          <meta itemprop="interactionCount" content="67200">
        </html>
        """

        self.assertEqual(
            YouTubeService.extract_published_at_from_html(html),
            "2026-04-20T18:34:03-07:00",
        )
        self.assertEqual(YouTubeService.extract_view_count_from_html(html), 67200)

    def test_extract_upload_metadata_from_ytdlp_info(self) -> None:
        info = {
            "upload_date": "20260420",
            "timestamp": 1776816000,
            "view_count": "12345",
        }

        self.assertEqual(YouTubeService.extract_published_at_from_info(info), "2026-04-20")
        self.assertEqual(YouTubeService.extract_view_count_from_info(info), 12345)

    def test_candidate_from_entry_keeps_discovery_metadata(self) -> None:
        entry = {
            "id": "abc123",
            "title": "Demo",
            "channel": "Chan",
            "duration": 10,
            "upload_date": "20260420",
            "view_count": 99,
        }

        candidate = YouTubeService._candidate_from_entry(entry)

        self.assertEqual(candidate["published_at"], "2026-04-20")
        self.assertEqual(candidate["view_count"], 99)

    def test_normalize_channel_url_appends_videos(self) -> None:
        url = "https://www.youtube.com/@MarkRober"
        self.assertEqual(
            YouTubeService.normalize_channel_url(url),
            "https://www.youtube.com/@MarkRober/videos",
        )

    def test_normalize_channel_url_accepts_bare_handle_and_slug(self) -> None:
        self.assertEqual(
            YouTubeService.normalize_channel_url("@kurzgesagt"),
            "https://www.youtube.com/@kurzgesagt/videos",
        )
        self.assertEqual(
            YouTubeService.normalize_channel_url("kurzgesagt"),
            "https://www.youtube.com/@kurzgesagt/videos",
        )
        self.assertEqual(
            YouTubeService.normalize_channel_url("channel/UCsXVk37bltHxD1rDPwtNM8Q"),
            "https://www.youtube.com/channel/UCsXVk37bltHxD1rDPwtNM8Q/videos",
        )

    def test_infer_source_type_detects_channel_inputs(self) -> None:
        self.assertEqual(YouTubeService.infer_source_type("@kurzgesagt"), "channel")
        self.assertEqual(
            YouTubeService.infer_source_type("https://www.youtube.com/@MarkRober"),
            "channel",
        )
        self.assertEqual(
            YouTubeService.infer_source_type("channel/UCsXVk37bltHxD1rDPwtNM8Q"),
            "channel",
        )

    def test_infer_source_type_defaults_to_search(self) -> None:
        self.assertEqual(YouTubeService.infer_source_type("anime doblado"), "search")
        self.assertEqual(YouTubeService.infer_source_type(""), "search")

    def test_extract_related_candidates_from_watch_next_payload(self) -> None:
        payload = {
            "contents": {
                "twoColumnWatchNextResults": {
                    "secondaryResults": {
                        "secondaryResults": {
                            "results": [
                                {
                                    "compactVideoRenderer": {
                                        "videoId": "rel123",
                                        "title": {"simpleText": "Related video"},
                                        "shortBylineText": {"runs": [{"text": "Related Channel"}]},
                                        "lengthText": {"simpleText": "12:34"},
                                        "thumbnail": {"thumbnails": [{"url": "small.jpg"}, {"url": "large.jpg"}]},
                                    }
                                },
                                {
                                    "compactVideoRenderer": {
                                        "videoId": "rel123",
                                        "title": {"simpleText": "Duplicate"},
                                    }
                                },
                                {
                                    "lockupViewModel": {
                                        "contentId": "lock456",
                                        "metadata": {
                                            "lockupMetadataViewModel": {
                                                "title": {"content": "Lockup video"},
                                                "metadata": {"content": "Lockup Channel"},
                                            }
                                        },
                                        "contentImage": {
                                            "thumbnailViewModel": {
                                                "image": {"sources": [{"url": "lock.jpg"}]}
                                            }
                                        },
                                    }
                                },
                            ]
                        }
                    }
                }
            },
            "webPrefetchData": {
                "navigationEndpoints": [
                    {"watchEndpoint": {"videoId": "pref789"}},
                ]
            },
        }

        candidates = YouTubeService.extract_related_candidates_from_payload(payload)

        self.assertEqual([item["video_id"] for item in candidates], ["rel123", "lock456", "pref789"])
        self.assertEqual(candidates[0]["title"], "Related video")
        self.assertEqual(candidates[0]["channel"], "Related Channel")
        self.assertEqual(candidates[0]["duration_seconds"], 754)
        self.assertEqual(candidates[0]["thumbnail_url"], "large.jpg")

    def test_extract_initial_data_from_watch_html_for_related_candidates(self) -> None:
        html = """
        <html><script>
        var ytInitialData = {"contents":{"x":{"compactVideoRenderer":{"videoId":"abc123","title":{"simpleText":"Demo"}}}}};
        </script></html>
        """

        candidates = YouTubeService.extract_related_candidates_from_watch_html(html)

        self.assertEqual([item["video_id"] for item in candidates], ["abc123"])


if __name__ == "__main__":
    unittest.main()
