# -*- coding: utf-8 -*-
"""
config.py
Uygulama ayarlarını (CSV dosya yolu, Spotify API bilgileri) kullanıcının
home dizininde saklar, böylece her açılışta yeniden girilmesi gerekmez.
"""

import json
from pathlib import Path

APP_DIR = Path.home() / ".knn_playlist_app"
CONFIG_PATH = APP_DIR / "config.json"
SPOTIFY_CACHE_PATH = APP_DIR / ".spotify_cache"

DEFAULT_CONFIG = {
    "csv_path": "",
    "spotify_client_id": "",
    "spotify_client_secret": "",
    "spotify_redirect_uri": "http://127.0.0.1:8888/callback",
}


def ensure_app_dir():
    APP_DIR.mkdir(parents=True, exist_ok=True)


def load_config():
    ensure_app_dir()
    if not CONFIG_PATH.exists():
        return dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(DEFAULT_CONFIG)
        merged.update(data)
        return merged
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_CONFIG)


def save_config(config):
    ensure_app_dir()
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def clear_spotify_cache():
    ensure_app_dir()
    if SPOTIFY_CACHE_PATH.exists():
        SPOTIFY_CACHE_PATH.unlink()
