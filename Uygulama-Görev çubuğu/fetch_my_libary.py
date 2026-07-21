# -*- coding: utf-8 -*-
"""
fetch_my_library.py

Amaç: CSV veri setini senin gerçek Spotify verinle değiştirmek.

Adım 1: Beğenilen şarkılar + kendi playlist'lerin + top tracks + son dinlenenleri
        çekip tekilleştiriyor (Spotify Web API — hâlâ tamamen çalışıyor).
Adım 2: Her track için ReccoBeats API'den energy/valence çekiyor
        (Spotify'ın audio-features endpoint'i Kasım 2024'ten beri yeni
        uygulamalar için kapalı, bu yüzden onun yerine ReccoBeats kullanıyoruz).
Adım 3: core.py'deki load_and_clean_data() ile birebir uyumlu bir CSV
        (track_name, artists, energy, valence) üretiyor.

Kullanım:
    python fetch_my_library.py

config.py'deki mevcut spotify_client_id / secret / redirect_uri bilgilerini
kullanır. Eksikse önce app.py üzerinden "Spotify Ayarları" ile gireceksin.
"""

import time
import requests
import pandas as pd
import spotipy
from spotipy.oauth2 import SpotifyOAuth

import config

# Bu script sadece OKUMA yapıyor, playlist oluşturmuyor -> read-only scope yeterli
SCOPES = "user-library-read playlist-read-private user-read-recently-played user-top-read"

RECCOBEATS_BASE = "https://api.reccobeats.com/v1"
CHUNK_SIZE = 40  # ReccoBeats toplu isteklerde makul bir grup boyutu


def log(msg):
    print(msg)


def get_spotify_client():
    cfg = config.load_config()
    if not cfg.get("spotify_client_id") or not cfg.get("spotify_client_secret"):
        raise SystemExit("❌ Önce Spotify Ayarları'ndan client_id/secret gir (app.py üzerinden).")

    auth_manager = SpotifyOAuth(
        client_id=cfg["spotify_client_id"],
        client_secret=cfg["spotify_client_secret"],
        redirect_uri=cfg["spotify_redirect_uri"],
        scope=SCOPES,
        cache_path=str(config.SPOTIFY_CACHE_PATH),
        open_browser=True,
    )
    return spotipy.Spotify(auth_manager=auth_manager)


def get_liked_tracks(sp):
    tracks = []
    results = sp.current_user_saved_tracks(limit=50)
    while results:
        tracks.extend(
            item["track"] for item in results["items"]
            if item.get("track") and item["track"].get("type", "track") == "track"
        )
        results = sp.next(results) if results.get("next") else None
    log(f"✅ Beğenilen şarkılar: {len(tracks)}")
    return tracks


def get_playlist_tracks(sp):
    """Sadece SENİN oluşturduğun playlist'lerdeki ŞARKILARI çeker.

    Şubat 2026 Spotify API değişikliğinden sonra /playlists/{id}/items
    endpoint'i artık yalnızca sahibi/collaborator'ı olduğun playlist'lerde
    çalışıyor (başkasının oluşturup senin takip ettiğin playlist'ler için
    403 dönüyor). Ayrıca podcast bölümlerini (episode) atlayıp sadece
    şarkıları alıyoruz.
    """
    me = sp.me()["id"]
    log(f"   ℹ️ Spotify kullanıcı ID'n: {me}")

    tracks = []
    playlists = sp.current_user_playlists(limit=50)["items"]

    for pl in playlists:
        owner_id = pl.get("owner", {}).get("id")
        is_own = owner_id == me
        tag = "SAHİP" if is_own else "takip edilen"
        log(f"   • '{pl.get('name')}' -> owner_id={owner_id} ({tag})")

        if not is_own:
            continue

        try:
            results = sp.playlist_items(pl["id"], additional_types=("track",))
            while results:
                for item in results["items"]:
                    track = item.get("track")
                    if track and track.get("id") and track.get("type", "track") == "track":
                        tracks.append(track)
                results = sp.next(results) if results.get("next") else None
        except spotipy.exceptions.SpotifyException as e:
            log(f"     ⚠️ 403/hata detayı: status={e.http_status}, msg={e.msg}, headers={getattr(e, 'headers', None)}")
            continue

    log(f"✅ Playlist şarkıları (sadece kendi playlist'lerin, sadece şarkılar): {len(tracks)}")
    return tracks


def get_top_tracks(sp):
    tracks = []
    for time_range in ("short_term", "medium_term", "long_term"):
        tracks.extend(sp.current_user_top_tracks(limit=50, time_range=time_range)["items"])
    log(f"✅ Top tracks (3 dönem toplam): {len(tracks)}")
    return tracks


def get_recently_played(sp):
    items = sp.current_user_recently_played(limit=50)["items"]
    tracks = [item["track"] for item in items]
    log(f"✅ Son dinlenenler: {len(tracks)}")
    return tracks


def _safe(fn, sp, label):
    try:
        return fn(sp)
    except spotipy.exceptions.SpotifyException as e:
        log(f"   ⚠️ {label} çekilemedi (atlandı: {e.http_status}).")
        return []


def collect_all_tracks(sp):
    all_tracks = (
        _safe(get_liked_tracks, sp, "Beğenilen şarkılar")
        + _safe(get_playlist_tracks, sp, "Playlist şarkıları")
        + _safe(get_top_tracks, sp, "Top tracks")
        + _safe(get_recently_played, sp, "Son dinlenenler")
    )
    unique = {}
    for t in all_tracks:
        if t and t.get("id"):
            unique[t["id"]] = t
    log(f"✅ Tekilleştirme sonrası toplam benzersiz şarkı: {len(unique)}")
    return list(unique.values())


def resolve_reccobeats_ids(spotify_ids):
    """Spotify track ID -> ReccoBeats UUID eşlemesini toplu (batch) olarak alır.

    ReccoBeats'in audio-features endpoint'i sadece kendi UUID'sini kabul ediyor,
    Spotify ID doğrudan çalışmıyor. Bu yüzden önce /v1/track?ids=... ile
    Spotify ID'leri ReccoBeats UUID'lerine çeviriyoruz.
    """
    mapping = {}
    total = len(spotify_ids)
    for i in range(0, total, CHUNK_SIZE):
        chunk = spotify_ids[i:i + CHUNK_SIZE]
        try:
            r = requests.get(
                f"{RECCOBEATS_BASE}/track",
                params={"ids": ",".join(chunk)},
                timeout=15,
            )
            if r.status_code == 200:
                for item in r.json().get("content", []):
                    href = item.get("href", "")
                    spotify_id = href.rstrip("/").split("/")[-1] if href else None
                    if spotify_id and item.get("id"):
                        mapping[spotify_id] = item["id"]
            else:
                log(f"   ⚠️ Track eşleme isteği {r.status_code} döndü, bu grup atlandı.")
        except requests.RequestException as e:
            log(f"   ⚠️ Track eşleme isteğinde ağ hatası: {e}")
        log(f"   ↳ eşleme: {min(i + CHUNK_SIZE, total)}/{total} şarkı işlendi ({len(mapping)} bulundu)")
        time.sleep(0.3)
    return mapping


def resolve_audio_features(reccobeats_ids):
    """ReccoBeats UUID -> {energy, valence, ...} eşlemesini toplu olarak alır."""
    features = {}
    ids_list = list(reccobeats_ids)
    total = len(ids_list)
    for i in range(0, total, CHUNK_SIZE):
        chunk = ids_list[i:i + CHUNK_SIZE]
        try:
            r = requests.get(
                f"{RECCOBEATS_BASE}/audio-features",
                params={"ids": ",".join(chunk)},
                timeout=15,
            )
            if r.status_code == 200:
                for item in r.json().get("content", []):
                    if item.get("id"):
                        features[item["id"]] = item
            else:
                log(f"   ⚠️ Audio-features isteği {r.status_code} döndü, bu grup atlandı.")
        except requests.RequestException as e:
            log(f"   ⚠️ Audio-features isteğinde ağ hatası: {e}")
        log(f"   ↳ audio-features: {min(i + CHUNK_SIZE, total)}/{total} şarkı işlendi ({len(features)} bulundu)")
        time.sleep(0.3)
    return features


def build_dataset(tracks):
    spotify_ids = [t["id"] for t in tracks]

    log("🔎 Spotify ID -> ReccoBeats ID eşleştirmesi yapılıyor...")
    id_map = resolve_reccobeats_ids(spotify_ids)
    log(f"✅ {len(id_map)}/{len(spotify_ids)} şarkı ReccoBeats veri tabanında bulundu.")

    if not id_map:
        return pd.DataFrame()

    log("🎧 Audio-features (energy/valence) çekiliyor...")
    feats_map = resolve_audio_features(set(id_map.values()))

    rows = []
    for t in tracks:
        recco_id = id_map.get(t["id"])
        feats = feats_map.get(recco_id) if recco_id else None
        if not feats or feats.get("energy") is None or feats.get("valence") is None:
            continue
        rows.append({
            "track_name": t["name"],
            "artists": ", ".join(a["name"] for a in t["artists"]),
            "energy": feats["energy"],
            "valence": feats["valence"],
        })
    return pd.DataFrame(rows)


def main():
    sp = get_spotify_client()
    tracks = collect_all_tracks(sp)
    if not tracks:
        raise SystemExit("❌ Hiç şarkı bulunamadı. Spotify hesabında beğenilen/playlist/geçmiş yok mu?")

    df = build_dataset(tracks)

    if df.empty:
        raise SystemExit("❌ Hiçbir şarkı için audio-features alınamadı.")

    out_path = "my_spotify_library.csv"
    df.to_csv(out_path, index=False, encoding="utf-8")
    log(f"🎉 Bitti! {len(df)} şarkı '{out_path}' dosyasına kaydedildi.")
    log("   Bu dosyayı app.py üzerinden 'Veri Dosyası Seç…' ile csv_path olarak ayarlayabilirsin.")


if __name__ == "__main__":
    main()