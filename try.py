import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

load_dotenv()

client_id = os.getenv("SPOTIPY_CLIENT_ID")
client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI")

if not all([client_id, client_secret, redirect_uri]):
    raise ValueError("Eksik çevresel değişkenler! Lütfen .env dosyasını kontrol edin.")

scope = "playlist-modify-public playlist-modify-private"
cache_path = ".test_cache"

# Eski cache'i temizle
if os.path.exists(cache_path):
    os.remove(cache_path)

auth_manager = SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    scope=scope,
    cache_path=cache_path,
    open_browser=True,
    show_dialog=True
)

sp = spotipy.Spotify(auth_manager=auth_manager)

# Kullanıcı bilgisi
user = sp.me()
print(f"✅ Bağlanıldı: {user['display_name']} (ID: {user['id']})")

# Playlist oluştur
try:
    playlist = sp.user_playlist_create(
        user=user["id"],
        name="Test Playlist (KNN)",
        public=False,
        description="Test amaçlı oluşturuldu."
    )
    print(f"✅ Playlist oluşturuldu! Link: {playlist['external_urls']['spotify']}")
except spotipy.exceptions.SpotifyException as e:
    print(f"❌ Hata: {e}")
    if e.http_status == 403:
        print("   → 403 Forbidden: Kullanıcı ID'niz Dashboard'da allowlist'e eklenmemiş veya hesap Premium değil.")
    else:
        print(f"   → HTTP {e.http_status}: {e.msg}")