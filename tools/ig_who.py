"""Which Instagram accounts can this repo's token reach? (read-only)"""
import os, httpx
t, u = os.environ["IG_ACCESS_TOKEN"].strip(), os.environ["IG_USER_ID"].strip()
G = "https://graph.facebook.com/v21.0"
print("secrets used: IG_ACCESS_TOKEN (starts", t[:4], ") - META_* secrets are not read when this exists")
print("token login:", httpx.get(f"{G}/me", params={"fields": "id,name", "access_token": t}).text[:120])
for known, name in (("17841445173070131", "getyr_ece"), ("17841426541767285", "getyr_ent"),
                    ("17841465549628730", "getyr_cse"), ("17841464952286078", "getyr_cybersec")):
    r = httpx.get(f"{G}/{known}", params={"fields": "username", "access_token": t})
    print(f"  can reach {name:15}:", "YES" if r.status_code == 200 else "no", "<- this repo's IG_USER_ID" if known == u else "")
print("IG_USER_ID is one of the 4 accounts:", u in ("17841445173070131", "17841426541767285", "17841465549628730", "17841464952286078"))
