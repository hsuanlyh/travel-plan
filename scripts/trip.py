#!/usr/bin/env python3
"""trip.py — staticrypt-compatible build / decrypt / deploy, no Node needed.

Each trip folder holds:
  <trip>/source.html   plaintext source (gitignored, keep local only)
  <trip>/index.html    staticrypt-encrypted page (committed, served by Pages)

用法:
  python3 scripts/trip.py decrypt 2026-kansai     # 還原 source.html（輸入密碼或分享連結的 #staticrypt_pwd= hash）
  python3 scripts/trip.py build   2026-hanoi      # source.html → 加密 index.html，並印出分享 hash
  python3 scripts/trip.py hash    2026-hanoi      # 只印出分享 hash
  python3 scripts/trip.py deploy  2026-hanoi      # build + git commit + push

密碼也可用環境變數 TRIP_PASSWORD 傳入（避免留在 shell history）。
Requires: python3, openssl (macOS 內建 LibreSSL 即可).
"""
import getpass
import hashlib
import hmac
import json
import os
import re
import secrets
import subprocess
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED = os.path.join(ROOT, "shared")
CSS_LINK = '<link rel="stylesheet" href="../shared/style.css">'
JS_TAG = '<script src="../shared/main.js"></script>'
CONFIG_RE = re.compile(r'staticryptConfig = (\{.*?\});')


# ---------- staticrypt v3 crypto ----------

def _pbkdf2(password, salt, iterations, algo):
    return hashlib.pbkdf2_hmac(algo, password.encode(), salt.encode(), iterations, 32).hex()


def hash_password(password, salt):
    # Same three rounds as staticrypt (1k SHA-1 → 14k SHA-256 → 585k SHA-256)
    h = _pbkdf2(password, salt, 1000, "sha1")
    h = _pbkdf2(h, salt, 14000, "sha256")
    return _pbkdf2(h, salt, 585000, "sha256")


def _openssl(mode, key_hex, iv_hex, data):
    args = ["openssl", "enc", "-aes-256-cbc", "-K", key_hex, "-iv", iv_hex]
    if mode == "d":
        args.append("-d")
    return subprocess.run(args, input=data, capture_output=True, check=True).stdout


def _sign(hashed, msg):
    return hmac.new(bytes.fromhex(hashed), msg.encode(), hashlib.sha256).hexdigest()


def encode(plaintext, hashed):
    iv = secrets.token_hex(16)
    encrypted = iv + _openssl("e", hashed, iv, plaintext.encode()).hex()
    return _sign(hashed, encrypted) + encrypted


def decode(signed, hashed):
    mac, encrypted = signed[:64], signed[64:]
    if not hmac.compare_digest(_sign(hashed, encrypted), mac):
        return None
    iv, body = encrypted[:32], encrypted[32:]
    return _openssl("d", hashed, iv, bytes.fromhex(body)).decode()


# ---------- helpers ----------

def trip_paths(trip):
    d = os.path.join(ROOT, trip)
    if not os.path.isdir(d):
        sys.exit(f"❌ 找不到資料夾 {trip}")
    return os.path.join(d, "source.html"), os.path.join(d, "index.html")


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def write(p, s):
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)


def load_config(page):
    m = CONFIG_RE.search(page)
    return json.loads(m.group(1)) if m else None


def ask_secret(prompt):
    return os.environ.get("TRIP_PASSWORD") or getpass.getpass(prompt)


def template_page():
    """Any existing encrypted page works as the staticrypt template."""
    for name in sorted(os.listdir(ROOT)):
        p = os.path.join(ROOT, name, "index.html")
        if os.path.isfile(p) and load_config(read(p)):
            return read(p)
    sys.exit("❌ 沒有可用的 staticrypt 範本頁")


def inline_shared(html):
    html = html.replace(CSS_LINK, f"<style>\n{read(os.path.join(SHARED, 'style.css'))}\n</style>")
    return html.replace(JS_TAG, f"<script>\n{read(os.path.join(SHARED, 'main.js'))}\n</script>")


def uninline_shared(html):
    html = html.replace(f"<style>\n{read(os.path.join(SHARED, 'style.css'))}\n</style>", CSS_LINK)
    return html.replace(f"<script>\n{read(os.path.join(SHARED, 'main.js'))}\n</script>", JS_TAG)


def salt_for(index_path):
    # Reuse the trip's existing salt so old share links keep working
    if os.path.isfile(index_path):
        cfg = load_config(read(index_path))
        if cfg:
            return cfg["staticryptSaltUniqueVariableName"]
    return secrets.token_hex(16)


# ---------- commands ----------

def cmd_decrypt(trip):
    src, idx = trip_paths(trip)
    cfg = load_config(read(idx))
    salt, msg = cfg["staticryptSaltUniqueVariableName"], cfg["staticryptEncryptedMsgUniqueVariableName"]
    secret = ask_secret("密碼或分享 hash（#staticrypt_pwd= 後面那串）: ").strip()
    secret = secret.split("staticrypt_pwd=")[-1].split("&")[0]
    candidates = []
    if re.fullmatch(r"[0-9a-f]{64}", secret):
        candidates.append(secret)  # already hashed (share link)
    print("🔑 計算 hash 中（約數秒）…")
    candidates.append(hash_password(secret, salt))
    for hashed in candidates:
        plain = decode(msg, hashed)
        if plain is not None:
            if os.path.exists(src):
                os.replace(src, src + ".bak")
                print(f"  （舊的 source.html 已備份為 source.html.bak）")
            write(src, uninline_shared(plain))
            print(f"✅ 已還原 → {os.path.relpath(src, ROOT)}")
            return
    sys.exit("❌ 密碼／hash 不正確")


def build(trip, password=None):
    src, idx = trip_paths(trip)
    if not os.path.isfile(src):
        sys.exit(f"❌ 找不到 {os.path.relpath(src, ROOT)}，先跑 decrypt 或建立 source")
    password = password or ask_secret("密碼: ")
    if not os.environ.get("TRIP_PASSWORD") and getpass.getpass("再輸入一次: ") != password:
        sys.exit("❌ 兩次密碼不一致")
    salt = salt_for(idx)
    print("🔑 計算 hash 中（約數秒）…")
    hashed = hash_password(password, salt)
    cfg = {
        "staticryptEncryptedMsgUniqueVariableName": encode(inline_shared(read(src)), hashed),
        "isRememberEnabled": False,
        "rememberDurationInDays": 0,
        "staticryptSaltUniqueVariableName": salt,
    }
    page = CONFIG_RE.sub(lambda _: f"staticryptConfig = {json.dumps(cfg, separators=(',', ':'))};", template_page())
    write(idx, page)
    print(f"✅ 已加密 → {os.path.relpath(idx, ROOT)}")
    print(f"🔗 分享 hash：#staticrypt_pwd={hashed}")
    return idx


def cmd_hash(trip):
    _, idx = trip_paths(trip)
    salt = salt_for(idx)
    print(f"#staticrypt_pwd={hash_password(ask_secret('密碼: '), salt)}")


def cmd_deploy(trip):
    idx = build(trip)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    subprocess.run(["git", "-C", ROOT, "add", "-f", idx], check=True)
    subprocess.run(["git", "-C", ROOT, "commit", "-m", f"deploy: {trip} @ {stamp}"], check=True)
    subprocess.run(["git", "-C", ROOT, "push"], check=True)


def main():
    cmds = {"decrypt": cmd_decrypt, "build": build, "hash": cmd_hash, "deploy": cmd_deploy}
    if len(sys.argv) != 3 or sys.argv[1] not in cmds:
        sys.exit(__doc__)
    cmds[sys.argv[1]](sys.argv[2].strip("/"))


if __name__ == "__main__":
    main()
