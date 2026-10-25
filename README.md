# YouTube Automation

Every 6 hours GitHub Actions runs `run.py`, which makes **at most one video per day** (India time):

1. **Topic** – Google Trends searches + trending YouTube videos (title, channel, tags,
   description) for India + US; positive topics only, India/US stories preferred
2. **Script** – news facts → original script (NVIDIA: Nemotron picks, Llama 3.3 70B writes) → fact-check
3. **Title & description** – SEO title, description, hashtags and tags from the trend research
4. **Video** – NotebookLM cinematic video (explainer as fallback) that opens with a clean
   title screen; 5-hour gap respected
5. **Edit** – watermark + ending removed with notebooklmremover.com (blur as fallback),
   audio normalised, optional music/outro. Thumbnail = the video's opening title screen
6. **Upload** – YouTube Data API (private by default)

If a run stops halfway (video still generating, upload error), the next run continues from there.

## GitHub secrets (Settings → Secrets and variables → Actions → Secrets)

| Secret | What |
|---|---|
| `NOTEBOOKLM_AUTH_JSON` | contents of `storage_state.json` after `notebooklm login` |
| `NVIDIA_API_KEY` | from build.nvidia.com |
| `YOUTUBE_API_KEY` | Google Cloud API key (reads trending videos) |
| `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` | from `tools/get_youtube_token.py` (below) |
| `NVIDIA_WRITER_MODEL` | optional, e.g. `qwen/qwen3-235b-a22b` |

## GitHub variables (same page → Variables tab)

| Variable | Default | What |
|---|---|---|
| `YT_PRIVACY` | `private` | `private`, `unlisted` or `public` |
| `WATERMARK_BOX` | `0.84,0.88,0.15,0.10` | blur fallback area as x,y,width,height fractions |
| `WATERMARK_SITE` | `on` | set to `off` to skip notebooklmremover.com and only blur |
| `THUMBNAIL_AT` | `1.5` | second of the video used as the thumbnail |

If the website step fails, the blur is used: check `watermark_check.jpg` in the run's artifacts.

## Optional files

- `assets/music.mp3` – quiet background music (use royalty-free music only)
- `assets/outro.mp4` – clip added at the end (e.g. "Subscribe")

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
- **Daily video** – the full pipeline (tick *force* to make another video today)
