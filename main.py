import os
import random
import time
import json
import pandas as pd
import numpy as np
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

load_dotenv()


# -------------------------------
# 1. VERİYİ YÜKLE VE TEMİZLE
# -------------------------------
def load_and_clean_data(file_path):
    df = pd.read_csv(file_path, decimal=',')
    df_clean = df.drop_duplicates(subset=['track_name', 'artists']).copy()
    df_clean['energy'] = pd.to_numeric(df_clean['energy'], errors='coerce')
    df_clean['valence'] = pd.to_numeric(df_clean['valence'], errors='coerce')
    df_clean = df_clean.dropna(subset=['energy', 'valence'])
    print(f"✅ Toplam benzersiz şarkı: {len(df_clean)}")
    features = df_clean[['energy', 'valence']].values.astype(float)
    return df_clean, features


# -------------------------------
# 2. KNN İLE EN YAKIN ŞARKILARI BUL
# -------------------------------
def find_closest_songs(df, features, target_energy, target_valence, weights, top_n=20):
    w_e, w_v = weights
    distances = []
    for idx, (energy, valence) in enumerate(features):
        dist = np.sqrt(w_e * (energy - target_energy)**2 + w_v * (valence - target_valence)**2)
        distances.append((idx, dist))

    distances.sort(key=lambda x: (x[1], random.random()))
    top_indices = [idx for idx, _ in distances[:top_n]]
    top_distances = [dist for _, dist in distances[:top_n]]

    result_df = df.iloc[top_indices].copy()
    result_df['distance'] = top_distances
    return result_df


# -------------------------------
# 3. SPOTIFY BAĞLANTISI (GÜNCELLENDİ - DOĞRU SCOPE)
# -------------------------------
def get_spotify_client():
    client_id = os.getenv("SPOTIPY_CLIENT_ID")
    client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
    redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI")

    if not client_id or not client_secret or not redirect_uri:
        raise ValueError("Eksik çevresel değişkenler! Lütfen .env dosyasını kontrol edin.")

    try:
        auth_manager = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope="playlist-modify-public playlist-modify-private",  # DOĞRU SCOPE
            cache_path=".spotify_cache",
            open_browser=True,
            show_dialog=True
        )

        sp = spotipy.Spotify(auth_manager=auth_manager)

        # Token'ı test et
        user = sp.me()
        print(f"\n✅ Spotify'a başarıyla bağlanıldı! Kullanıcı: {user['display_name']} (ID: {user['id']})")
        return sp

    except spotipy.exceptions.SpotifyException as e:
        print("\n❌ Spotify bağlantı hatası:")
        print(f"   Hata kodu: {e.http_status}")
        print(f"   Mesaj: {e.msg}")
        if e.http_status == 403:
            print("\n🔑 403 Forbidden hatası!")
            print("   Bu hata genellikle şu nedenlerle oluşur:")
            print("   1. Spotify Dashboard'da kullanıcınız (ID: 31nv2nkr3nyey353s7fmrlospapa) 'User Management'a eklenmemiş.")
            print("   2. Uygulama Development modunda ve siz allowlist'te değilsiniz.")
            print("   3. Token'da 'playlist-modify-private' scope'u eksik.")
            print("\n   Çözüm:")
            print("   - Dashboard > Settings > User Management > Add user")
            print("   - Kullanıcı ID'sini (31nv2nkr3nyey353s7fmrlospapa) ekleyin.")
            print("   - .spotify_cache dosyasını silip yeniden deneyin.")
        return None
    except Exception as e:
        print(f"\n❌ Beklenmeyen hata: {e}")
        return None


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
# 5. ÇALMA LİSTESİ OLUŞTUR (SPOTIPY NATIVE)
# -------------------------------
def create_playlist_and_add_tracks(sp, playlist_name, track_ids, description=""):
    try:
        user_id = sp.me()["id"]
        playlist = sp.user_playlist_create(
            user=user_id,
            name=playlist_name,
            public=False,
            description=description
        )
        playlist_id = playlist["id"]

        for i in range(0, len(track_ids), 100):
            sp.playlist_add_items(playlist_id, track_ids[i:i+100])

        print(f"\n✅ Çalma listesi oluşturuldu!")
        print(f"🔗 Link: {playlist['external_urls']['spotify']}")
        return playlist_id

    except spotipy.exceptions.SpotifyException as e:
        if e.http_status == 403:
            print("\n❌ 403 Forbidden: Playlist oluşturma yetkisi yok!")
            print("   Muhtemel nedenler:")
            print("   1. Kullanıcı ID'niz Dashboard'da allowlist'e eklenmemiş.")
            print("   2. Token'da 'playlist-modify-private' scope'u eksik.")
            print("   3. Spotify hesabınız Premium değil (Development modunda Premium gerekli).")
        else:
            print(f"\n❌ Spotify hatası (HTTP {e.http_status}): {e.msg}")
        raise


# -------------------------------
# 6. ANA PROGRAM
# -------------------------------
def main():
    print("="*60)
    print("🎵  KNN Playlist Önerici (Spotify Entegrasyonlu)  🎵")
    print("="*60)

    # Veriyi yükle
    df, features = load_and_clean_data('datasets/envanter_özel.csv')

    # Mod seçimi
    print("\nLütfen bir mod seçin:")
    print("1 - Sadece Ruh Hali (valans)")
    print("2 - Sadece Aktivite (enerji)")
    print("3 - Hem Ruh Hali hem Aktivite")

    while True:
        try:
            mode = int(input("Seçiminiz (1/2/3): "))
            if mode in [1, 2, 3]:
                break
            print("Lütfen 1, 2 veya 3 girin.")
        except ValueError:
            print("Geçersiz giriş, lütfen bir sayı girin.")

    target_energy = 0.5
    target_valence = 0.5
    weights = (0, 0)

    def get_scaled_input(prompt, min_val=1, max_val=10):
        while True:
            try:
                val = int(input(prompt))
                if min_val <= val <= max_val:
                    return val / 10.0
                print(f"Lütfen {min_val} ile {max_val} arasında bir tam sayı girin.")
            except ValueError:
                print("Geçersiz giriş, lütfen bir tam sayı girin.")

    if mode == 1:
        print("\nRuh hali seviyesi (1: üzgün, 10: mutlu):")
        target_valence = get_scaled_input("Değer (1-10): ")
        weights = (0.001, 1.0)

    elif mode == 2:
        print("\nAktivite seviyesi (1: sakin, 10: enerjik):")
        target_energy = get_scaled_input("Değer (1-10): ")
        weights = (1.0, 0.001)

    else:
        print("\nHem ruh hali hem aktivite:")
        target_valence = get_scaled_input("Ruh hali (1: üzgün, 10: mutlu): ")
        target_energy = get_scaled_input("Aktivite (1: sakin, 10: enerjik): ")
        weights = (1.0, 1.0)

    # KNN ile 20 şarkı bul
    result = find_closest_songs(df, features, target_energy, target_valence, weights, top_n=20)

    # Hedef sanatçılardan 5 şarkı ekle
    target_artists = [
        "Ezhel", "Motive", "UZI", "maNga", "Duman", "mor ve ötesi",
        "Tarkan", "Sezen Aksu", "Mert Demir", "Melike Şahin", "Mabel Matiz",
        "Dolu Kadehi Ters Tut", "Adamlar", "Yüzyüzeyken Konuşuruz"
    ]

    target_mask = df['artists'].isin(target_artists)
    target_songs = df[target_mask].copy()

    if not target_songs.empty:
        target_features = target_songs[['energy', 'valence']].values.astype(float)
        w_e, w_v = weights
        distances = []
        for idx, (energy, valence) in enumerate(target_features):
            dist = np.sqrt(w_e * (energy - target_energy)**2 + w_v * (valence - target_valence)**2)
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
            top_candidates = candidate_indices[:min(10, len(candidate_indices))]
            num_to_add = min(5, len(top_candidates))
            if num_to_add > 0:
                selected = random.sample(top_candidates, num_to_add)
                added_songs = []
                for idx, dist in selected:
                    row = target_songs.loc[idx].copy()
                    row['distance'] = dist
                    added_songs.append(row)
                added_df = pd.DataFrame(added_songs)
                result = pd.concat([result, added_df], ignore_index=True)
                print(f"\n✨ Hedef sanatçılardan {num_to_add} şarkı eklendi.")

    # Sonuçları göster
    print("\n" + "="*60)
    print(f"🎧  Öneri Listesi (mod: {mode})")
    print("="*60)

    for i, (idx, row) in enumerate(result.iterrows(), start=1):
        dist_str = f"{row['distance']:.6f}" if pd.notna(row['distance']) else "🎲 Rastgele"
        print(f"{i:2d}. {row['track_name']} - {row['artists']}  (distance: {dist_str})")

    # Spotify'a bağlan
    print("\n" + "="*60)
    print("🎵  Spotify'a Bağlanılıyor...")
    print("="*60)

    sp = get_spotify_client()
    if sp is None:
        print("❌ Spotify bağlantısı başarısız, program sonlandırılıyor.")
        return

    # Şarkı ID'lerini al
    print("\n🔍 Şarkılar Spotify'da aranıyor...")
    track_ids = []
    not_found = []
    
    for i, (idx, row) in enumerate(result.iterrows(), start=1):
        print(f"   {i}/{len(result)}: {row['track_name']} - {row['artists']}")
        track_id = get_track_id(sp, row['track_name'], row['artists'])
        if track_id:
            track_ids.append(track_id)
            print(f"      ✅ Bulundu!")
        else:
            not_found.append(f"{row['track_name']} - {row['artists']}")
            print(f"      ❌ Bulunamadı!")

    if not track_ids:
        print("\n❌ Hiçbir şarkı Spotify'da bulunamadı!")
        return

    # Çalma listesi oluştur
    playlist_name = f"KNN Öneri Listesi (mod {mode})"
    description = f"KNN ile oluşturuldu. Enerji: {target_energy:.2f}, Valans: {target_valence:.2f}"

    print("\n📁 Çalma listesi oluşturuluyor...")
    create_playlist_and_add_tracks(sp, playlist_name, track_ids, description)

    if not_found:
        print("\n⚠️ Aşağıdaki şarkılar bulunamadı:")
        for item in not_found:
            print(f"   - {item}")

    print("\n🎉 TAMAMLANDI! Spotify'da çalma listenizi kontrol edin.")
    print("🎶 İyi dinlemeler!")


if __name__ == "__main__":
    main()