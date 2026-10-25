# YouTube Automation

Trending topic → NVIDIA script → NotebookLM cinematic video → edit → thumbnail/title → YouTube.
Built in parts. **Current: Part 1 (NotebookLM test).**

## Part 1 - test on your PC

Needs Python 3.10+ and ffmpeg installed.

```bash
pip install -r requirements.txt
pip install "notebooklm-py[browser]==0.8.5"
playwright install chromium

notebooklm login          # browser opens - sign in with your Google account yourself
python part1_test.py      # wait 20-40 min
```

Success = `output/part1_test.mp4` plays.

## Part 1 - test on GitHub Actions

1. After `notebooklm login`, find the saved login file:
   - Windows: `C:\Users\<you>\.notebooklm\profiles\default\storage_state.json`
   - Mac/Linux: `~/.notebooklm/profiles/default/storage_state.json`
2. GitHub repo → Settings → Secrets and variables → Actions → New secret
   - Name: `NOTEBOOKLM_AUTH_JSON`
   - Value: the full contents of `storage_state.json`
3. Actions tab → "Part 1 - NotebookLM test" → Run workflow.
4. When done, download the video from the run's **Artifacts** section.

If it fails with a login error: run `notebooklm login` again on your PC and update the secret.

**Never commit `storage_state.json` or `.env`** - they are your login and keys.
