"""Run this ONCE on your own PC to allow uploads to your YouTube channel.

    pip install google-auth-oauthlib
    python tools/get_youtube_token.py path/to/client_secret.json

A browser opens - sign in with the account that owns the YouTube channel and click Allow.
It prints three values. Save each as a GitHub secret:
    YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
"""

import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube"]


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Usage: python tools/get_youtube_token.py client_secret.json")
    client = json.load(open(sys.argv[1]))
    client = client.get("installed") or client.get("web")
    flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    print("\nSave these as GitHub secrets:\n")
    print("YT_CLIENT_ID     =", client["client_id"])
    print("YT_CLIENT_SECRET =", client["client_secret"])
    print("YT_REFRESH_TOKEN =", creds.refresh_token)


if __name__ == "__main__":
    main()
