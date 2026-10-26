# YouTube Automation

Every hour GitHub Actions runs `run.py`. A new video is made every 6 hours (4 a day) and
**scheduled** into the next free slot - 2 videos a day (12:00 + 18:00 India time), filled up to
7 days ahead - so the channel keeps posting even if runs fail:

1. **Episode** – the series "Arjun – Words That Shape You": one meaningful word per video
   (anger, discipline, trust...), never repeated (`pipeline/series.py`, `state/used_words.json`)
2. **Script** – a planned, editor-reviewed story about Arjun (stick-figure boy with an orange scarf)
   → the word's meaning → what it does to us → real-life moments → how to handle/build it
   (NVIDIA Nemotron, other models as fallback). `CONTENT_MODE=trending` switches back to trending topics
3. **Title & description** – SEO title, description, hashtags and tags from the trend research
4. **Video** – NotebookLM cinematic video (explainer as fallback) that opens with a clean
   title screen and the series' stickman animation style (explainer + custom style as fallback);
   6-hour gap respected
5. **Edit** – watermark + ending removed with notebooklmremover.com (blur as fallback),
   GetYr_ENT text in the corner, audio normalised, intro + ending clips (assets/), optional music.
   Thumbnail = sharpest frame of the opening title screen
6. **Upload** – YouTube Data API, scheduled to go public at its slot
7. **Clean up** – the NotebookLM notebooks the pipeline made are deleted after the upload, and
   the run files (videos in the Actions artifacts) are deleted automatically after 3 days.
   Videos on your YouTube channel are never deleted.

If a run stops halfway (video still generating, upload error), the next run continues from there.
A video that fails 3 more times is dropped and a new one is made; a video is never uploaded twice.

## GitHub secrets (Settings → Secrets and variables → Actions → Secrets)

| Secret | What |
|---|---|
| `NOTEBOOKLM_MASTER_TOKEN` | contents of `master_token.json` (long-lasting login, see below) |
| `NOTEBOOKLM_AUTH_JSON` | contents of `storage_state.json` (cookies) |
| `NVIDIA_API_KEY` | from build.nvidia.com |
| `YOUTUBE_API_KEY` | Google Cloud API key (reads trending videos) |
| `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` | from `tools/get_youtube_token.py` (below) |
| `NVIDIA_WRITER_MODEL` | optional, e.g. `qwen/qwen3-235b-a22b` |

## GitHub variables (same page → Variables tab)

| Variable | Default | What |
|---|---|---|
| `YT_PRIVACY` | `public` | `private`, `unlisted` or `public` |
| `YT_PUBLISH_TIMES` | `12:00,18:00` | slot times (India); 1-video days use the last one |
| `BUFFER_DAYS` | `7` | how many days ahead to fill with scheduled videos |
| `VIDEOS_PER_DAY` | `2` | videos published per day (or a repeating pattern like `1,2`; `0` = no limit) |
| `WATERMARK_BOX` | `0.84,0.88,0.15,0.10` | blur fallback area as x,y,width,height fractions |
| `WATERMARK_SITE` | `on` | set to `off` to skip notebooklmremover.com and only blur |
| `YT_CATEGORY` | `27` | YouTube category id (27 Education, 24 Entertainment, 22 People & Blogs) |
| `SERIES_CHARACTER` | `Arjun` | name of the series' character |
| `CONTENT_MODE` | `series` | `series` or `trending` |
| `CHANNEL_NAME` | `GetYr_ENT` | text watermark in the bottom-right corner (or add `assets/logo.png`) |
| `THUMBNAIL_AT` | auto | force a second of the video for the thumbnail (default: best frame of the first 5 s) |

If the website step fails, the blur is used: check `watermark_check.jpg` in the run's artifacts.

## Optional files

- `assets/logo.png` – your channel logo, shown in the bottom-right corner of every video
  (transparent PNG works best; used instead of `CHANNEL_NAME`)
- `assets/music.mp3` – quiet background music (use royalty-free music only)
- `assets/intro.mp4` – branding intro added at the start
- `assets/outro.mp4` – ending added at the end ("Thank you for watching" / Subscribe)

## NotebookLM login (one time, on your PC)

```
pip install "notebooklm-py[browser,headless]==0.8.5"
playwright install chromium
notebooklm login --master-token --account YOUR_EMAIL@gmail.com
```
Then copy these two files from `%USERPROFILE%\.notebooklm\profiles\default\` (Windows) or
`~/.notebooklm/profiles/default/` into GitHub secrets:
- `master_token.json` → `NOTEBOOKLM_MASTER_TOKEN`
- `storage_state.json` → `NOTEBOOKLM_AUTH_JSON`

The master token is a long-lasting key to that Google account - use a separate account
for this channel, and never share the file.

## YouTube upload setup (one time, on your PC)

1. https://console.cloud.google.com → project **yt-automation**
2. **APIs & Services → OAuth consent screen**: External, fill app name + your email,
   add your Gmail as a test user, then click **Publish app** (otherwise login expires every 7 days).
3. **Credentials → Create credentials → OAuth client ID → Desktop app** → download the JSON.
4. On your PC:
   ```
   pip install google-auth-oauthlib
   python tools/get_youtube_token.py client_secret.json
   ```
   Sign in with the account that owns the channel → Allow → copy the 3 printed values into secrets.

Note: Google keeps API uploads **private** until the project passes a YouTube API audit
(https://support.google.com/youtube/contact/yt_api_form). Until then, publish videos from YouTube Studio.
Custom thumbnails need a phone-verified channel (youtube.com/verify).

## Test workflows (Actions tab → Run workflow)

- **Part 1 - NotebookLM test** – makes a test video
- **Part 2 - Trending topic + script test** – writes a script (tick the box to also make the video)
- **Part 4 - YouTube upload test** – checks the YouTube login and uploads one PRIVATE test video
- **Daily video** – the full pipeline (tick *force* to make another video today)
