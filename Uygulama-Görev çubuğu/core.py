# -*- coding: utf-8 -*-
"""
core.py
Orijinal terminal betiğindeki (main.py) çekirdek mantık burada birebir korunuyor:
- Veri temizleme
- KNN ile en yakın şarkı bulma
- Spotify bağlantısı
- Şarkı arama
- Çalma listesi oluşturma

Tek fark: input()/print() yerine parametre ve log_callback kullanılıyor,
böylece bu fonksiyonlar hem terminalden hem de masaüstü arayüzünden
aynı şekilde çağrılabiliyor.
"""

import os
import random
import numpy as np
import pandas as pd
import spotipy
from spotipy.oauth2 import SpotifyOAuth

TARGET_ARTISTS = [
    "Ezhel", "Motive", "UZI", "maNga", "Duman", "mor ve ötesi",
    "Tarkan", "Sezen Aksu", "Mert Demir", "Melike Şahin", "Mabel Matiz",
    "Dolu Kadehi Ters Tut", "Adamlar", "Yüzyüzeyken Konuşuruz"
]


def _noop_log(msg):
    pass


# -------------------------------
# 1. VERİYİ YÜKLE VE TEMİZLE
# -------------------------------
def load_and_clean_data(file_path, log=_noop_log):
    df = pd.read_csv(file_path, decimal=',')
    df_clean = df.drop_duplicates(subset=['track_name', 'artists']).copy()
    df_clean['energy'] = pd.to_numeric(df_clean['energy'], errors='coerce')
    df_clean['valence'] = pd.to_numeric(df_clean['valence'], errors='coerce')
    df_clean = df_clean.dropna(subset=['energy', 'valence'])
    log(f"✅ Toplam benzersiz şarkı: {len(df_clean)}")
    features = df_clean[['energy', 'valence']].values.astype(float)
    return df_clean, features


# -------------------------------
# 2. KNN İLE EN YAKIN ŞARKILARI BUL
# -------------------------------
def find_closest_songs(df, features, target_energy, target_valence, weights, top_n=20):
    w_e, w_v = weights
    distances = []
    for idx, (energy, valence) in enumerate(features):
        dist = np.sqrt(w_e * (energy - target_energy) ** 2 + w_v * (valence - target_valence) ** 2)
        distances.append((idx, dist))

    distances.sort(key=lambda x: (x[1], random.random()))
    top_indices = [idx for idx, _ in distances[:top_n]]
    top_distances = [dist for _, dist in distances[:top_n]]

    result_df = df.iloc[top_indices].copy()
    result_df['distance'] = top_distances
    return result_df


# -------------------------------
# 3. SPOTIFY BAĞLANTISI
# -------------------------------
class SpotifyConnectionError(Exception):
    pass


def get_spotify_client(client_id, client_secret, redirect_uri, cache_path, log=_noop_log):
    if not client_id or not client_secret or not redirect_uri:
        raise SpotifyConnectionError("Eksik Spotify bilgileri! Lütfen Spotify Ayarları'nı kontrol edin.")

    try:
        auth_manager = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope="playlist-modify-public playlist-modify-private",
            cache_path=cache_path,
            open_browser=True,
            show_dialog=True
        )

        sp = spotipy.Spotify(auth_manager=auth_manager)

        user = sp.me()
        log(f"✅ Spotify'a başarıyla bağlanıldı! Kullanıcı: {user['display_name']} (ID: {user['id']})")
        return sp

    except spotipy.exceptions.SpotifyException as e:
        msg = f"Spotify bağlantı hatası (HTTP {e.http_status}): {e.msg}"
        if e.http_status == 403:
            msg += (
                "\n\n403 Forbidden hatası genellikle şu nedenlerle oluşur:\n"
                "1. Spotify Dashboard'da kullanıcınız 'User Management'a eklenmemiş.\n"
                "2. Uygulama Development modunda ve siz allowlist'te değilsiniz.\n"
                "3. Token'da 'playlist-modify-private' scope'u eksik.\n\n"
                "Çözüm: Dashboard > Settings > User Management > kullanıcı ID'nizi ekleyin, "
                "sonra Spotify Ayarları penceresinden 'Önbelleği Temizle' butonuna basıp tekrar deneyin."
            )
        raise SpotifyConnectionError(msg) from e
    except Exception as e:
        raise SpotifyConnectionError(f"Beklenmeyen hata: {e}") from e


# -------------------------------
# 4. ŞARKI ARAMA
# -------------------------------
def get_track_id(sp, track_name, artist_name):
    query = f"track:{track_name} artist:{artist_name}"
    results = sp.search(q=query, type="track", limit=1)
    tracks = results.get("tracks", {}).get("items", [])
    if tracks:
        return tracks[0]["id"]
    else:
        results = sp.search(q=track_name, type="track", limit=1)
        tracks = results.get("tracks", {}).get("items", [])
        if tracks:
            return tracks[0]["id"]
    return None


# -------------------------------
# 5. ÇALMA LİSTESİ OLUŞTUR
# -------------------------------
def create_playlist_and_add_tracks(sp, playlist_name, track_ids, description="", log=_noop_log):
    try:
        # NOT: Spotify, Şubat 2026 migration'ında POST /users/{user_id}/playlists
        # endpoint'ini tamamen kaldırdı (son geçiş tarihi 9 Mart 2026).
        # Bu yüzden yeni doğru endpoint olan POST /me/playlists kullanılıyor.
        payload = {
            "name": playlist_name,
            "public": False,
            "description": description
        }
        playlist = sp._post("me/playlists", payload=payload)
        playlist_id = playlist["id"]

        for i in range(0, len(track_ids), 100):
            sp.playlist_add_items(playlist_id, track_ids[i:i + 100])

        log("✅ Çalma listesi oluşturuldu!")
        log(f"🔗 Link: {playlist['external_urls']['spotify']}")
        return playlist_id, playlist['external_urls']['spotify']

    except spotipy.exceptions.SpotifyException as e:
        if e.http_status == 403:
            raise SpotifyConnectionError(
                "403 Forbidden: Playlist oluşturma yetkisi yok!\n"
                "Muhtemel nedenler:\n"
                "1. Kullanıcı ID'niz Dashboard'da allowlist'e eklenmemiş.\n"
                "2. Token'da 'playlist-modify-private' scope'u eksik.\n"
                "3. Spotify hesabınız Premium değil."
            ) from e
        raise SpotifyConnectionError(f"Spotify hatası (HTTP {e.http_status}): {e.msg}") from e


# -------------------------------
# 6. TÜM AKIŞI BİRLEŞTİREN YARDIMCI (GUI'nin çağırdığı fonksiyon)
# -------------------------------
def build_result_dataframe(df, features, mode, target_energy, target_valence, weights,
                            total_songs, log=_noop_log):
    """Orijinal main() içindeki KNN + hedef sanatçı bonus mantığının aynısı."""
    bonus_count = max(1, round(total_songs * 0.2))
    bonus_count = min(bonus_count, 10)
    knn_count = total_songs - bonus_count

    result = find_closest_songs(df, features, target_energy, target_valence, weights, top_n=knn_count)

    target_mask = df['artists'].isin(TARGET_ARTISTS)
    target_songs = df[target_mask].copy()

    if not target_songs.empty:
        target_features = target_songs[['energy', 'valence']].values.astype(float)
        w_e, w_v = weights
        distances = []
        for idx, (energy, valence) in enumerate(target_features):
            dist = np.sqrt(w_e * (energy - target_energy) ** 2 + w_v * (valence - target_valence) ** 2)
            original_idx = target_songs.index[idx]
            distances.append((original_idx, dist))

        distances.sort(key=lambda x: x[1])
        knn_keys = set(zip(result['track_name'], result['artists']))
        candidate_indices = []
        for idx, dist in distances:
            row = target_songs.loc[idx]
            if (row['track_name'], row['artists']) not in knn_keys:
                candidate_indices.append((idx, dist))

        if candidate_indices:
            pool_size = min(bonus_count * 2, len(candidate_indices))
            top_candidates = candidate_indices[:pool_size]
            num_to_add = min(bonus_count, len(top_candidates))
            if num_to_add > 0:
                selected = random.sample(top_candidates, num_to_add)
                added_songs = []
                for idx, dist in selected:
                    row = target_songs.loc[idx].copy()
                    row['distance'] = dist
                    added_songs.append(row)
                added_df = pd.DataFrame(added_songs)
                result = pd.concat([result, added_df], ignore_index=True)
                log(f"✨ Hedef sanatçılardan {num_to_add} şarkı eklendi.")

    return result
