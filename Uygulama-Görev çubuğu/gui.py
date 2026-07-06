# -*- coding: utf-8 -*-
"""
gui.py
Masaüstü arayüz pencereleri:
- SpotifySettingsDialog: Spotify API bilgilerini girme/düzenleme
- PlaylistWizard: mod seçiminden çalma listesi oluşturmaya kadar adım adım sihirbaz

Not: Buradaki mantık main.py'deki soru-cevap akışının birebir aynısıdır,
sadece input()/print() yerine tıklanabilir arayüz elemanları kullanılıyor.
"""

import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import config
import core

# --- Tema ---
BG = "#121212"
BG_PANEL = "#181818"
FG = "#FFFFFF"
FG_MUTED = "#B3B3B3"
ACCENT = "#1DB954"
ACCENT_HOVER = "#1ed760"
DANGER = "#e74c3c"
FONT_TITLE = ("Segoe UI", 16, "bold")
FONT_LABEL = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)


def style_root(widget):
    widget.configure(bg=BG)


def make_button(parent, text, command, primary=True, width=18):
    bg = ACCENT if primary else "#2a2a2a"
    fg = "#000000" if primary else FG
    b = tk.Button(
        parent, text=text, command=command, bg=bg, fg=fg,
        activebackground=ACCENT_HOVER if primary else "#3a3a3a",
        activeforeground=fg, relief="flat", font=("Segoe UI", 10, "bold"),
        width=width, bd=0, cursor="hand2", padx=8, pady=8
    )
    return b


class SpotifySettingsDialog(tk.Toplevel):
    def __init__(self, master, cfg, on_saved=None):
        super().__init__(master)
        self.cfg = cfg
        self.on_saved = on_saved
        self.title("Spotify Ayarları")
        self.geometry("460x420")
        self.resizable(False, False)
        style_root(self)
        self.grab_set()
        self._build()

    def _build(self):
        tk.Label(self, text="🎧 Spotify Bağlantı Ayarları", font=FONT_TITLE,
                  bg=BG, fg=FG).pack(pady=(20, 5))
        tk.Label(
            self,
            text="Bu bilgileri Spotify Developer Dashboard'dan (developer.spotify.com)\n"
                 "oluşturduğunuz uygulamadan alabilirsiniz.",
            font=FONT_SMALL, bg=BG, fg=FG_MUTED, justify="center"
        ).pack(pady=(0, 15))

        form = tk.Frame(self, bg=BG)
        form.pack(fill="x", padx=30)

        self.entry_id = self._add_field(form, "Client ID", self.cfg.get("spotify_client_id", ""))
        self.entry_secret = self._add_field(form, "Client Secret", self.cfg.get("spotify_client_secret", ""), show="•")
        self.entry_redirect = self._add_field(form, "Redirect URI", self.cfg.get(
            "spotify_redirect_uri", "http://127.0.0.1:8888/callback"))

        tk.Label(
            self,
            text="Not: Redirect URI'yi Dashboard'daki uygulama ayarlarına\n"
                 "birebir aynı şekilde eklemeniz gerekir.",
            font=FONT_SMALL, bg=BG, fg=FG_MUTED, justify="center"
        ).pack(pady=(10, 15))

        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(pady=10)
        make_button(btn_frame, "Kaydet", self._save, primary=True).grid(row=0, column=0, padx=6)
        make_button(btn_frame, "Önbelleği Temizle", self._clear_cache, primary=False).grid(row=0, column=1, padx=6)
        make_button(btn_frame, "İptal", self.destroy, primary=False).grid(row=0, column=2, padx=6)

    def _add_field(self, parent, label, default, show=None):
        tk.Label(parent, text=label, font=FONT_LABEL, bg=BG, fg=FG_MUTED, anchor="w").pack(fill="x", pady=(8, 2))
        var_entry = tk.Entry(parent, font=FONT_LABEL, bg=BG_PANEL, fg=FG, insertbackground=FG,
                              relief="flat", show=show)
        var_entry.insert(0, default)
        var_entry.pack(fill="x", ipady=6)
        return var_entry

    def _save(self):
        self.cfg["spotify_client_id"] = self.entry_id.get().strip()
        self.cfg["spotify_client_secret"] = self.entry_secret.get().strip()
        self.cfg["spotify_redirect_uri"] = self.entry_redirect.get().strip()
        config.save_config(self.cfg)
        messagebox.showinfo("Kaydedildi", "Spotify ayarları kaydedildi.", parent=self)
        if self.on_saved:
            self.on_saved()
        self.destroy()

    def _clear_cache(self):
        config.clear_spotify_cache()
        messagebox.showinfo("Temizlendi", "Spotify oturum önbelleği temizlendi.\n"
                                           "Bir sonraki bağlantıda tekrar giriş yapmanız istenecek.", parent=self)


class PlaylistWizard(tk.Toplevel):
    """Mod seçiminden çalma listesi oluşturmaya kadar adım adım sihirbaz."""

    MODE_MOOD, MODE_ACTIVITY, MODE_BOTH = 1, 2, 3

    def __init__(self, master, cfg):
        super().__init__(master)
        self.cfg = cfg
        self.title("Yeni Çalma Listesi Oluştur")
        self.geometry("520x480")
        self.resizable(False, False)
        style_root(self)
        self.grab_set()

        self.state = {
            "mode": self.MODE_BOTH,
            "target_valence": 0.5,
            "target_energy": 0.5,
            "playlist_name": "",
            "total_songs": 20,
        }
        self.df = None
        self.features = None

        self.container = tk.Frame(self, bg=BG)
        self.container.pack(fill="both", expand=True)
        self._show_step_mode()

    # ---------- ortak yardımcılar ----------
    def _clear(self):
        for w in self.container.winfo_children():
            w.destroy()

    def _header(self, title, subtitle=""):
        tk.Label(self.container, text=title, font=FONT_TITLE, bg=BG, fg=FG).pack(pady=(25, 5))
        if subtitle:
            tk.Label(self.container, text=subtitle, font=FONT_LABEL, bg=BG, fg=FG_MUTED,
                      wraplength=440, justify="center").pack(pady=(0, 15))

    def _nav(self, back_cmd=None, next_text="İleri", next_cmd=None):
        frame = tk.Frame(self.container, bg=BG)
        frame.pack(side="bottom", fill="x", pady=20, padx=30)
        if back_cmd:
            make_button(frame, "Geri", back_cmd, primary=False).pack(side="left")
        if next_cmd:
            make_button(frame, next_text, next_cmd, primary=True).pack(side="right")

    # ---------- adım 1: mod seçimi ----------
    def _show_step_mode(self):
        self._clear()
        self._header("Adım 1/4 — Ne için çalma listesi istiyorsun?",
                      "KNN algoritması bu tercihe göre en yakın enerji/ruh hali değerine\n"
                      "sahip şarkıları veri setinden bulacak.")

        self.mode_var = tk.IntVar(value=self.state["mode"])
        options = [
            (self.MODE_MOOD, "🙂 Sadece Ruh Hali (valans)"),
            (self.MODE_ACTIVITY, "⚡ Sadece Aktivite (enerji)"),
            (self.MODE_BOTH, "🎯 Hem Ruh Hali hem Aktivite"),
        ]
        box = tk.Frame(self.container, bg=BG)
        box.pack(pady=10)
        for val, text in options:
            tk.Radiobutton(
                box, text=text, variable=self.mode_var, value=val,
                font=("Segoe UI", 11), bg=BG, fg=FG, selectcolor=BG_PANEL,
                activebackground=BG, activeforeground=FG, anchor="w",
                indicatoron=True, padx=10, pady=8
            ).pack(fill="x", padx=40)

        self._nav(next_cmd=self._to_step_values)

    def _to_step_values(self):
        self.state["mode"] = self.mode_var.get()
        self._show_step_values()

    # ---------- adım 2: değerler ----------
    def _show_step_values(self):
        self._clear()
        mode = self.state["mode"]
        self._header("Adım 2/4 — Seviyeyi ayarla", "1: en düşük, 10: en yüksek")

        box = tk.Frame(self.container, bg=BG)
        box.pack(pady=10, fill="x", padx=40)

        self.valence_var = tk.IntVar(value=int(self.state["target_valence"] * 10))
        self.energy_var = tk.IntVar(value=int(self.state["target_energy"] * 10))

        if mode in (self.MODE_MOOD, self.MODE_BOTH):
            self._add_slider(box, "Ruh Hali  (1: üzgün → 10: mutlu)", self.valence_var)
        if mode in (self.MODE_ACTIVITY, self.MODE_BOTH):
            self._add_slider(box, "Aktivite  (1: sakin → 10: enerjik)", self.energy_var)

        self._nav(back_cmd=self._show_step_mode, next_cmd=self._to_step_details)

    def _add_slider(self, parent, label, var):
        tk.Label(parent, text=label, font=FONT_LABEL, bg=BG, fg=FG_MUTED, anchor="w").pack(fill="x", pady=(15, 0))
        tk.Scale(
            parent, from_=1, to=10, orient="horizontal", variable=var,
            bg=BG, fg=FG, troughcolor=BG_PANEL, highlightthickness=0,
            activebackground=ACCENT, sliderrelief="flat", font=FONT_LABEL
        ).pack(fill="x")

    def _to_step_details(self):
        mode = self.state["mode"]
        if mode in (self.MODE_MOOD, self.MODE_BOTH):
            self.state["target_valence"] = self.valence_var.get() / 10.0
        if mode in (self.MODE_ACTIVITY, self.MODE_BOTH):
            self.state["target_energy"] = self.energy_var.get() / 10.0
        self._show_step_details()

    # ---------- adım 3: isim & şarkı sayısı ----------
    def _show_step_details(self):
        self._clear()
        self._header("Adım 3/4 — Çalma listesi detayları")

        box = tk.Frame(self.container, bg=BG)
        box.pack(pady=10, fill="x", padx=40)

        tk.Label(box, text="Çalma listesi ismi", font=FONT_LABEL, bg=BG, fg=FG_MUTED, anchor="w").pack(
            fill="x", pady=(10, 2))
        self.name_entry = tk.Entry(box, font=FONT_LABEL, bg=BG_PANEL, fg=FG,
                                    insertbackground=FG, relief="flat")
        self.name_entry.insert(0, self.state["playlist_name"])
        self.name_entry.pack(fill="x", ipady=6)

        tk.Label(box, text="Kaç şarkı olsun? (en az 5)", font=FONT_LABEL, bg=BG, fg=FG_MUTED,
                  anchor="w").pack(fill="x", pady=(20, 2))
        self.count_spin = tk.Spinbox(box, from_=5, to=200, font=FONT_LABEL, bg=BG_PANEL, fg=FG,
                                      insertbackground=FG, relief="flat", justify="center")
        self.count_spin.delete(0, "end")
        self.count_spin.insert(0, str(self.state["total_songs"]))
        self.count_spin.pack(fill="x", ipady=6)

        self._nav(back_cmd=self._show_step_values, next_text="Oluştur", next_cmd=self._validate_and_run)

    def _validate_and_run(self):
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showwarning("Eksik bilgi", "Lütfen çalma listesine bir isim ver.", parent=self)
            return
        try:
            count = int(self.count_spin.get())
            if count < 5:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Geçersiz sayı", "Şarkı sayısı en az 5 olmalı.", parent=self)
            return

        if not self.cfg.get("csv_path"):
            messagebox.showwarning("Veri dosyası seçilmedi",
                                    "Lütfen önce görev çubuğu menüsünden bir veri dosyası (.csv) seç.",
                                    parent=self)
            return
        if not (self.cfg.get("spotify_client_id") and self.cfg.get("spotify_client_secret")):
            messagebox.showwarning("Spotify ayarları eksik",
                                    "Lütfen önce görev çubuğu menüsünden Spotify Ayarları'nı doldur.",
                                    parent=self)
            return

        self.state["playlist_name"] = name
        self.state["total_songs"] = count
        self._show_step_progress()

    # ---------- adım 4: ilerleme / sonuç ----------
    def _show_step_progress(self):
        self._clear()
        self._header("Adım 4/4 — Çalma listesi oluşturuluyor…")

        self.log_text = tk.Text(self.container, bg=BG_PANEL, fg=FG, font=("Consolas", 9),
                                 relief="flat", height=14, wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=30, pady=(0, 10))
        self.log_text.configure(state="disabled")

        self.progress = ttk.Progressbar(self.container, mode="indeterminate")
        self.progress.pack(fill="x", padx=30, pady=(0, 10))
        self.progress.start(12)

        self.close_btn = make_button(self.container, "Kapat", self.destroy, primary=False)
        # Kapat butonu iş bitene kadar gizli
        thread = threading.Thread(target=self._run_pipeline, daemon=True)
        thread.start()

    def _log(self, msg):
        def _append():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", msg + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.after(0, _append)

    def _run_pipeline(self):
        try:
            self._log("📂 Veri seti yükleniyor…")
            df, features = core.load_and_clean_data(self.cfg["csv_path"], log=self._log)

            mode = self.state["mode"]
            if mode == self.MODE_MOOD:
                weights = (0.001, 1.0)
            elif mode == self.MODE_ACTIVITY:
                weights = (1.0, 0.001)
            else:
                weights = (1.0, 1.0)

            self._log("🔎 En yakın şarkılar hesaplanıyor…")
            result = core.build_result_dataframe(
                df, features, mode,
                self.state["target_energy"], self.state["target_valence"], weights,
                self.state["total_songs"], log=self._log
            )

            self._log("🎵 Spotify'a bağlanılıyor (tarayıcı açılabilir)…")
            sp = core.get_spotify_client(
                self.cfg["spotify_client_id"],
                self.cfg["spotify_client_secret"],
                self.cfg["spotify_redirect_uri"],
                str(config.SPOTIFY_CACHE_PATH),
                log=self._log
            )

            self._log("🔍 Şarkılar Spotify'da aranıyor…")
            track_ids, not_found = [], []
            for i, (_, row) in enumerate(result.iterrows(), start=1):
                self._log(f"   {i}/{len(result)}: {row['track_name']} - {row['artists']}")
                tid = core.get_track_id(sp, row['track_name'], row['artists'])
                if tid:
                    track_ids.append(tid)
                else:
                    not_found.append(f"{row['track_name']} - {row['artists']}")

            if not track_ids:
                raise core.SpotifyConnectionError("Hiçbir şarkı Spotify'da bulunamadı!")

            self._log("📁 Çalma listesi oluşturuluyor…")
            _, url = core.create_playlist_and_add_tracks(
                sp, self.state["playlist_name"], track_ids,
                description="Senin için özel olarak hazırlandı 🎧", log=self._log
            )

            if not_found:
                self._log("\n⚠️ Bulunamayan şarkılar:")
                for item in not_found:
                    self._log(f"   - {item}")

            self.after(0, lambda: self._finish_success(url, len(track_ids), len(not_found)))

        except core.SpotifyConnectionError as e:
            self.after(0, lambda: self._finish_error(str(e)))
        except FileNotFoundError:
            self.after(0, lambda: self._finish_error(
                "Veri dosyası bulunamadı. Görev çubuğu menüsünden veri dosyasını yeniden seç."))
        except Exception as e:
            self.after(0, lambda: self._finish_error(f"Beklenmeyen hata: {e}"))

    def _finish_success(self, url, added_count, not_found_count):
        self.progress.stop()
        self.progress.pack_forget()
        self._log("\n🎉 TAMAMLANDI!")
        self.playlist_url = url

        btns = tk.Frame(self.container, bg=BG)
        btns.pack(pady=10)
        make_button(btns, "Spotify'da Aç", lambda: webbrowser.open(url), primary=True).grid(row=0, column=0, padx=6)
        make_button(btns, "Kapat", self.destroy, primary=False).grid(row=0, column=1, padx=6)

    def _finish_error(self, message):
        self.progress.stop()
        self.progress.pack_forget()
        self._log(f"\n❌ Hata: {message}")
        messagebox.showerror("Hata oluştu", message, parent=self)
        make_button(self.container, "Kapat", self.destroy, primary=False).pack(pady=10)
