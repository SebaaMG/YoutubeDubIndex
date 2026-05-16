# Reaction Discovery Strategy Recommendation

Date: 2026-05-16

Target app: local Windows desktop app for discovering YouTube videos with confirmed Spanish dub. Constraints: no server, no API key, no login, no runtime LLM, no audio download/transcription, and no manual taxonomy UI.

## Current Implementation Status

Implemented in `main` after the last two pushes:

- `resources/discovery/content_pool_v1.json` ships broad English content-search seeds for reaction-friendly discovery.
- Startup imports that file idempotently as `system_search` seeds using `content_pool_version`.
- The discovery worker now claims seeds with a deterministic 10-slot pattern: 7 content slots and 3 free YouTube graph slots.
- Content slots include `system_search`, `system_channel`, `user_search`, and `user_channel`.
- Free slots include `starter_video` and `related_video`.
- User-entered search/channel interests are saved permanently and immediately enqueue 150 candidates in a background thread.
- The catalog button now reads `Explorar 200` and inspects up to 200 queued candidates per click.
- No dynamic global ranking or catalog-side scoring was added in this phase. The existing `candidate_frontier.score` behavior and channel-diversity logic remain intact.

This means the active production approach is the pool-based discovery strategy, not the optional scoring phase below.

## Verdict

Use a minimal hybrid discovery profile:

1. Static `Original:` anchors from CristianGhost R descriptions.
2. A compact English theme seed bank derived from his actual reaction formats.
3. A fixed 70/30 seed mix: 70% content pool and 30% free graph exploration.
4. Optional future candidate scoring only if the pool mix still lets too much low-effort content dominate.

Do not rely on broad bans, `made_for_kids`, view thresholds, or duration alone. The real problem is graph convergence: the crawler is entering repetitive kids/brainrot clusters too often. The first fix is to feed the crawler better graph entry points while preserving the existing diversity and inspection flow.

## Evidence

- `docs/research/cristianghost_reaction_signal_profile.md` contains 460 Videos-tab entries and 5 Shorts from `https://www.youtube.com/@cristianghostreacciona`.
- Local check over the 50 newest channel videos found 42 descriptions with an `Original:` YouTube link, or `84%` of that sample.
- CristianGhost R's current core duration band is `10-30 min`: 333/460 long-form entries and 78/100 recent entries.
- The channel is not only creepy/mystery. Strong lanes include internet/platform commentary, creator drama, social behavior, community/chat, memes, media nostalgia, food/money/value, institutions, science/body/animals, and structured explainers.
- YouTube says automatic dubs can be generated for new videos and later for previously published videos, and may be regenerated over time. This supports periodic reinspection of rejected/no-dub candidates.
- `yt-dlp` supports YouTube channel tabs, search prefixes, metadata printing, and JSON output; this is enough to build profile resources without API keys.
- `pytubefix` documents multiple audio track discovery and default/extra audio track distinction, which supports the current approach of inspecting audio track metadata rather than guessing from titles.

## Why Not Hard Exclusion

Hard topic bans are too brittle:

- `roblox`, `minecraft`, `cartoon`, `kids`, and `animation` can be valid when the framing is `iceberg`, `dark side`, `lost media`, `horror`, `controversy`, `scam`, `explained`, or `history`.
- Many kids-ish videos are not reliably marked `made_for_kids`.
- Low-view videos can still be good niche reaction material.
- Duration is useful, but not enough. A 25-minute low-quality kids compilation and a 25-minute internet mystery both pass the same duration check.

The app should demote low-signal clusters, not reject broad topics.

## Implemented Data

The shipped resource is `resources/discovery/content_pool_v1.json`. It intentionally contains broad search terms rather than a hard taxonomy:

```json
{
  "version": "v1",
  "theme_queries": [
    "internet mysteries explained",
    "streamer controversy explained",
    "influencer scam exposed",
    "TikTok trend explained",
    "lost media explained",
    "internet iceberg explained"
  ]
}
```

Theme terms are not shown directly. They only create search seeds. Candidates still need inspection and must have confirmed Spanish dub before appearing in the catalog.

## Future Scoring Option

Scoring is not implemented in the current build. If the 70/30 pool still lets too much low-effort kids/toy/gameplay content dominate, compute score only when a candidate is enqueued. Do not compute text similarity in catalog queries.

Use cheap positive signals:

- `10-30 min`: strong duration bonus.
- `30-45 min`: smaller bonus.
- `why`, `how`, `explained`, `what happened`, `problem with`, `truth about`.
- `fake`, `scam`, `exposed`, `lied`, `worth it`, `failed`, `downfall`, `worst`, `out of control`.
- `YouTube`, `TikTok`, `streamer`, `influencer`, `Twitch`, `algorithm`, `Discord`, `Reddit`, `Instagram`.
- `iceberg`, `tier list`, `ranked`, `top`, `levels`, `timeline`, `rise and fall`, `documentary`.
- `caught on camera`, `dashcam`, `Google Maps`, `CCTV`, `recorded live`, `photos`, `footage`.
- social/culture framing: `Gen Alpha`, `Gen Z`, `dating`, `addiction`, `brainrot`, `internet culture`, `trend`.

Use weak demotions only when several low-signal signs combine:

- very short duration,
- repetitive toy/nursery/family/kids channel/title language,
- no adult/explainer/debunk/history/documentary markers,
- same channel already saturates the frontier.

The score should not reject anything. It should only change inspection order.

## Implementation Order

1. Import static profile seeds into existing `discovery_seeds`. Done for `content_pool_v1.json`.
   - theme queries become `system_search` seeds.
   - Gate import by an `app_preferences` version key so it is idempotent.

2. Claim seeds through the 70/30 mix. Done.
   - 7 content slots, 3 free slots.
   - Fallback to whichever pool has eligible seeds.
   - User search/channel seeds belong to the content pool.

3. Add optional candidate scoring only after the pool-based approach is measured.
   - Keep existing channel diversity ordering and same-channel seed dampening.

4. Add catalog `discover` sort only after discovery-side improvement.
   - Add `videos.feed_rank`.
   - Use indexed keyset order: `feed_rank ASC, random_key ASC, video_id ASC`.
   - Do not use `ROW_NUMBER()` or global `COUNT(*)` in UI queries.

5. Keep reinspection of rejected/no-dub candidates.
   - YouTube can add or regenerate dubs later, so `no_dub` is time-limited, not permanent truth.

## Success Metrics

Measure on the real DB after 10-20 discovery cycles:

- First 50 visible results contain at least 15 unique channels.
- Max channel concentration in first 50 is under 15%.
- New verified videos from profile/theme seeds have a higher useful-audit rate than current generic graph walk.
- The first 50 results are not dominated by raw kids/game/toy/cartoon clusters unless they have adult commentary framing.
- Explicit user search still returns matching videos even if they are low-score.
- `1M` and `5M` perf tests still use indexed keyset paging and no global blocking counts.

## Source Links

- YouTube Help, automatic dubbing: https://support.google.com/youtube/answer/15569972?hl=en-EN
- yt-dlp README: https://raw.githubusercontent.com/yt-dlp/yt-dlp/master/README.md
- pytubefix dubbed streams: https://pytubefix.readthedocs.io/en/latest/user/dubbed_streams.html
- Claude Opus 4.6 prompting guide used for the Claude delegation prompt: https://claude.com/resources/tutorials/get-the-most-from-claude-opus-4-6
- Claude debate artifact: `J:\Users\SebaM\.gemini\antigravity\brain\9a55c5b7-4bf7-49eb-b2d4-9861be9fddc0\artifacts\discovery_strategy_plan.md`
