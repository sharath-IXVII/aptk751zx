# Maintenance guide (no Claude needed)

The robot runs on its own: cron-job.org starts **Actions → Daily video** every hour. A new episode
is made about every 6 hours (4 a day), and 2 are published a day at 12:00 and 18:00 India time.

## Is it working?
1. **GitHub → Actions → Daily video:** green ✓ means OK. Most hourly runs finish in seconds,
   which is normal: they had nothing to do.
2. **YouTube Studio → Content:** new videos should appear as **Scheduled**.
3. **Details of the last real run:** open the **run-logs** branch → `run.log`. Search it for
   `WARNING` or `ERROR`.

## Common problems and fixes
| What you see in the log or on GitHub | Fix |
|---|---|
| No new runs in Actions for hours | Open cron-job.org and check the job is enabled. Press **Test run**: `204` means OK, `401` means the GitHub key expired, so make a new fine-grained token (Actions: read and write, only this repo) and paste it after `Bearer ` in the Authorization header. |
| `NotebookLM` / `auth` / `login` / `401` error | On your PC run `py -m notebooklm login --master-token --account <the NotebookLM gmail>`, then copy the new `master_token.json` contents into the GitHub secret **NOTEBOOKLM_MASTER_TOKEN** (and `storage_state.json` into **NOTEBOOKLM_AUTH_JSON**). |
| `rate limit` / `quota exceeded` from NotebookLM | Nothing to do. It retries every hour by itself. |
| `invalid_grant` or YouTube upload `401` | Run the token command again (README → "YouTube upload setup") and update the secret **YT_REFRESH_TOKEN**. |
| `All NVIDIA models failed` | Make a new key at build.nvidia.com and update the secret **NVIDIA_API_KEY**. |
| `Watermark website failed` | Not urgent: the robot removes the logo itself (delogo) instead. If it happens on every run, the website changed; set the variable `WATERMARK_SITE` = `off` to skip it. |
| A Python error after the NotebookLM website changes | In `requirements.txt`, change `notebooklm-py[headless]==0.8.5` to the newest version from pypi.org/project/notebooklm-py and commit. |

## Change things without code
Go to **Settings → Secrets and variables → Actions → Variables**:

| Variable | Example | What it changes |
|---|---|---|
| `VIDEOS_PER_DAY` | `2` | Videos published per day |
| `YT_PUBLISH_TIMES` | `12:00,18:00` | Publish times (India time) |
| `CHANNEL_NAME` | `GetYr_ENT` | Corner text on the video |
| `SERIES_CHARACTER` | `Arjun` | One fixed hero in every episode (empty = new cast each time) |
| `YT_PRIVACY` | `public` / `private` | Visibility |

## Add more words
Edit `pipeline/series.py` → the `WORDS` lists → add words in quotes, separated by commas → **Commit**.
When every word has been used, the robot starts the list again with new stories.

## Stop or pause
- **Pause:** in cron-job.org, switch the job off. Also, in `.github/workflows/daily.yml`, put `#` in
  front of the two `schedule:` lines.
- **Run once now:** **Actions → Daily video → Run workflow**.
