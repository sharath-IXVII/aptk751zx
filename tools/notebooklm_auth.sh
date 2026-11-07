#!/usr/bin/env bash
# Restore the NotebookLM login on GitHub Actions from secrets.
#   NOTEBOOKLM_MASTER_TOKEN  contents of master_token.json  (long-lasting, preferred)
#   NOTEBOOKLM_AUTH_JSON     contents of storage_state.json (cookies, expire after a while)
# With a master token, fresh cookies are minted on every run, so the login doesn't expire.
set -euo pipefail

dir="$HOME/.notebooklm/profiles/default"
mkdir -p "$dir"
chmod 700 "$HOME/.notebooklm" "$dir"

if [ -n "${NOTEBOOKLM_AUTH_JSON:-}" ]; then
  printf '%s' "$NOTEBOOKLM_AUTH_JSON" > "$dir/storage_state.json"
  chmod 600 "$dir/storage_state.json"
fi

if [ -n "${NOTEBOOKLM_MASTER_TOKEN:-}" ]; then
  printf '%s' "$NOTEBOOKLM_MASTER_TOKEN" > "$dir/master_token.json"
  chmod 600 "$dir/master_token.json"
  echo "Minting fresh NotebookLM cookies from the master token..."
  unset NOTEBOOKLM_AUTH_JSON
  if ! notebooklm login --master-token-refresh; then
    # Google rejected the master token: carry on with the saved cookies if there are any,
    # so a run can still work until the master token is renewed.
    if [ -s "$dir/storage_state.json" ]; then
      echo "::warning::NotebookLM master token rejected - using the saved cookies. Renew NOTEBOOKLM_MASTER_TOKEN soon."
    else
      exit 1
    fi
  fi
else
  echo "No NOTEBOOKLM_MASTER_TOKEN secret - using saved cookies (these expire; see README)."
fi
