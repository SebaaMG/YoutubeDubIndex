# CristianGhost Reaction Signal Profile

Research artifact for deciding discovery and ranking strategy for the local YouTube Spanish-dub desktop app.

Target creator: https://www.youtube.com/@cristianghostreacciona / CristianGhost R.

Date gathered: 2026-05-16. Tooling: `yt-dlp 2026.03.17`, no login, no paid API, no video downloads.

## Collection Method and Limits

Command used for the main sample:

```powershell
yt-dlp --encoding utf-8 --skip-download --flat-playlist --playlist-end 1000 --print "%(playlist_index)s`t%(id)s`t%(duration_string)s`t%(title)s" "https://www.youtube.com/@cristianghostreacciona/videos"
```

Result: 460 public entries from the channel Videos tab. The channel root produced the same long-form list plus Shorts. `yt-dlp` flat playlist mode returned title, video id, playlist order, and duration string, but view count and upload date were not available (`NA`) in this mode. Therefore, "recent" below means current channel order, not confirmed upload date. The collection cannot see private, deleted, unlisted, geo-restricted, or temporarily hidden videos.

Additional checks:

- `https://www.youtube.com/@cristianghostreacciona/shorts` returned 5 Shorts, listed in the appendix.
- `https://www.youtube.com/@cristianghostreacciona/streams` returned: channel does not have a streams tab.
- No public API key, login, cookies, or paid API was used.

## High-Level Read

CristianGhost R's reaction channel is not simply a creepy-video channel. The broader repeatable signal is "commentary-ready friction": a video gives the streamer something to judge, question, laugh at, compare, debunk, rank, or react to beat-by-beat. Creepy/mystery material is one lane, but the channel also heavily uses internet culture, creator drama, social behavior, food/money/value stories, games/TV nostalgia, memes, audience submissions, lists, and explainers.

The current long-form style has shifted away from explicit `CRISTIANGHOST REACCIONA a ...` titles and toward standalone editorial packaging such as `Por Qué ...`, `El Lado ...`, `X Era FALSO...`, `Cuando ...`, `Los ... Más ...`, and `Cosas ...`. Older videos have more explicit `CristianGhost Reacciona`, `Iceberg`, `Tierlist`, chat, and stream-context titles.

This matters for discovery: ranking should favor format and reaction-worthiness signals, not just topic keywords or a creepy-only dictionary. A broad ban like `roblox` would be brittle, but so would over-promoting every `creepy` result. The target profile is closer to "Spanish streamer can riff on an English video with clear premise, pacing, and judgment hooks."

## Duration Profile

From 460 Videos-tab entries:

| Band | Count | Notes |
| --- | ---: | --- |
| `<10 min` | 35 | Mostly older clips, memes, chat, short stream segments. |
| `10-20 min` | 211 | Largest band; compact reactions, memes, culture, commentary, clips with a clear premise. |
| `20-30 min` | 122 | Second-largest band; common for recent editorial reactions and explainers. |
| `10-30 min` | 333 | The main target band: 72.4% of the long-form inventory. |
| `30-45 min` | 68 | Secondary allowance for deep dives, social topics, histories, scandals, mysteries. |
| `45+ min` | 24 | Rare; mostly icebergs, tier lists, long mysteries, YouTube history, long reaction sessions. |

Summary: min 2:56, median 19.3 min, mean 22.4 min, max 1:26:19. Recent 100 entries have median 21.8 min, no `<10 min` entries, and 78/100 are in `10-30 min`. The practical local prior should be `10-30 min` first, `30-45 min` second, and `45-90 min` only when the title has a strong structured format such as `iceberg`, `tier list`, documentary/explainer, or major controversy.

## Coverage Audit

The first pass over-covered creepy/mystery examples. A broader regex audit over the 460 titles found these overlapping content families. Counts are not mutually exclusive because one title can be, for example, a YouTube drama explainer and a scam/downfall story.

| Signal family | Count | Examples |
| --- | ---: | --- |
| Lists/icebergs/rankings/explainers | 364 | `Por Qué...`, `Cómo...`, `Los ... Más ...`, `El Iceberg De...`, `TIERLIST...`, `25 datos...` |
| Creator/platform/internet commentary | 180 | streamers, YouTubers, TikTokers, YouTube, Twitch, Spotify, AI/algorithms, internet trends |
| Community/chat/viewer-made | 90 | `VIENDO MEMES QUE HIZO MI CHAT`, `CONFESIONES DEL CHAT`, viewers, Discord, stream bits |
| Drama/scam/downfall/debunk | 83 | falso, engañó, estafa, funado, fracasó, caída, peor, secreto, controversias |
| History/geography/institutions | 71 | Korea, CECOT, prison, villages, Chile, urban tribes, TV/history, places, police |
| Social/culture/behavior commentary | 62 | Gen Alpha/Beta, obesity, looksmaxing, seductores, gender, addiction, children, society |
| Memes/humor/cringe | 56 | memes, cringe, Reels/TikTok comments, laugh challenges, absurd clips |
| Weird/mystery/creepy | 96 | perturbador, raro, fantasmas, OVNI, leyendas, terror, turbio, impossible accidents |
| Games/TV/movies/nostalgia/fandom | 44 | Akinator, videojuegos, Nickelodeon, Simpsons, Chavo, Disney/Pixar, fandoms, lost media |
| Food/money/luxury/consumer | 36 | luxury flight, food, street food, Funko, Temu, scams, money/value, products |
| Visual/evidence/discovery | 36 | dashcams, photos, Google Maps, cameras, commercials, places, objects, screenshots |
| Personal/challenges/tests | 33 | tests, cooking on stream, haircut/fitness bits, `si me río`, viewer submissions |
| Science/body/animals/limits | 22 | humans, animals, body limits, IQ/culture tests, evolution, accidents, biology-adjacent topics |

Other title mechanics:

- 184/460 titles include an all-caps emphasis word of length 4+ (`PERTURBADORAS`, `FALSO`, `FRACASAN`, `INFIERNO`). Use this as a weak packaging signal, not as content semantics.
- 95/460 titles use ellipses, often as suspense or unresolved premise.
- 23/460 titles are question-framed; `Por qué`, `Cómo`, `¿Vale la pena?`, `¿Qué pasó?` are especially useful discovery equivalents.
- 49/460 include explicit `reacciona`; mostly older, not sufficient as a modern discovery signal.
- Recent 100 entries are broad, not creepy-only: creator/platform 45, social/culture 25, drama/debunk 25, weird/mystery 24, history/institutions 21, food/money 13, community/chat 13.

## Content Shape by Era

Current channel order suggests a content evolution:

| Segment | Median duration | Dominant shape |
| --- | ---: | --- |
| 1-100, newest | 21.8 min | Editorial commentary on internet culture, social behavior, creator/platform stories, scams/debunks, weird evidence, food/value, institutions. |
| 101-200 | 17.4 min | Mix of creator/platform, chat/community, drama, creepy/weird, plus longer icebergs. |
| 201-300 | 18.7 min | More icebergs, internet mysteries, stream/chat formats, fandom and controversy. |
| 301-400 | 19.3 min | Older reaction packaging, memes, games/TV/fandom, tier lists. |
| 401-460, oldest sampled | 14.3 min | Early explicit `CristianGhost reacciona`, chat, memes, stream clips, shorter formats. |

For app strategy, the newest profile should get more weight than the oldest: prioritize 10-30 minute English originals with a clear explainable premise, social/internet commentary, or structured list/ranking format.

## Source Themes and English Discovery Equivalents

The app mainly discovers English originals and then inspects for Spanish audio/dubbing. Seed/search language should therefore use English equivalents for the underlying source-video archetype, not Spanish streamer phrasing.

| Spanish source theme seen in titles | English discovery equivalents | Why it fits |
| --- | --- | --- |
| `Por Qué El YouTube Actual Se Siente FALSO?` | `why YouTube feels fake`, `the problem with modern YouTube`, `YouTube changed`, `YouTube algorithm explained` | Core modern fit: platform commentary with a clear argument. |
| `Streamers Que Terminaron Funados` | `streamer exposed`, `streamer downfall`, `cancelled streamer`, `Twitch controversy`, `YouTuber controversy` | Social judgment plus internet context. |
| `Este Tiktoker ENGAÑÓ A Todos...` | `TikToker scam`, `influencer scam exposed`, `fake guru exposed`, `creator lied to everyone` | Deception/reveal arc. |
| `La Generación Alfa Está Destinada a FRACASAR` | `Gen Alpha is doomed`, `iPad kids problem`, `brainrot culture explained`, `TikTok generation problem` | Culture commentary; should be adult-framed, not raw kids entertainment. |
| `Los Hombres Performativos Son Lo PEOR` | `performative men explained`, `male manipulator trend`, `TikTok dating trends`, `modern dating cringe` | Social behavior and internet-trend commentary. |
| `Los Algoritmos Están Cambiando Nuestra Personalidad` | `algorithms are changing us`, `social media algorithm explained`, `TikTok algorithm problem`, `internet addiction explained` | Strong non-creepy commentary lane. |
| `El Precio De La Historia Era FALSO...` | `TV show was fake`, `reality show was fake`, `Pawn Stars fake`, `scripted reality show` | Debunking familiar media. |
| `Funko Pop: De Valer Millones A Ser BASURA` | `Funko Pop crash`, `collectibles bubble`, `why collectibles lost value`, `failed product craze` | Consumer/value story with rise-and-fall structure. |
| `¿Vale La Pena Un Asiento De Avión De $15,000?` | `is it worth it luxury flight`, `$15000 plane seat`, `expensive first class review`, `luxury vs economy` | Value judgment, spectacle, and class commentary. |
| `Cosas ASQUEROSAS Encontradas En Comida` | `gross things found in food`, `food contamination stories`, `disgusting food discoveries` | Strong reaction payload without needing horror. |
| `La Comida Callejera Es Una PESADILLA` | `street food nightmare`, `dangerous street food`, `worst street food hygiene`, `food safety documentary` | Disgust plus travel/social commentary. |
| `Objetos Que La Historia No Puede Explicar` | `unexplained historical artifacts`, `history mysteries`, `ancient objects unexplained`, `weird historical discoveries` | Documentary/mystery crossover. |
| `CECOT: La Cárcel Más ESTRICTA Del Mundo` | `world's strictest prison`, `inside mega prison`, `El Salvador prison explained`, `dangerous prisons documentary` | Institution/geography/current-affairs reaction material. |
| `El Único Juego Que Nadie Ha Podido Superar` | `hardest game ever`, `game nobody can beat`, `impossible video game`, `gaming challenge explained` | Games lane with challenge premise. |
| `La Industria Del KPop Es Una PESADILLA` | `dark side of K-pop industry`, `K-pop industry explained`, `idol industry problem` | Media/industry criticism, not necessarily creepy. |
| `El Iceberg De ...` | `iceberg explained`, `internet iceberg`, `lost media iceberg`, `fandom iceberg`, `TV show iceberg` | Structured escalation; good for long reactions. |
| `Memes Que Esconden Un Origen MACABRO` | `origin of memes`, `dark meme origins`, `meme history explained`, `internet lore memes` | Bridges meme culture with explanation/history. |
| `Programas infantiles Tétricos` | `creepy kids shows`, `dark kids cartoons`, `disturbing children's shows`, `lost episodes explained` | Do not ban child-coded nouns when the framing is analytical/eerie. |
| `Roblox`-adjacent older titles | `Roblox horror`, `Roblox controversy`, `Roblox iceberg`, `Roblox explained` | Keep as soft positive only when paired with commentary, challenge, horror, lore, or controversy. |
| `VIENDO MEMES QUE HIZO MI CHAT` | `viewer memes`, `Discord memes`, `funniest viewer submissions`, `try not to laugh memes` | Community format; useful for manual/channel discovery, less reliable for English dubbed originals. |

## Reaction-Worthiness Signals

Use these as positive local features before expensive inspection:

1. Explainable premise: `why`, `how`, `what happened`, `the problem with`, `explained`, `the truth about`.
2. Judgment frame: `worst`, `best`, `fake`, `scam`, `out of control`, `doomed`, `horrible`, `worth it`, `failed`, `downfall`.
3. Internet/social object: `YouTube`, `TikTok`, `streamer`, `influencer`, `Twitch`, `Discord`, `Reddit`, `algorithm`, `AI`, `memes`, `fandom`.
4. Structured format: `iceberg`, `tier list`, `top`, `ranked`, `most`, `levels`, `timeline`, `rise and fall`.
5. Evidence object: `caught on camera`, `dashcam`, `photos`, `Google Maps`, `Street View`, `recorded live`, `CCTV`, screenshots, commercials.
6. Culture/behavior premise: Gen Alpha/Beta, dating trends, body/fitness trends, online addiction, social media behavior, kids/parents as a social topic.
7. Consumer/value spectacle: expensive travel, luxury, cheap products, scams, product bubbles, weird food, collectibles, money/lifestyle extremes.
8. Media/nostalgia/fandom: games, TV shows, cartoons, movies, music industries, lost media, old internet, childhood references.
9. Weird/creepy/mystery: paranormal, urban legends, mysteries, disturbing evidence, but only as one lane among many.
10. Packaging style: all-caps emotional word, ellipsis, question title, `the day that`, `the only`, `no one could`, `nobody knows`, `almost nobody`.

These signals should add score; they should not create hard gates. Some useful niche videos may have low views, sparse metadata, or unpolished titles.

## Avoiding Kids/Brainrot Overrepresentation Without Hard Bans

The problem is cluster dominance, not individual forbidden words. The profile suggests a soft dampening strategy:

- Penalize child-targeted clusters only when several weak signals co-occur: short duration, toy/nursery/family/kids channel name, repetitive cartoon/game title, no adult/eerie/debunk/history/documentary markers, and repeated same-channel frontier saturation.
- Do not hard-ban nouns like `roblox`, `minecraft`, `cartoon`, `kids`, `animation`, or `toy`. Promote them when paired with `iceberg`, `dark side`, `lost media`, `horror`, `controversy`, `scam`, `explained`, `disturbing`, `history`, or `why/how` framing.
- Treat `brainrot` as a topical signal only when paired with commentary framing (`explained`, `problem`, `generation`, `TikTok culture`, `trend`). Treat raw meme-compilation/shorts farms as lower priority by duration, channel repetition, and missing reaction-worthiness signals.
- Keep an exploration quota so low-view niche sources survive: e.g. 65-75% profile-scored candidates, 15-25% diverse related candidates, 5-10% random/cold candidates. View count should be a weak confidence signal, not a quality threshold.
- Prefer channel-level caps over topic bans. Existing discovery already counts active candidates by channel; extend strategy by making same-channel saturation a dampener even when individual titles look good.

## Scalable Local Scoring Sketch

The app already has deterministic metadata that can be scored cheaply at enqueue time: `title`, `channel`, `channel_id`, `duration_seconds`, `published_at`, `view_count`, `source_seed_id`, `discovered_from_video_id`, plus SQLite FTS5 over title/channel. For 1M-5M rows, avoid per-row LLMs or remote classifiers. Use normalized-title token features, integer weights, and channel-diversity quotas.

Suggested pre-inspection score components:

| Feature | Weight idea | Implementation note |
| --- | ---: | --- |
| Duration `10-30 min` | `+4` | Main profile center: 72.4% overall and 78% of recent 100. |
| Duration `30-45 min` | `+1` | Useful secondary band for larger explainers and controversies. |
| Duration `45-90 min` with `iceberg/explained/tier list/documentary` | `+1` | Long videos need structure; avoid making this a default preference. |
| Duration `<3 min` | `-3` | Often Shorts/clips; do not reject if very strong topic. |
| Duration `<10 min` | `-1` | Weak modern fit, still allow clips/memes. |
| Explainable premise terms | `+3` | `why`, `how`, `explained`, `what happened`, `the problem with`, `truth about`. |
| Internet creator/platform commentary | `+3` | `YouTube`, `TikTok`, `streamer`, `influencer`, `Twitch`, `algorithm`, `AI`, `Discord`, `Reddit`. |
| Drama/debunk/value judgment | `+2` | `fake`, `scam`, `exposed`, `lied`, `worth it`, `failed`, `downfall`, `out of control`. |
| Structured reaction format | `+2` | `iceberg`, `tier list`, `top`, `worst`, `most`, `ranked`, `rise and fall`. |
| Social/culture commentary | `+2` | generations, dating, body trends, social media behavior, internet addiction, parenting/kids-as-topic. |
| Food/money/consumer/luxury | `+1` | product bubbles, weird food, luxury reviews, money extremes, cheap/unsafe products. |
| Games/TV/media/nostalgia | `+1` | games, TV, cartoons, movies, music industries, lost media, childhood references. |
| Evidence/visual discovery | `+1` | `caught on camera`, `dashcam`, `Google Maps`, `photos`, `CCTV`, weird places/objects. |
| Weird/mystery/creepy terms | `+1` | `disturbing`, `creepy`, `ghost`, `mystery`, `urban legend`, `lost media`; do not let this dominate alone. |
| Packaging/title energy | `+1` | all-caps emphasis, ellipses, question framing, `nobody`, `impossible`, `out of control`; cap this so clickbait alone cannot win. |
| Child-target cluster density | `-2` to `-5` | Only when no positive adult/eerie/documentary marker exists. |
| Same-channel frontier saturation | `-1` to `-4` or later claim order | Prevents repeated kids/channel clusters from crowding the batch. |
| Verified Spanish auto-dub/manual dub | strong promotion after inspection | This is the app's final relevance gate; discovery score should only choose inspection order. |

Important: preserve the existing distinction between discovery ranking and catalog truth. A candidate can be low-priority without being rejected. Only dubbing inspection should decide whether it becomes catalog-visible.

## Deterministic Query/Seed Strategy

A no-configuration starter profile can be a small rotating set of English search seeds plus related-video expansion from verified hits. Keep seeds neutral and format-oriented:

```text
why YouTube feels fake
the problem with modern YouTube
TikTok trends explained
social media algorithm problem
streamer exposed downfall
influencer scam exposed
creator lied to everyone
Gen Alpha brainrot explained
modern dating trends explained
internet addiction explained
AI replacing jobs explained
dark side of K-pop industry
reality show was fake
TV show was fake
collectibles bubble explained
failed product craze
is it worth it luxury flight
street food hygiene documentary
gross things found in food
world's strictest prison
weird historical discoveries
unexplained historical artifacts
hardest game ever
lost media explained
cartoon controversy explained
iceberg explained internet culture
creepy Google Maps discoveries
disturbing dashcam footage
urban legends explained
```

Use these as seed families, not permanent exact config. Rotate them, measure verified-dub yield, then let related-video seeds from verified results take over. Keep the seed mix broad: platform/social commentary and creator stories should be at least as prominent as creepy/mystery seeds. To avoid self-reinforcing kids clusters, decay seed families that produce many rejected or repeated-channel candidates, but do not remove the underlying topic vocabulary globally.

## Practical Ranking Policy

A simple deterministic policy compatible with the current architecture:

1. Score candidates as soon as they are enqueued from search/channel/related discovery.
2. Store the score in the existing `candidate_frontier.score`; lower numeric `priority` can represent stronger seed/profile families while `score DESC` handles within-priority ordering.
3. Use title/channel tokenization with accent folding and lowercase; normalize Spanish and English dictionaries separately, because current sources may be Spanish while target originals are often English.
4. Keep the existing channel-count diversity ordering, and optionally add a stronger same-channel penalty before enqueueing when a channel already dominates queued candidates.
5. Reserve an exploration lane for low-view or unknown-view candidates with positive title patterns. Do not demote solely because `view_count` is missing or low.
6. After inspection, promote verified Spanish-dub videos regardless of whether they came from high-score or exploration lanes; use rejections to decay only the seed/channel path, not global topics.
7. Keep child-coded dampening conditional: apply it only when child-target tokens dominate and no adult/eerie/documentary/reveal signals are present.

## Top Findings for Strategy

1. The core duration target is `10-30 min`, not `10-45 min`: 333/460 long-form entries and 78/100 recent entries fall there.
2. The channel is broader than creepy/mystery. Major lanes include internet/platform commentary, creator drama, social behavior, community/chat, memes, media nostalgia, food/money/value, institutions, science/body/animals, and structured explainers.
3. The strongest transferable discovery signals are premise/format signals: `why/how/explained`, `problem with`, `fake/scam/downfall`, `worth it`, `iceberg/tier list/top`, creator/platform terms, and social-trend framing.
4. Use English query equivalents for originals, then inspect locally for Spanish audio/dubbing. Spanish title themes are useful as a seed dictionary, not as final candidate language requirements.
5. The scalable fix is a soft ranker with diversity and exploration quotas, not a rejection filter. It should reorder the frontier, preserve low-view niche candidates, dampen repeated kids/brainrot clusters by channel/title-density patterns, and avoid letting any one lane, including creepy content, dominate.

## Appendix A: Full Videos-Tab Title Inventory

Format: `index duration video_id title`.

```text
001	16:30	9ahwe1-qeBI	¿Por Qué Los Humanos Somos Tan Inútiles Al Nacer?
002	13:46	PHozgU4uCHM	VIENDO MEMES QUE HIZO MI CHAT #6
003	22:56	afHHnR6jKWM	Miniaturas Que Se Convirtieron En Memes
004	38:45	dKMoGRQF8LA	Cosas PERTURBADORAS Captadas Por Dashcams
005	19:41	tsHjRWcEPRw	¿De Dónde Salieron Estas Fotos?
006	32:13	0_apqhx3n5w	Streamers Que Terminaron Funados
007	42:29	vqvdIMyaS48	¿Vale La Pena Un Asiento De Avión De $15,000 Dólares?
008	26:53	j3dVw8lqVYI	Fantasmas REALES Que Aparecieron En Fotos
009	37:15	p45DJp5I0Q8	Según Esta Señora TODO Es Del Diablo
010	41:06	NZrJCb00mVM	El Precio De La Historia Era FALSO...
011	21:37	2QBdLfSZBR8	Este Tiktoker ENGAÑÓ A Todos Para Vivir de Donaciones
012	18:04	AZISb9gsdZ8	VIENDO MEMES QUE HIZO MI CHAT #5
013	28:20	niAiq1G6oHE	La Generación Alfa Está Destinada a FRACASAR
014	30:31	qbVUU8UGdas	Tener Superpoderes ARRUINARÍA Tu Vida
015	41:15	1g-jCaLHKkI	El Día Que Un Pueblo ENTERO Vió Al Ejército Cazar Un OVNI
016	19:06	owVUD6whwM4	Nunca Habrá Otro Youtuber Como El Rubius
017	17:22	SjnJKODjzg0	Cómo Akinator Logró Engañar A Todo Internet
018	36:48	-6RtwkCqO1w	Pizzagate: La Conspiración De Internet Más Turbia De La Historia
019	29:38	J5vQZp8f-XQ	El Único Juego Que Nadie Ha Podido Superar
020	15:26	jNQ041lyYOo	Ser Mujer En Internet Es Un INFIERNO
021	43:00	A-y42IitTww	Personas Admiradas Que En Realidad Eran HORRIBLES
022	18:18	AGm3MKoXBM0	¿Que Es Lo Más RARO Que Te Ha Pasado?
023	35:33	O9wiWIh1GCM	Descubrimientos PERTURBADORES De Google Maps
024	14:20	qqU9YlpUJgs	VIENDO MEMES QUE HIZO MI CHAT #4
025	50:16	1ede5QMri7M	El Streamer Más ODIADO De Chile
026	28:53	2F2UR5m0Hmw	El Metaverso De Mark Zuckerberg FRACASÓ
027	16:24	YDrAlCKJ-C8	Los "Seductores" De TikTok Están Fuera De Control
028	25:29	8MSUseuv0Os	Las Fortunas Más ABSURDAS Que Han Existido
029	12:46	3AG57aAYtlY	VIENDO MEMES QUE HIZO MI CHAT #3
030	19:41	6jF8mHvbjyI	Cosas ASQUEROSAS Encontradas En Comida
031	37:43	xp3le7x9ro0	La MERECIDA Caída de Borja Escalona
032	34:50	ewTNoViw0d8	La Brutal Realidad De La Comida De Prisión
033	35:13	h9yILAdqNH4	Leyendas Urbanas Que Casi Nadie Conoce
034	17:17	8jEGLV-sa6U	Memes Que Esconden Un Origen MACABRO
035	34:47	RCDiESXvZxY	Los Youtubers Más Hambreados De Internet
036	30:14	lgk15ufAVqk	Así Murieron Los Asesinos Más Famosos
037	23:17	Bgrcbx0gmh8	El Jugador De Basketball Profesional Que Se Hizo Amigo De Kim Jong Un
038	21:25	ljUCWJpXmeo	Roy Jay: El Hombre Que Según 4Chan NUNCA EXISTIÓ
039	22:09	CPnuFyT0kCI	Normalizar La Obesidad Es Un PELIGRO
040	13:15	7tD16LNuNKg	VIENDO MEMES QUE HIZO MI CHAT #2
041	27:18	CViMXeIdDAM	Cuando Los Policías Arrestan a La Persona EQUIVOCADA
042	31:00	skG3Go08y2k	Los Casos De Reencarnacion Más Creibles
043	21:02	jOK9wqBfX3k	El Lado OSCURO De Los Cibers
044	49:14	fml_GTizM0k	Los Descubrimientos Más Extraños De La Historia
045	26:31	3ox5SOpcXx4	Cuando Los Mundos Virtuales Se Ponen TURBIOS
046	18:28	iX9ExLqX0MA	El Curso de Looksmaxing Que Terminó Acusado de Estafa
047	26:58	KY8dCQpzzKs	Objetos Que La Historia No Puede Explicar
048	32:03	dr01T1RTF4Y	CECOT: La Carcel Más ESTRICTA Del Mundo (Nadie Escapa)
049	26:37	G86uHxMHzAU	El Genio Matemático Que Escapó de Corea del Norte
050	21:21	csnoH4WMgRI	La Comida Callejera Es Una PESADILLA
051	21:21	eTm0fQD5ylg	Cuando Los Gringos Se Ofenden Por Videojuegos...
052	26:03	2y6WeWeOzrE	Por Qué El 99% De Los Streamers FRACASAN.
053	16:54	j9JZ351fVQ8	Llamó a La Policía Por "Seres No Humanos" En Su Patio...
054	24:39	5tboniGUA-k	El Iceberg De La Existencia Humana
055	36:43	oLPR0RxoZak	Los Horrores De Ir Al Cine
056	14:54	PSI3tmyMqiY	Los Comentarios MÁS CRINGE De TikTok 🥀 | CristianGhost Reacciona
057	28:26	POZJ5Ook--U	Las Señales De Advertencia Más PERTURBADORAS
058	19:06	bQ7POH7vsqY	TIERLIST DE PLACERES DE LA VIDA
059	20:57	HGMyPvhK20c	Una Chihuahua En Beverly Hills Era RARISIMA
060	19:46	Ii5PJqg3QS0	CURIOSIDADES QUE NO SABIA Y QUE SE ME VAN A OLVIDAR
061	29:58	JTOUGU_LpuM	La Decadencia Del Terror De Internet
062	27:54	SfXBiTizxjU	El Origen Real De Videos PERTURBADORES
063	19:10	XNKkexoeebY	Los Imitadores De Michael Jackson Están LOCOS
064	17:15	5S2hL918KNk	Los Niños "Emprendedores" Son Un Problema...
065	30:22	IVyjN2kvMaM	Los Anuncios De YouTube Son HORRIBLES
066	13:48	-fwoT2tX3Og	Los Migajeros Están Fuera De Control
067	10:02	vNUD8B9Q3xk	VIENDO MEMES QUE HIZO MI CHAT
068	13:57	yCIrlt15neA	Era Estrella De Nickelodeon, Ahora Vive En La Calle...
069	20:57	DPG9H8zMZ80	REWIND CHILE 2025 | CristianGhost Reacciona
070	28:48	p6dmUkuhYew	Funko Pop: De Valer Millones A Ser BASURA
071	18:34	wDWIi8XI_Oc	Viajar A La India Fue Su PEOR Error
072	18:30	e0S1YnQMxGc	Por Qué El Youtube Actual Se Siente FALSO?
073	17:42	2WnQ6EEW1rw	Estos Streamers Tienen Millones Pero Viven En La Basura
074	21:53	bRm4O6fWdnw	Arruinar La Salud De Tus Hijos Por Visitas es LAMENTABLE
075	22:55	nAOFukzRZYk	El Hombre Que Creó Vida Humana En Un FRASCO
076	26:54	MtqfiR_acRw	Los Hombres Performativos Son Lo PEOR
077	15:40	SWfzIdAsDlA	Todas Las Teorías Sobre La Vida Después De La Muerte Explicadas | CristianGhost Reacciona
078	18:53	oIm2CXc2uzE	El Lujo Es Una ESTAFA...
079	20:32	702qbHOzm6o	Chileno Reacciona a Ibai Probando Comida Chilena
080	21:29	zY0IFQ6--sg	Los "Estoicos" De TikTok Son Muy Raros
081	26:28	Xw7XSCMts5s	La Industria Del KPop Es Una PESADILLA
082	21:53	txfJNWjZ8nU	Cuando las Copias Chinas Van DEMASIADO LEJOS...
083	28:57	c-xUJI_m2xA	Los Algoritmos Están Cambiando Nuestra Personalidad... | CristianGhost Reacciona
084	14:58	3SYbTjgy_Bk	La TV Norcoreana Es Aterradora
085	20:47	uK2WJAOLMCo	El Origen SECRETO De Spotify…
086	23:17	4tiDzmgms1E	La Descubrieron Haciendo Trampa y Culpó a Los Hombres...
087	14:23	AREwHzlUu24	Cerró Un Negocio Con Un Solo Video.
088	21:38	GnwOoH5FI-4	Tacaños Extremos Era FALSO...
089	17:41	Uzyt6P8kE2o	Este Robot Te Quiere Reemplazar...
090	28:51	cna3p2teBcM	Villanos De Terror Que Podría Vencer
091	13:16	WXmnOuwHSqE	La Generación Beta Está Perdida... | CristianGhost Reacciona
092	21:37	G08DHrLhPJI	Las PEORES Tribus Urbanas Modernas
093	12:04	SbXjQcnb8gc	Personas Que Sobrevivieron Accidentes IMPOSIBLES
094	11:42	WIJnPJYS9-g	El Museo De Los Warren: El Lugar Más MALDITO Del Mundo
095	17:43	Xk5RCxwnPc0	Hay Algo Muy Raro Con Estos Youtubers De Corea Del Norte...
096	12:32	LJDgAfSejT0	Comentarios Brainrot En Canciones Tristes
097	24:36	02iw09HFJC4	La IA Que Intentó MATAR a Su Creador...
098	47:09	pYY2lzrA38o	Los Casos Mejor Documentados De Encuentros OVNI | CristianGhost Reacciona
099	23:50	HUPhOci0qkI	La Oscura Verdad de TEMU | CristianGhost Reacciona
100	15:06	RLhTMuYS6-I	Estamos En La PEOR Época De Internet...
101	18:37	t2vBJyHbHvg	Los Hoteles Más RAROS Del Mundo (No Entiendo Nada)
102	23:01	nWT-ffEpL2w	La Isla Más POBLADA Del Mundo (No Te Puedes Ni Mover)
103	19:44	NuJZWvQCNq4	El Hombre Que Construyó Una Máquina Del Tiempo y DESAPARECIÓ...
104	16:31	RwbPc3fVTd4	Cosas INQUIETANTES Encontradas En Videojuegos
105	12:50	K20OXDMmuNA	Los “Artistas” de TikTok Son Cada Vez Más RAROS
106	25:16	oXC7Mn9M6gE	Los Momentos Más Peligrosos De Luisito Comunica | CristianGhost Reacciona
107	28:02	R4-Y9nTVPRI	El "Gran Hermano" Clandestino Que Acabó En TRAGEDIA
108	28:27	l0dy2L6oF4M	El Mono Morado Que DESTRUYÓ Internet: Bonzi Buddy
109	17:16	KMN6NSJNkqY	GENTE PROYECTÁNDOSE EN INTERNET
110	42:50	nrDy2zZJ2KM	LA TIERLIST DE SILLAS DEFINITIVA
111	1:19:24	qKDwXvjkbxk	El Iceberg más Perturbador y Polémico De TLC | CristianGhost Reacciona
112	15:35	1pA9-_pzg0s	CUAL FUE TU PEOR PRIMERA CITA?
113	30:16	n6rWKCiSazM	Rumores BIZARROS De Hollywood
114	13:56	WWI2-USLTWk	La Generación Alfa Está Perdida... | CristianGhost Reacciona
115	45:04	EtLBL5B7Yao	LEYENDAS URBANAS GRINGAS
116	14:45	8_Ublx_C6RE	DESDE HOY DEJO DE SER GORDO.
117	1:21:26	CFxYKR-bouo	El Iceberg De Los Reality Shows Más Perturbadores | CristianGhost Reacciona
118	20:26	3_OF0l7f4JQ	Lo De D4vd Se Puso Mucho Peor...
119	21:46	1XfW2ayLoio	Todo Este Pueblo Es Adicto a La Coca Cola...
120	15:30	tZ5mENcgcq4	El Caso De D4vd Es Muy Turbio...
121	31:24	SPk3N1_0Xps	Los 10 Animales mas RAROS de LATAM | CristianGhost Reacciona
122	35:36	bpG8nuqVfE8	El Iceberg De Leyendas Urbanas De Chile
123	15:54	8ZwWIFm3gkI	25 DATOS QUE SE ME VAN A OLVIDAR EN 5 MINUTOS #2
124	20:48	odtL-UJKHio	Limites EXTREMOS Del Cuerpo Humano
125	1:06:50	q76I4Ht6if0	Las Cosas Más PELIGROSAS Que Hacemos Sin Darnos Cuenta...
126	13:30	Zf8uvjsDG1E	Comentarios CRINGE De TikTok... 😭🥀| CristianGhost Reacciona
127	32:08	MWssm9kqMJ4	Las Muertes Prehistoricas Más HORRIBLES
128	23:22	MZmUn38aoaw	Las Muertes Más Ridículas De La Historia | CristianGhost Reacciona
129	21:11	uo2QGnLLVSY	La Vida Explicada En 21 Minutos
130	33:03	TjJAlhfSazI	25 DATOS QUE SE ME VAN A OLVIDAR EN 5 MINUTOS
131	37:35	2Kp9fkkOd1U	Las Comidas Rápidas Más Extrañas...
132	37:07	eWtQh9nDJbM	El Iceberg De Leyendas Urbanas Japonesas
133	13:42	Hn7-Z8eX-Jk	Lo Funaron Otra Vez...
134	28:23	v4--BP61Hls	Por Fin Voy a Hablar Sobre Esto...
135	15:50	CTQww9lNTyM	Streamers Que Olvidaron Que Seguían En Vivo
136	20:44	Uma0NaunsMg	El Mono Más Inteligente De La Historia...
137	12:33	0PuwbYNAxp4	Simulando una Colonia de Hormigas por 1000 Días | CristianGhost Reacciona
138	12:44	It4zxeMahKw	Shorts Are Destroying YouTube. | CristianGhost Reacts
139	9:23	WMScgstwHtc	chat I don't look anything like you
140	55:13	gqMJHupLPB8	THE ICEBERG OF SHOCKING THEORIES (Conspiracies, Secrets, Mysteries) | CristianGhost Reacts
141	11:26	J4thLNt1nN8	HICE UNA COCADA GIGANTE EN STREAM
142	14:02	Lkg-BG5EvH8	Mis Viewers Me Hicieron Miniaturas...
143	10:00	_-idbAJDlyc	Reaccionando a Videos Con 0 Visitas
144	51:49	eaFDraTP8k0	El Iceberg De Objetos Peligrosos | CristianGhost Reacciona
145	12:11	zRwfr3z1kY8	Mi Chat Hizo a Mi Gata En W PLACE
146	12:16	1Om7flgEp3o	VIENDO MIS HISTORIAS ANTIGUAS DE INSTAGRAM...
147	14:48	MqIPndp8uxM	Videos ESCALOFRIANTES De Fantasmas
148	41:45	4MN3mOvbFDI	Comerciales Prohibidos En La Televisión
149	23:27	UEi8AeD114o	HICE UN QUEQUE EN STREAM
150	19:57	80hjhZZS1Xg	ME DEPILÉ CON CERA EN STREAM...
151	38:21	N9tQuKfY840	Los Seres Humanos MÁS RAROS De La Historia...
152	20:25	0VRuwY-fVPg	CONFESIONES DEL CHAT 3
153	14:27	D7sVhNQMaj4	MASCOTAS FEAS DE MIS VIEWERS...
154	1:00:53	5BJ8BOqccB8	¿Cuál Fue La ÉPOCA DORADA De YOUTUBE CHILE? | CristianGhost Reacciona
155	57:00	bJDIf1VeY5g	El Iceberg De Datos Perturbadores | CristianGhost Reacciona
156	15:36	XyEe0wfWKSw	ibai debería demandar a los miniatureros de los críticos
157	38:51	qK9DVGAbd60	El Iceberg De Aimep3 | CristianGhost Reacciona
158	21:18	zIwuPzhYjaE	Está Mal Que Las Latinas Se Crean Coreanas?
159	11:50	PrNlpzIiQZY	viendo memes que me hicieron mis viewers
160	24:54	WhycptLj6g4	La Página Web Más Peligrosa De La Historia | CristianGhost Reacciona
161	17:33	bzfiz3rmC9k	Rostros Que Causaron Pesadillas | CristianGhost Reacciona
162	22:57	3HyGzSRLeIA	MrBeast Arruinó YouTube.
163	10:51	Mdj1x2JEOVE	cristian me incomoda el brillo de tu calva, ponte pelo porfavor
164	14:31	V5oj-nWc8Pw	que clase de edits son estos 💀
165	25:00	feZ1qXfujdA	Los 8 Colores de Ojos y Qué Ventaja Evolutiva Esconden | CristianGhost Reacciona
166	22:30	v_XZSL-KNXw	Cada Fallo De La Vida REAL Explicado | CristianGhost Reacciona
167	16:04	_6c7O0HV0JU	Jarvis, Hazme Negro
168	33:32	NufU8TWGsd8	Así Es Como Los Hoteles De Lujo Te Sacan Dinero | CristianGhost Reacciona
169	39:45	vp_vJ3EA0tw	El Iceberg Del Chavo Del 8 (Capítulos Turbios y Perdidos) | CristianGhost Reacciona
170	10:05	obS-qxmkVos	viendo tiktoks chinos (no entiendo nada)
171	28:14	bp-iYDnq41M	Los Gringos Arruinaron La Gastronomia?
172	10:03	xVmINhQ6jrM	mi chat me agregó a google maps...
173	10:07	wUVecoyAlDQ	realmente los chinos venden cualquier cosa
174	10:18	8GeuQJZ-vw0	chat les juro que no le di like
175	10:07	A2ikKkzvfa4	Mis Viewers Me Mostraron Su Ropa Más Chistosa
176	11:21	qDqjcoE2g-s	no voy a josear en clase
177	21:30	tWJ8kKHotms	Las Adicciones Modernas Nos Están Destruyendo | CristianGhost Reacciona
178	9:50	2X2AoT-O51c	chat les juro que la dieta es real
179	10:06	WyGGObcZ3no	Así Voy A Quedar Después De Mi Cambio Físico
180	13:33	YSKGqQxpMOo	Lo De Los Labubu Se Salió De Control... | CristianGhost Reacciona
181	9:51	c4EtY6wCZvQ	Mi Chat Es Demasiado Raro...
182	21:47	G-Cf4qfoIPY	Los Logos Más Polémicos Explicados | CristianGhost Reacciona
183	10:31	RieW7gmY-iw	Mis Recomendaciones De Youtube Se Pusieron Raras
184	9:57	R62abwpa-e8	Me Hago Las Medidas Y ChatGPT Me Dice Gordo
185	13:04	a2DdvkdYhGk	Debería Ser Ilegal Cocinar Así...
186	15:07	tsWMXnCUous	Me Busqué En Google...
187	10:19	FEQy3UM4YEM	Las Peores Publicaciones De Facebook Marketplace
188	8:37	kTCb91YLs2o	Me Arrepiento De Haber Visto Estos Reels 🥀
189	10:56	4ggRJgbnyf0	La Situación De Alana Es Muy Triste...
190	11:05	Rqkd9w7DADU	Los Streamers Van a Ser Reemplazados Por La IA
191	9:39	btV2VstIXOM	Tengo Las Peores Fotos De La Infancia 💀
192	15:56	qG5M6dcnBOQ	Me Corté El Pelo En Stream...
193	10:19	Mf4xHgcUSZM	El Meme Llegó Muy Lejos...
194	9:00	aOhjZBmgNsI	En Chile Están Peleando Por Un Tostador...
195	41:47	LInJINq9x_s	Objetos Mexicanos Que Están MALDITOS
196	27:10	GZqT0iFLIk0	Riéndome Por 27 Minutos De Las Top 10 Bizarradas De July3P
197	10:35	auB7w2GcVA4	Mi Chat Me Hizo Reir Con Memes De Discord
198	15:19	qn0jIbZHx0w	CristianGhost Hace Un Test De Autismo
199	19:23	6EAOOget8U8	El Hombre que Hizo Trampa Frente a Millones
200	1:11:47	WILGLL9U270	La Tier List De Perros DEFINITIVA (198 Razas)
201	12:22	sMEqQWzuL3g	Estatuas Feas Que Deberían Ser Demolidas
202	13:54	1zOhBVJnmfs	Paquetes Turbios Recibidos Por Streamers
203	22:29	1v9eQV6mZeA	OPINIONES FUNABLES DE MI CHAT
204	16:08	2Jo0P08WeaE	Riéndome De Piñatas Feas Que Encontré En Google
205	13:42	8DOIKDeBW4k	Gente Con Gustos "Raros"
206	20:29	KPky-d9pmXg	CONFESIONES ANÓNIMAS DE MI CHAT
207	15:51	Z9YEdxqv0Y0	El Caso Peruano De Aliens Más Convincente
208	12:42	ZBeOXG6IqMA	Qué Le Está Pasando A Justin Bieber?
209	12:29	w_2J5eY3ACw	Se Le Incendió El Ferrari Al Primer Día... (Y Más Noticias)
210	21:19	qw7jlZRvVrA	Las 15 Mayores Donaciones De La Historia | CristianGhost Reacciona
211	12:23	wq-tayUAU1A	Los Oscars Son Una Mentira...
212	37:46	XyHLfkFYeCQ	D.B. Cooper, El Hombre Que Humilló Al FBI
213	9:49	L7rqkrH-hvg	AriGameplays Ahora Es Cantante 💀
214	12:57	H9ILhCy4WEo	Streamer Sin Estudios Intenta Jugar Timeguessr
215	10:05	IOgvhU7kZvU	Mis Reels Están Muy Raros 💀
216	41:00	gtKtmdkbTkY	Streamer Que No Trabaja Reacciona A Trabajos Horribles
217	12:13	8pTavwrHY44	Streamers Que Fueron Engañados En Vivo
218	37:01	y0Zamsx6j9w	Los "Hoteles Gamer" Más Raros Del Mundo
219	1:26:19	6arS3L1Giro	1 Hora y 26 Minutos De Misterios Sin Resolver
220	14:33	PyRSQu3WXWI	Cosas Terroríficas Encontradas En Casas
221	26:29	n6AjqzCUzrI	Lugares Que Cientificamente No Deberian Existir
222	1:09:32	s5X2c--tS8U	El Iceberg De Los Sitios Web Más Perturbadores De Internet | CristianGhost Reacciona
223	24:36	odqk_AVTKeE	TIERLIST DE COSAS QUE DAN MIEDO
224	16:00	Erp5SIackfg	Top 5 Tik Tokers Con Peores Rugidos De Tripas ☠️ | CristianGhost Reacciona
225	37:12	8DmhCKQF4Ms	El Lado Oscuro De Google Maps
226	12:10	PVkeFiLoT8w	Chat Por Qué Me Hacen Esto 💀
227	1:05:29	-4oxLTVYVHw	Las Cosas Más Perturbadoras Captadas en una Transmisión en Vivo | CristianGhost Reacciona
228	12:32	Z6NNeuzIUws	El Gran Secreto de Homero Simpson | CristianGhost Reacciona
229	16:47	iqDztsxnTfQ	Los Memes De Ahora Son Rarisimos
230	21:12	UTEOAIHNy78	BRAINROT: La Evolución Más Extraña de la Comedia | CristianGhost Reacciona
231	13:34	YF1Byf0pI9U	Este Clip Me Persigue 💀
232	11:06	nG5aasDYl_o	Los Famosos Arruinaron a Los Simpsons
233	16:39	CuM2hIQ62PI	Le Regalaron Una Moto Y Una Casa A Una Streamer
234	22:26	kUnJ3J5uWWM	Este Video Perturbó A Millones De Personas
235	22:14	Dgon-1aikC8	Las Peores Cosas Que Ha Hecho Homero Simpson
236	15:37	HpMcIVhEz4g	4 Casos Curiosos De Lost Media
237	9:12	BmH-DU44MZ4	QUIERES SER CHILENO?
238	19:44	oPu9TtYU2Qs	Por Qué El Futuro En Los 2000 Lucía Así | CristianGhost Reacciona
239	17:03	1_va_R6s6uU	La Lenta, Dolorosa y Avariciosa Muerte De Angry Birds
240	13:48	oJASq2OIaCM	Ibai Quiere Ser MrBeast
241	10:28	OEOjStkcrVw	Hice Un Brownie De Microondas Con Mi Chat
242	38:03	_tLj1ZBt4kg	Probé "Jugar" en CADA Asiento de Avión. | CristianGhost Reacciona
243	11:20	S6NPnvo_yIU	Buscando Comentarios Brainrot En Shorts De Youtube
244	18:52	L-6OQQUzou4	Famosos Millonarios Que Lo Perdieron Todo
245	18:34	-3MLhQrxFjM	Videos Japoneses De Terror Que No Deberías Ver Solo
246	17:55	6N4eSZgYXkM	¿Cómo TIKTOK arruinó el CINE? | CristianGhost Reacciona
247	23:01	0zgW8K2bJVY	¿HAS VISTO A ESTE GATO? La Historia De Kush Cat | CristianGhost Reacciona
248	20:41	VCxGJZzPVwM	Mis Viewers Me Mostraron Sus Tazas
249	10:08	KmJasb6bPBk	Videos De Terror Claramente Falsos 💀
250	20:51	wfqQ_3sLPAI	El Iceberg De Los Screamers
251	25:38	ib1VL7ibHy4	Florida Man: Los Criminales Más Tontos Que Existen
252	10:29	Uiz6dOFxMyU	Obligué A Mis Viewers A Imitar Personajes
253	26:23	UWX9R9wT85s	RETOLAM: El Ser Inmortal De Tiktok
254	15:24	EI65th-pW0o	Si Me Rio Termina El Video
255	40:23	v97wgEPrKzg	Programas Infantiles Aterradores Y Perturbadores
256	14:54	MG5l23Xm2OE	Probé El Ramen Más Picante Que Encontré
257	27:15	ApueUY-G0QA	Charlie Y La Fábrica De Chocolate Da MIEDO
258	28:01	QcW02P78RZs	Los Animales Más Terrorificos Del Mar
259	27:36	Oi5QXvV8F0w	Las Comidas Más Raras De Latinoamerica
260	25:04	fTPfMwqJ-y4	¿CUÁL FUE TU PEOR EXPERIENCIA AMOROSA?
261	45:31	eQa1T9BUOx8	El Iceberg De Los Misterios De Internet
262	51:05	BZAYlgxLVTw	El Iceberg De Los Fandoms Turbios
263	11:56	73cYawlRayw	La Serie De MrBeast Es Cruel?
264	26:22	v3ifWwSgwOo	Tier List De Tazas Que Tengo En Mi Casa
265	21:12	F8zCgjY27pk	La Triste Realidad De Este Youtuber Infantil... (Ryan's World)
266	16:10	4iRe1LHoowA	Momentos En Los Que a Streamers Les ROBARON En Vivo
267	32:47	w5mWWOBYcKs	Shifting: El Fandom Que Genera PSICOSIS
268	11:15	Sck4FU_qodc	Kanye Está Peor Que Nunca...
269	13:06	PgsEK1ojqM0	Reaccionando A 10 Videos De Miedo Que No Deberías Ver Solo
270	39:12	FzA5V--dZhY	Las Peores Tendencias De Tiktok
271	25:38	Sgis7RVmGSc	Momentos En Los Que Streamers Salvaron Vidas
272	10:29	lJFq9yHBPeU	Riéndome De Estupideces Por 10 Minutos
273	17:26	H4jB97fzvG4	Cuando Los Youtubers Se Meten Con Gangsters De Verdad
274	21:41	mnJfEb14-So	Crímenes Inspirados Por Creepypastas
275	26:00	TNDclXcrefY	CONFESIONES DEL CHAT 2
276	1:19:43	8t10qwFFBf8	Las Controversias Más Grandes de YouTube
277	11:23	z1UeJq-4jz0	Fernanfloo Volvió y Lo Recibieron De La Peor Forma...
278	13:55	gt9GJOJgd4E	Riéndome De Cosas a Las Que Les Doy Like
279	33:56	ztMnwZXxb9Q	Los Peores Castigos En La Historia De La Humanidad
280	23:30	jruCeZuJdCI	Tier List De TODAS Las Series De Cartoon Network
281	14:54	ahkSmrVfwyI	Todos los Niveles de Internet Explicados
282	30:27	tIr3_xHV47U	50 Datos Perturbadores Sobre Disneylandia
283	10:07	OqDPHmL8nVQ	Los Videos IA De Got Talent Son Horribles...
284	32:01	T-HNR6uXCcI	Este Fue El Peor Momento En La Historia Para Ser Humano
285	18:34	ixaU5VyAZ98	El Vendehumo Más Grande De Argentina
286	17:04	LhBQFfltHdw	Coincidencias Captadas En Cámara
287	25:41	bNOBnRnxQ6g	Creepypastas Que Resultaron Ser Reales...
288	8:10	ABSNo1kL0Bw	Los Peores Reels Que He Visto
289	19:42	5Rytw74Wc24	El Iceberg De Temu
290	14:43	VXTSwqvrP28	La Ciudad Más Obesa De Estados Unidos...
291	24:18	-lUM-BWwNiY	Mi Chat Me Obligó A Ver El Iceberg De Pou
292	12:56	WNWdi9DFR5k	La Situación De "Mateo Yo Guapo" Es Muy Triste...
293	19:01	8FLXZlE4xqM	Es El Fin De Los Streamers...
294	13:07	l9N_dYtsoiw	La Influencer Más Falsa De China
295	33:53	-sJm14B2Avs	Profecías Para 2025 Que Ojalá No Se Cumplan...
296	27:08	jIYvybmOjL8	Están Funando A La Warensita...
297	27:15	es1IKIBjb2U	El Iceberg De Lo Perturbador Del Oceano
298	11:01	k0Ccvhfys-M	Si Te Da Cringe, Pierdes 💀
299	41:04	ZhlowVo3M3k	Animales A Los Que Les Podría Ganar En Una Pelea
300	17:22	Llcha2BsQds	Referencias Que No Entendías De Pequeño
301	11:33	A4HXxaFurVM	Perdió 10 Años De Matrimonio Por Un Beso...
302	19:16	PfAULjS-qNs	¿QUÉ ES LO MÁS TONTO QUE HICISTE DE NIÑO?
303	19:17	I_QcjeyNgQg	El Lado Oscuro De Tiktok...
304	29:40	G95HxX3JWz8	El Iceberg De Pixar
305	26:21	HGJ70UKi1M0	Los Mejores y Peores Hobbies Para Hombres (Según Mujeres)
306	18:53	wExl62Tkl2k	¿QUÉ ES LO MÁS RARO QUE HAS VISTO EN LA CASA DE ALGUIEN?
307	8:34	Js-rqI87UqA	Reels Muy Raros De Instagram
308	19:06	wivpyVBYElk	Probó TODAS Las Adicciones Legales
309	30:37	h7Js3jc7f-0	El Iceberg De Los Juguetes Prohibidos
310	10:16	2Z-tWtQ58Jk	MEMES MALOS DE DISCORD
311	38:55	TgCfvOWaRoA	Les Pedí Fotos de Sus Habitaciones... Me Arrepiento
312	12:23	BIEqzeTWvTk	La Espantaviejos
313	36:03	wyXRChs8hYc	Animales Actuando Como HUMANOS
314	53:11	oVsfoxeqrNk	El Iceberg Del CRINGE
315	15:44	8vRu3guMHos	Solo Es Un Tipo Tranquilo y Chill...
316	17:09	GNCZ8jhjDTk	Comerciales Que Envejecieron Mal
317	27:33	aCa77bd9Kgw	AriGameplays No Merece el Odio Que Recibe
318	22:41	GEUXjsjH__M	SHREK Es La Mejor Saga Que Has Visto
319	10:45	A6XgVLg4AfI	La Convención Furry Que Fue Un Desastre
320	27:44	msPVOLgGfaQ	10 Veces Que Intentaron Funar a Fernanfloo (No Funcionó)
321	20:41	s1ybZF0QlR4	Todos Los Niveles Del Infierno Explicados (Infierno de Dante)
322	24:36	NKRUEQYbOx4	El Rapero Que ESTAFÓ A Sus Fans...
323	10:31	Ki02sLrkdLc	Los Streamers Koreanos Lo Cazaron Por Faltar El Respeto
324	22:45	ib19LXlaUnE	Mitos Raros De Paises Latinoamericanos
325	12:40	VTe8pvR0s5A	El Nuevo Producto de MrBeast Es Un FRACASO
326	27:05	NO-EasCufw0	Lo Más TURBIO De La Comida Rápida
327	39:23	kNPB-FfWQng	El Lado Oscuro De IShowSpeed...
328	32:18	CsCJJlvUdVc	El Iceberg De Golosinas PROHIBIDAS
329	35:04	c16zMkNWzUg	4Chan Encontró El Rostro De Dios...
330	24:30	rJUnHDizSbY	El Juego De Celular Que Espió a TODO Internet
331	30:41	JjzPksEFpoI	SUPERCOOL Es La Mejor Película Que Has Visto
332	26:21	n9Loh2fU4g4	Los Sabores de Coca Cola Más Raros Del Mundo
333	21:37	c7lWUedbTfg	Cada Tipo De Hombre EXPLICADO
334	10:47	l60LAsU2Gys	Baños Raros Que No Deberían Existir
335	29:55	sy6gTz9S1Qk	Los Criminales Más TONTOS
336	19:45	6IeVp7RXWJc	El Selfshipping Es Muy Raro...
337	16:54	JBO78HUAmG0	Ahora TODOS Odian a Khaby Lame
338	32:32	MofDDztPQWE	P. Diddy Es Lo Peor Que Le Pasó A Hollywood...
339	13:34	1GY1HDs192A	Mis Viewers Hicieron Videos Graciosos Con IA
340	11:45	wFvOmcqaBh8	Las Relaciones De Streamers Son FALSAS?
341	19:37	vqoar5MCSZs	Las Mujeres Que Hacen Berrinche Son LO PEOR
342	34:53	3HiFXZ3Ou20	Chileno Reacciona a Illojuan Probando Dulces Chilenos
343	9:10	gBValtCRQjU	Buscando La Mejor Comida Típica Chilena
344	19:39	mxoEKCA0o-I	Los 10 Casos Más ATERRADORES De Chile
345	9:04	Lh947CpUa0Y	Los Disfraces Más FEOS De Internet
346	11:04	JuNvArkWJHM	Esta Silla Tiene Lore...
347	12:01	2Yq8dxVRuf0	Smash Or Pass Cuestionable...
348	35:36	z3C7G__CiH4	La Situación de Doña Lety Es Una LOCURA
349	26:29	BH-Re-piyMc	Páginas Que NUNCA Debes Visitar
350	28:08	kY5lpAZGx_k	Las Novias de 4Chan...
351	33:46	56HAJaaMQIk	El Lado OSCURO De Facebook Marketplace...
352	19:54	oUbK7Uqm8a8	Nikocado Avocado Es Un GENIO (bajó de peso)
353	11:02	svb5xeXDUGI	El Usuario Más TURBIO de ROBLOX
354	34:00	OzPV4lin1nQ	smartschoolboy9: El Misterio Más Perturbador De Internet
355	9:51	0ygQnUeB-4E	Videos Chistosos del 2010
356	27:03	TBBqp1Dws70	Muñecas POSEIDAS.
357	34:26	E23Pene1LPw	Probando Dulces GRINGOS
358	19:23	FCqADtZvDsA	5 Tiktokers Que Hicieron Lo PEOR
359	18:16	3DwZ3Wu-xII	¿QUÉ ES LO MÁS CRINGE QUE HAS HECHO?
360	16:04	Q-pwKNm9ky8	Los Obligaron a Vivir Como Ratas.
361	18:46	pBvy0Qv-X5g	El Iceberg de Sucesos Ocurridos en Stream
362	10:01	DOmO0Adqs2Q	Las Peticiones de Desban Más DEGENERADAS.
363	48:58	evzcDy81QKc	Se Casó Con Una MUÑECA.
364	12:53	KEKrejYD5DI	Yo de cabro chico / Yo de cabro grande
365	8:01	yag7F9V9qFM	Amor como dejistes 🥺
366	11:57	_wwC0gLOJo0	Cringe Gringo.
367	22:36	AXB7mv_qj5s	Nadie puede contra mi 💋💅 (Roblox Dress to Impress)
368	1:02:51	VAaryeVycNM	El iceberg de Los Simpsons
369	19:29	H8SfAoeyNYY	NO DEJES DE CLICKEAR...
370	11:11	cOyerv_jhng	ESE NO ES ANUEL JSJSJAJJSJSJKJ
371	26:36	1thGE_8nvq8	descubriendo el origen de imágenes aterradoras
372	8:03	W5ROK0c7aag	Reaccionando a Reels de Instagram
373	36:22	5hfM7GAoTWI	Metiendo gente inocente a la cárcel
374	10:55	43t3A-6foEU	EL ASESINO DEL BAÑO
375	10:28	eMtbrU7e5Rc	viendo los likes de mis viewers en tiktok
376	36:51	ZtFofbHTYGg	Nadie lo hace como yo 💋💅 (Roblox Dress to Impress)
377	15:47	J1HFAs23POY	2 JUEGOS DE TERROR
378	26:23	zwdaaecIV38	reaccionando a mis momentos con menos IQ
379	9:21	8nQNK8V2i50	el video más triste del mundo
380	18:39	5eV39srcev8	el geoguessr de GTA San Andreas me dejó mal...
381	18:25	35nzVt1ngWQ	hablando con IA porque no tengo amigos
382	9:07	v6ylB0z4HbU	reaccionando a memes porque no quiero tener un trabajo real
383	19:35	CjpAIZ9p8Ss	ME APLAUDIÓ LOS CACHETES
384	10:33	R0ORxQ35FGc	Los Reels de Instagram No Tienen Sentido...
385	1:13:30	vcrCwG0DMck	Este Juego es MUY Difícil
386	17:42	6NbzDLOY_4Q	Experto en Moda Juega Dress to Impress
387	14:12	ExrO3V_r-4I	LA VENGANZA DE POU
388	9:39	u2WpIdCkiIc	MI CHAT HIZO VIDEOS CHISTOSOS CON IA
389	13:02	vCrl64mmw9M	LOS PERROS DE MIS VIEWERS SON RARISIMOS
390	9:36	2H9a2klaofw	adulto de 25 años le grita a gente en roblox
391	1:25:36	xClmdau1xh8	LA TIERLIST DE MEMES DEFINITIVA
392	10:56	vBHVxgEiMVs	hola humanos 👽
393	36:57	XbB2IgJSAIY	LA EVOLUCIÓN DE LA MÚSICA
394	8:08	X7hPF9WIYBs	ANUNCIOS QUE HOY ESTARÍAN PROHIBIDOS
395	8:35	A9N9_mVjGSI	en este video no digo 1 sola palabra.
396	15:20	_iMm5KUxSDs	¿QUE ES LO MÁS TONTO QUE HAS HECHO?
397	12:24	NivrokSHrII	memes que me mandaron por discord
398	19:42	iXzUdQ7fCkA	viendo tiktoks hasta que me ria
399	27:25	Xeej-_D5g9c	EL ICEBERG DE LOS SUEÑOS
400	12:06	DWzNkfUwVEA	dando malos consejos amorosos
401	12:57	It6bsmaGebM	chat no tengo poto de teletubi
402	14:13	uSm9zRIZNhI	mi esposa me abandonó y tuve que cocinar yo
403	8:18	-RsP-0eslmI	🐒
404	9:55	SMJonO5zRWc	EL LADO OSCURO DE GERMAN...
405	22:07	jyCVkqzMrfE	CONFESIONES
406	21:31	wHlNCFryReQ	FOTOS GRACIOSAS TOMADAS POR MIS VIEWERS
407	14:23	6eAcU3TzVt0	MENSAJES ANÓNIMOS DE MI CHAT
408	15:01	vcBH2xv61zk	chat no me parezco
409	11:20	WSlpM67T26U	QUE HIZO EL RARO DE TU CLASE?
410	10:03	ffXiKWluXp8	CUMPEO
411	26:37	GBL1TAysPu4	HABLANDO Y RIENDONOS POR 26 MINUTOS
412	15:38	l0-MJo8VOqI	tengo el "para ti" más raro de tiktok
413	11:41	OfBah8deTC4	YIAAAAA
414	13:14	x3kHG-6p3aA	estos son los crush animados de las mujeres 💀
415	12:35	uMCu0zEu8lE	MIS VIEWERS IMITARON A LOS ANGRY BIRDS
416	9:19	Kzl5p_gXEIw	MI CHAT ME OBLIGÓ A SALTAR EN CÁMARA LENTA
417	20:10	abwbvOuP3g8	MIS VIEWERS ME MANDAN AUDIOS CHISTOSOS
418	18:49	n9DDKQFEpKc	OBLIGUÉ A MI ABUELO A HACER STREAM
419	8:03	LwERNlVBFHo	MI CHAT ME MOSTRÓ SUS REGALOS
420	8:21	7jHgFaUbC9Y	MI CHAT NO DEJA DE HACERME ESTO
421	8:29	ELlzGmto4w8	SALIÓ EL LIVE ACTION DE COMO TAN MUCHACHO
422	8:08	TOYW17hR3HQ	MI CHAT ME MANDÓ TIKTOKS CHISTOSOS
423	11:34	kc87zjx_vJ0	MI CHAT ME MANDÓ COSAS RARAS DE ALIEXPRESS
424	17:56	mhFFNI9FtJM	los fondos de pantalla de mis viewers son rarisimos...
425	27:27	uXWM5DocbGQ	MI CHAT DECIDE QUIEN ES EL MEJOR PELADO DEL MUNDO
426	9:23	H9BV6iT4rIA	Viendo los clips MÁS vistos de Twitch
427	31:56	EvVpGO4rRj0	1 Nerd VS 100 Supermodelos
428	8:09	LMgxR5bct_s	me doxearon la casa en roblox 🏠😨
429	9:27	eKiODTF5UK0	mis viewers me hicieron edits chistosos
430	21:12	To_nhNOveHc	Obligó a su novio a convertirse en Furro...
431	12:17	8LqxvMsvZOM	salí en el stream del rubius de la peor forma...
432	8:11	-1lIP50KRfk	REACCIONANDO A MEMES DE DISCORD
433	14:40	tzuAhqutPJY	Probando TODOS los chocolates y galletas de MrBeast
434	10:53	KIEkMaMhr_s	SMASH OR PASS DE FNAF
435	8:06	d74f1l4LlQo	mi chat me odia 😔
436	10:22	apVE5haiLVk	DESBANEANDO A LOS BANEADOS
437	10:22	rhx6VbdZ79A	se me subio un coco papito
438	20:37	4WpG9ew7i4Q	COSAS RARAS DE FACEBOOK MARKETPLACE
439	47:11	3zj37I5aZRA	CONFESIONES DEL CHAT
440	10:13	doFiCyyzffA	MEMES DE DISCORD
441	27:01	iN2VhxVT1Go	MI CHAT HIZO IMÁGENES CHISTOSAS CON IA
442	26:53	CD_hDE-QG-s	Todos los Países del Mundo Compiten por $250,000 | REACCIONANDO A MRBEAST
443	10:45	AukDPdQ536o	RUBEN TUESTA LE ESTÁ COPIANDO A TODOS
444	18:49	9snbu5C4pIQ	QUE PREFIERES?
445	30:38	EBFQn6tsAis	REACCIONANDO A UNA CRITICA A LAS REACCIONES
446	25:45	1Sb_DFTsXzw	STREAMER CON 263 DE IQ HACE UN TEST DE CULTURA GENERAL
447	18:21	IA0iTQ81wkE	EL ICEBERG DE LAS FOTOS PERTURBADORAS
448	12:23	yfaTnE58hQI	CRISTIANGHOST REACCIONA a Desmintiendo Videos POV: Sabes El Contexto 💀
449	35:09	D2PWfgx8tEs	CRISTIANGHOST REACCIONA a EL ICEBERG DE TOTTUS
450	16:38	uBukPcTDlFs	CRISTIANGHOST REACCIONA a TREN VS FOSA GIGANTE
451	17:05	sXuGAlBC228	CRISTIANGHOST REACCIONA a REESE EL PERSONAJE MAS MISERABLE DE MALCOLM
452	22:13	qrGIvX8kPJI	CRISTIANGHOST REACCIONA a SUS LIKES DE TIKTOK
453	44:43	40WKARcvrIE	CRISTIANGHOST REACCIONA a ICEBERG DE COMIDA CALLEJERA
454	13:54	LDuNrkGauf4	CRISTIANGHOST REACCIONA a TODOS SON ESPAÑOLES: ¿Qué Pasó con los Creadores Latinos?
455	24:37	vYcE3f62fds	el cristian revisa tinders de sus viewers
456	25:34	MFUxP2j1gHo	Iceberg de Animales con Superpoderes / Reaccion de CristianGhost
457	42:36	8imod_fkW4M	le hacen bullying con memes WUAJAJA / CristianGhost
458	2:56	NNv-d0NgH9g	cristianghost cantando con autotune en vivo
459	12:37	lgyFw0XIa24	CristianGhost muestra sus 200 de IQ - Test de cultura general
460	32:44	vsB1QNqZywk	Iceberg de Programas infantiles Tétricos / cristianghost reacciona
```

## Appendix B: Shorts Inventory

Format: `index duration video_id title`. Duration was unavailable in flat mode for these Shorts.

```text
1	NA	nKoSt4jGN9A	No se aguanten
2	NA	sVwS3FG_fCg	noo curly que le haces a fernan 😔
3	NA	MyNggfZiGHE	simplemente un genio
4	NA	aTC3wXWW3VY	mis viewers se ponen degenerados en discord 💀
5	NA	d4QgTV4afA0	no hay emojis de angry birds 🐷🏛  🐦🕊🏹
```
