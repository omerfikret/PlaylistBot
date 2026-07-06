# -*- coding: utf-8 -*-
"""
app.py
Görev çubuğu (system tray) uygulamasının giriş noktası.

Orijinal main.py'deki soru-cevap akışı (mod seç -> değerleri gir ->
isim/şarkı sayısı gir -> Spotify'a bağlan -> çalma listesi oluştur)
burada da AYNEN devam ediyor; tek fark artık terminale yazı yazmak yerine
görev çubuğundan açılan pencerelerle ilerliyor olman.
"""

import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import pystray
from PIL import Image, ImageDraw

import config
import gui


def build_icon_image():
    """Basit, Spotify yeşili bir nota ikonu çizer (dış dosyaya ihtiyaç yok)."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((2, 2, size - 2, size - 2), fill=(29, 185, 84, 255))
    # basit nota şekli
    d.ellipse((18, 38, 30, 50), fill=(18, 18, 18, 255))
    d.ellipse((34, 30, 46, 42), fill=(18, 18, 18, 255))
    d.rectangle((28, 16, 32, 44), fill=(18, 18, 18, 255))
    d.rectangle((44, 12, 48, 38), fill=(18, 18, 18, 255))
    d.line((28, 16, 48, 12), fill=(18, 18, 18, 255), width=4)
    return img


class TrayApp:
    def __init__(self):
        self.cfg = config.load_config()

        # Gizli ana pencere: tüm Toplevel pencereler buna bağlanır.
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("KNN Playlist Önerici")

        self.icon = pystray.Icon(
            "knn_playlist_app",
            build_icon_image(),
            "KNN Çalma Listesi Önerici",
            menu=self._build_menu()
        )

    def _build_menu(self):
        return pystray.Menu(
            pystray.MenuItem("🎵 Yeni Çalma Listesi Oluştur", self._open_wizard, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("📁 Veri Dosyası Seç…", self._choose_csv),
            pystray.MenuItem("⚙️ Spotify Ayarları…", self._open_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Çıkış", self._quit),
        )

    # --- pystray bu callback'leri kendi thread'inden çağırır,
    # bu yüzden gerçek işi self.root.after(0, ...) ile ana thread'e devrediyoruz.
    def _open_wizard(self, icon=None, item=None):
        self.root.after(0, self._open_wizard_main_thread)

    def _open_wizard_main_thread(self):
        self.cfg = config.load_config()
        gui.PlaylistWizard(self.root, self.cfg)

    def _choose_csv(self, icon=None, item=None):
        self.root.after(0, self._choose_csv_main_thread)

    def _choose_csv_main_thread(self):
        path = filedialog.askopenfilename(
            title="Şarkı veri setini seç (.csv)",
            filetypes=[("CSV dosyaları", "*.csv"), ("Tüm dosyalar", "*.*")]
        )
        if path:
            self.cfg["csv_path"] = path
            config.save_config(self.cfg)
            messagebox.showinfo("Kaydedildi", f"Veri dosyası ayarlandı:\n{path}")

    def _open_settings(self, icon=None, item=None):
        self.root.after(0, self._open_settings_main_thread)

    def _open_settings_main_thread(self):
        def refresh():
            self.cfg = config.load_config()
        gui.SpotifySettingsDialog(self.root, self.cfg, on_saved=refresh)

    def _quit(self, icon=None, item=None):
        self.icon.stop()
        self.root.after(0, self.root.quit)

    def run(self):
        # Tray ikonunu ayrı bir thread'de çalıştır, Tk mainloop ana thread'de kalsın.
        tray_thread = threading.Thread(target=self.icon.run, daemon=True)
        tray_thread.start()

        # İlk açılışta ayarlar eksikse kullanıcıyı bilgilendir.
        if not self.cfg.get("csv_path") or not self.cfg.get("spotify_client_id"):
            self.root.after(500, self._show_first_run_hint)

        self.root.mainloop()

    def _show_first_run_hint(self):
        messagebox.showinfo(
            "Hoş geldin 🎵",
            "Başlamadan önce görev çubuğundaki simgeye sağ tıklayıp:\n\n"
            "1) 'Veri Dosyası Seç…' ile şarkı veri setini (.csv)\n"
            "2) 'Spotify Ayarları…' ile Spotify API bilgilerini gir.\n\n"
            "Sonra 'Yeni Çalma Listesi Oluştur' ile devam edebilirsin."
        )


if __name__ == "__main__":
    if sys.platform == "darwin":
        # macOS'ta pystray + tkinter birlikte çalışırken bazı sürümlerde
        # ana thread uyarısı verebilir; bilgi amaçlı.
        pass
    TrayApp().run()
