# -*- coding: utf-8 -*-
"""
gui.py
Masaüstü arayüz — minimal, düz ve akıcı.

Tasarım fikri: dekorasyonu değil hareketi ve tipografiyi öne çıkar.
Kutulu "kart"lar, yoğun emoji ve kalın çerçeveler yerine; büyük rakamlar,
ince bir segment anahtarı ve tek bir kayan vurgu rengi var. Her adım
geçişi ve her seçim yumuşak bir tween ile ilerliyor; ani zıplama yok.

Not: main.py'deki soru-cevap akışı (mod seç -> seviye ayarla -> isim/şarkı
sayısı -> oluştur) burada da birebir aynı sırayla ilerliyor. Sadece bu
dosyaya (gui.py) dokunuldu; core.py / config.py / app.py aynı kaldı.
"""

import threading
import webbrowser
import tkinter as tk
from tkinter import messagebox

import config
import core

# ------------------------------------------------------------------
# Tasarım tokenları
# ------------------------------------------------------------------
BG = "#0B0B0D"
SURFACE = "#18181B"
SURFACE_2 = "#232326"
TEXT = "#F5F5F7"
MUTED = "#75757E"
MUTED_2 = "#57575F"
ACCENT = "#1DB954"
ACCENT_SOFT = "#173620"
DANGER = "#F26161"

_FONT_CACHE = {}


def F(size, weight="normal"):
    key = ("Segoe UI", size, weight)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = (key[0], size, weight) if weight != "normal" else (key[0], size)
    return _FONT_CACHE[key]


EYEBROW = F(10, "bold")
TITLE = F(21, "bold")
BODY = F(11)
SMALL = F(9)
HERO = F(46, "bold")
MONO = ("Cascadia Mono", 9)


# ------------------------------------------------------------------
# Animasyon yardımcıları
# ------------------------------------------------------------------
def ease_out_cubic(t):
    return 1 - pow(1 - t, 3)


def ease_in_out(t):
    return 3 * t * t - 2 * t * t * t


def tween(widget, duration_ms, on_update, on_done=None, fps=60, easing=ease_out_cubic):
    steps = max(1, int(duration_ms / 1000 * fps))
    interval = max(1, int(duration_ms / steps))
    state = {"i": 0}

    def step():
        state["i"] += 1
        t = min(1.0, state["i"] / steps)
        try:
            on_update(easing(t))
        except tk.TclError:
            return
        if t < 1.0:
            widget.after(interval, step)
        elif on_done:
            on_done()

    step()


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(c))) for c in rgb)


def lerp_color(c1, c2, t):
    r1, g1, b1 = hex_to_rgb(c1)
    r2, g2, b2 = hex_to_rgb(c2)
    return rgb_to_hex((r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t))


def rr(x1, y1, x2, y2, r):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    return [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]


# ------------------------------------------------------------------
# Bileşenler
# ------------------------------------------------------------------
class SolidButton(tk.Canvas):
    """Düz, hafif dolgulu birincil buton — hover'da sadece ton değişir."""

    def __init__(self, parent, text, command=None, width=150, height=44, radius=10):
        super().__init__(parent, width=width, height=height, bg=parent["bg"],
                          highlightthickness=0, cursor="hand2")
        self.command = command
        self.w, self.h = width, height
        self.base, self.hover_c = ACCENT, "#25d467"
        self.current = self.base
        self.poly = self.create_polygon(rr(0, 0, width, height, radius), smooth=True,
                                         fill=self.base, outline="")
        self.label = self.create_text(width / 2, height / 2, text=text, fill="#08110b",
                                       font=F(11, "bold"))
        self.bind("<Enter>", lambda e: self._to(self.hover_c))
        self.bind("<Leave>", lambda e: self._to(self.base))
        self.bind("<ButtonRelease-1>", self._click)

    def _to(self, target):
        start = self.current

        def u(t):
            c = lerp_color(start, target, t)
            self.current = c
            self.itemconfig(self.poly, fill=c)

        tween(self, 130, u)

    def _click(self, e):
        if 0 <= e.x <= self.w and 0 <= e.y <= self.h and self.command:
            self.command()


class GhostButton(tk.Label):
    """Arka planı olmayan, sadece metin rengi yumuşakça açılan ikincil buton."""

    def __init__(self, parent, text, command=None):
        super().__init__(parent, text=text, font=F(11, "bold"), bg=parent["bg"],
                          fg=MUTED, cursor="hand2", padx=6)
        self.command = command
        self._pressed = False
        self.bind("<Enter>", lambda e: self._to(TEXT))
        self.bind("<Leave>", lambda e: self._to(MUTED))
        # SolidButton gibi press+release (release'de sınır kontrolü) kullan;
        # sadece "<Button-1>" ile anında tetiklemek, yan yana duran başka bir
        # butona basılırken bu butonun da tetiklenmesine yol açabiliyordu.
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _on_press(self, _e):
        self._pressed = True

    def _on_release(self, e):
        was_pressed = self._pressed
        self._pressed = False
        inside = 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height()
        if was_pressed and inside and self.command:
            self.command()

    def _to(self, target):
        start = self.cget("fg")

        def u(t):
            self.configure(fg=lerp_color(start, target, t))

        tween(self, 120, u)


class ProgressDots(tk.Canvas):
    """Üstte kalıcı duran, adım ilerledikçe dolan ince çizgiler."""

    def __init__(self, parent, total=4, width=140, height=4):
        super().__init__(parent, width=width, height=height, bg=parent["bg"], highlightthickness=0)
        self.total = total
        gap = 6
        seg_w = (width - gap * (total - 1)) / total
        self.segments = []
        for i in range(total):
            x1 = i * (seg_w + gap)
            poly = self.create_polygon(rr(x1, 0, x1 + seg_w, height, height / 2),
                                        smooth=True, fill=SURFACE_2, outline="")
            self.segments.append(poly)

    def set_step(self, n):
        for i, poly in enumerate(self.segments):
            target = ACCENT if i < n else SURFACE_2
            start = self.itemcget(poly, "fill")

            def u(t, poly=poly, start=start, target=target):
                self.itemconfig(poly, fill=lerp_color(start, target, t))

            tween(self, 220, u)


class SegmentedControl(tk.Canvas):
    """İnce, kayan vurgulu üçlü seçim anahtarı."""

    def __init__(self, parent, options, value, on_change, width=440, height=46):
        super().__init__(parent, width=width, height=height, bg=parent["bg"], highlightthickness=0)
        self.options = options
        self.on_change = on_change
        self.w, self.h = width, height
        self.n = len(options)
        self.seg_w = width / self.n
        self.value = value

        self.create_polygon(rr(0, 0, width, height, height / 2), smooth=True, fill=SURFACE, outline="")
        idx = [o[0] for o in options].index(value)
        m = 4
        x1 = idx * self.seg_w + m
        self.highlight = self.create_polygon(rr(x1, m, x1 + self.seg_w - 2 * m, height - m, (height - 2 * m) / 2),
                                              smooth=True, fill=ACCENT, outline="")
        self.texts = []
        for i, (val, label) in enumerate(options):
            cx = i * self.seg_w + self.seg_w / 2
            color = "#08110b" if val == value else MUTED
            t = self.create_text(cx, height / 2, text=label, font=F(10, "bold"), fill=color)
            self.texts.append(t)

        self.bind("<Button-1>", self._on_click)

    def _on_click(self, e):
        idx = min(self.n - 1, max(0, int(e.x // self.seg_w)))
        self.select(self.options[idx][0])

    def select(self, value, animate=True):
        if value == self.value and animate:
            return
        self.value = value
        idx = [o[0] for o in self.options].index(value)
        m = 4
        target_x1 = idx * self.seg_w + m

        coords = self.coords(self.highlight)
        start_x1 = coords[0] if coords else target_x1

        def u(t):
            x1 = start_x1 + (target_x1 - start_x1) * t
            self.coords(self.highlight, *rr(x1, m, x1 + self.seg_w - 2 * m, self.h - m, (self.h - 2 * m) / 2))

        tween(self, 200, u)

        for i, t_id in enumerate(self.texts):
            self.itemconfig(t_id, fill="#08110b" if self.options[i][0] == value else MUTED)

        if self.on_change:
            self.on_change(value)


class HeroSlider(tk.Canvas):
    """Büyük, canlı rakamlı; ince izli sürüklenebilir kaydırıcı."""

    def __init__(self, parent, left_caption, right_caption, min_v, max_v, init,
                 on_change=None, width=440):
        self.pad = 10
        self.track_y = 78
        h = 104
        super().__init__(parent, width=width, height=h, bg=parent["bg"], highlightthickness=0)
        self.w = width
        self.min_v, self.max_v = min_v, max_v
        self.value = init
        self.on_change = on_change

        self.hero = self.create_text(width / 2, 34, text=str(init), font=HERO, fill=TEXT)

        self.create_line(self.pad, self.track_y, width - self.pad, self.track_y,
                          fill=SURFACE_2, width=4, capstyle="round")
        self.fill = self.create_line(self.pad, self.track_y, self.pad, self.track_y,
                                      fill=ACCENT, width=4, capstyle="round")
        self.thumb = self.create_oval(0, 0, 0, 0, fill=TEXT, outline="")

        self.create_text(self.pad, self.track_y + 16, text=left_caption, anchor="w",
                          fill=MUTED, font=SMALL)
        self.create_text(width - self.pad, self.track_y + 16, text=right_caption, anchor="e",
                          fill=MUTED, font=SMALL)

        self._place(init, animate=False)
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)

    def _x_for(self, v):
        span = self.w - 2 * self.pad
        return self.pad + span * (v - self.min_v) / (self.max_v - self.min_v)

    def _v_for_x(self, x):
        span = self.w - 2 * self.pad
        ratio = max(0.0, min(1.0, (x - self.pad) / span))
        return round(self.min_v + ratio * (self.max_v - self.min_v))

    def _place(self, v, animate=True):
        x = self._x_for(v)

        def draw(x):
            self.coords(self.thumb, x - 7, self.track_y - 7, x + 7, self.track_y + 7)
            self.coords(self.fill, self.pad, self.track_y, x, self.track_y)

        if not animate:
            draw(x)
            return
        c = self.coords(self.thumb)
        start_x = (c[0] + c[2]) / 2 if c else self.pad
        tween(self, 130, lambda t: draw(start_x + (x - start_x) * t))

    def _set(self, v, animate):
        v = max(self.min_v, min(self.max_v, v))
        if v == self.value and not animate:
            return
        self.value = v
        self.itemconfig(self.hero, text=str(v))
        self._place(v, animate=animate)
        if self.on_change:
            self.on_change(v)

    def _on_press(self, e):
        self._set(self._v_for_x(e.x), animate=True)

    def _on_drag(self, e):
        self._set(self._v_for_x(e.x), animate=False)

    def get(self):
        return self.value


class Underline(tk.Frame):
    """Kutu yerine sadece alt çizgili, başlık gibi büyük yazı tipi kullanan giriş alanı."""

    def __init__(self, parent, placeholder, default="", width=440):
        super().__init__(parent, bg=parent["bg"])
        self.placeholder = placeholder
        self.showing_placeholder = not bool(default)

        self.entry = tk.Entry(self, font=F(18), bg=parent["bg"], fg=TEXT if default else MUTED,
                               insertbackground=TEXT, relief="flat", bd=0,
                               highlightthickness=0)
        self.entry.insert(0, default if default else placeholder)
        self.entry.pack(fill="x", ipady=6)

        self.line = tk.Frame(self, bg=SURFACE_2, height=2)
        self.line.pack(fill="x")

        self.entry.bind("<FocusIn>", self._focus_in)
        self.entry.bind("<FocusOut>", self._focus_out)

    def _focus_in(self, _e):
        if self.showing_placeholder:
            self.entry.delete(0, "end")
            self.entry.configure(fg=TEXT)
            self.showing_placeholder = False
        self._line_to(ACCENT)

    def _focus_out(self, _e):
        if not self.entry.get():
            self.entry.insert(0, self.placeholder)
            self.entry.configure(fg=MUTED)
            self.showing_placeholder = True
        self._line_to(SURFACE_2)

    def _line_to(self, target):
        start = self.line["bg"]
        tween(self, 150, lambda t: self.line.configure(bg=lerp_color(start, target, t)))

    def get(self):
        return "" if self.showing_placeholder else self.entry.get().strip()


class Pulse(tk.Canvas):
    """İnce, yavaşça ileri-geri kayan belirsiz ilerleme çizgisi."""

    def __init__(self, parent, width=440, height=3):
        super().__init__(parent, width=width, height=height, bg=parent["bg"], highlightthickness=0)
        self.w, self.h = width, height
        self.create_polygon(rr(0, 0, width, height, height / 2), smooth=True, fill=SURFACE_2, outline="")
        self.bar_w = width * 0.22
        self.bar = self.create_polygon(rr(0, 0, self.bar_w, height, height / 2), smooth=True,
                                        fill=ACCENT, outline="")
        self._running = False

    def start(self):
        self._running = True
        self._loop()

    def stop(self):
        self._running = False

    def _loop(self):
        if not self._running:
            return
        span = self.w + self.bar_w

        def u(t):
            x = -self.bar_w + span * t
            self.coords(self.bar, *rr(x, 0, x + self.bar_w, self.h, self.h / 2))

        tween(self, 1000, u, on_done=self._loop, easing=ease_in_out)


# ------------------------------------------------------------------
# Spotify Ayarları
# ------------------------------------------------------------------
class SpotifySettingsDialog(tk.Toplevel):
    def __init__(self, master, cfg, on_saved=None):
        super().__init__(master)
        self.cfg = cfg
        self.on_saved = on_saved
        self.title("Spotify Ayarları")
        self.configure(bg=BG)
        self.geometry("460x420")
        self.resizable(False, False)
        self.grab_set()
        self._build()

    def _build(self):
        tk.Label(self, text="SPOTIFY", font=EYEBROW, bg=BG, fg=ACCENT).pack(pady=(30, 4))
        tk.Label(self, text="Bağlantı bilgileri", font=TITLE, bg=BG, fg=TEXT).pack()
        tk.Label(self, text="developer.spotify.com üzerindeki uygulamandan alınır.",
                  font=BODY, bg=BG, fg=MUTED).pack(pady=(4, 26))

        form = tk.Frame(self, bg=BG)
        form.pack(fill="x", padx=40)

        self.f_id = Underline(form, "Client ID", self.cfg.get("spotify_client_id", ""))
        self.f_id.pack(fill="x", pady=10)
        self.f_secret = Underline(form, "Client Secret", self.cfg.get("spotify_client_secret", ""))
        self.f_secret.pack(fill="x", pady=10)
        self.f_redirect = Underline(form, "Redirect URI",
                                     self.cfg.get("spotify_redirect_uri", "http://127.0.0.1:8888/callback"))
        self.f_redirect.pack(fill="x", pady=10)

        btns = tk.Frame(self, bg=BG)
        btns.pack(pady=28)
        SolidButton(btns, "Kaydet", self._save, width=110).pack(side="left", padx=6)
        GhostButton(btns, "Önbelleği temizle", self._clear_cache).pack(side="left", padx=10)
        GhostButton(btns, "İptal", self.destroy).pack(side="left", padx=10)

    def _save(self):
        self.cfg["spotify_client_id"] = self.f_id.get()
        self.cfg["spotify_client_secret"] = self.f_secret.get()
        self.cfg["spotify_redirect_uri"] = self.f_redirect.get()
        config.save_config(self.cfg)
        messagebox.showinfo("Kaydedildi", "Spotify ayarları kaydedildi.", parent=self)
        if self.on_saved:
            self.on_saved()
        self.destroy()

    def _clear_cache(self):
        config.clear_spotify_cache()
        messagebox.showinfo("Temizlendi", "Spotify oturum önbelleği temizlendi.", parent=self)


# ------------------------------------------------------------------
# Sihirbaz
# ------------------------------------------------------------------
class PlaylistWizard(tk.Toplevel):
    MODE_MOOD, MODE_ACTIVITY, MODE_BOTH = 1, 2, 3
    WIDTH, HEIGHT = 540, 500

    def __init__(self, master, cfg):
        super().__init__(master)
        self.cfg = cfg
        self.title("Yeni Çalma Listesi")
        self.configure(bg=BG)
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.resizable(False, False)
        self.grab_set()

        self.state = {
            "mode": self.MODE_BOTH,
            "target_valence": 0.5,
            "target_energy": 0.5,
            "playlist_name": "",
            "total_songs": 20,
        }
        self.step_no = 1

        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", pady=(22, 0))
        self.dots = ProgressDots(top, total=4, width=120)
        self.dots.pack()
        self.dots.set_step(1)

        self.stage = tk.Frame(self, bg=BG)
        self.stage.pack(fill="both", expand=True)
        self.current_frame = None
        self._goto(self._build_step_mode, direction=0, step_no=1)

    # ---------- geçiş motoru ----------
    def _goto(self, builder, direction=1, step_no=None):
        if step_no:
            self.step_no = step_no
            self.dots.set_step(step_no)

        new_frame = tk.Frame(self.stage, bg=BG)
        builder(new_frame)

        if self.current_frame is None or direction == 0:
            new_frame.place(x=0, y=0, relwidth=1, relheight=1)
            self.current_frame = new_frame
            return

        old_frame = self.current_frame
        w = self.WIDTH
        new_frame.place(x=w * direction, y=0, relwidth=1, relheight=1)

        def u(t):
            new_frame.place_configure(x=int(w * direction * (1 - t)))
            old_frame.place_configure(x=int(-direction * w * t))

        tween(self, 240, u, on_done=old_frame.destroy)
        self.current_frame = new_frame

    def _shell(self, frame, eyebrow, title, subtitle=""):
        tk.Label(frame, text=eyebrow, font=EYEBROW, bg=BG, fg=ACCENT).pack(pady=(30, 4))
        tk.Label(frame, text=title, font=TITLE, bg=BG, fg=TEXT).pack()
        self.subtitle_label = tk.Label(frame, text=subtitle, font=BODY, bg=BG, fg=MUTED,
                                        wraplength=440, justify="center")
        self.subtitle_label.pack(pady=(4, 6))
        body = tk.Frame(frame, bg=BG)
        body.pack(fill="both", expand=True, padx=48, pady=(16, 0))
        return body

    def _nav(self, frame, back_cmd=None, next_text="Devam", next_cmd=None):
        bar = tk.Frame(frame, bg=BG)
        bar.place(relx=0.5, rely=1.0, anchor="s", y=-26)
        if back_cmd:
            GhostButton(bar, "Geri", back_cmd).pack(side="left", padx=(0, 18))
        if next_cmd:
            SolidButton(bar, next_text, next_cmd, width=160).pack(side="left")

    # ---------- adım 1: mod ----------
    def _build_step_mode(self, frame):
        body = self._shell(frame, "ADIM 1 / 4", "Ne dinlemek istersin?",
                            "Öneriler bu seçime göre eşleştirilecek.")

        wrap = tk.Frame(body, bg=BG)
        wrap.pack(pady=28)
        options = [
            (self.MODE_MOOD, "Ruh Hali"),
            (self.MODE_ACTIVITY, "Aktivite"),
            (self.MODE_BOTH, "İkisi de"),
        ]
        self.segmented = SegmentedControl(wrap, options, self.state["mode"], self._on_mode_change, width=440)
        self.segmented.pack()

        self.mode_caption = tk.Label(body, text=self._mode_caption(self.state["mode"]),
                                      font=BODY, bg=BG, fg=MUTED)
        self.mode_caption.pack(pady=(22, 0))

        self._nav(frame, next_cmd=lambda: self._goto(self._build_step_values, 1, 2))

    def _mode_caption(self, mode):
        return {
            self.MODE_MOOD: "Şarkılar ruh haline (valans) göre seçilir.",
            self.MODE_ACTIVITY: "Şarkılar enerji seviyesine göre seçilir.",
            self.MODE_BOTH: "Şarkılar hem ruh hali hem enerjiye göre seçilir.",
        }[mode]

    def _on_mode_change(self, value):
        self.state["mode"] = value
        self.mode_caption.configure(text=self._mode_caption(value))

    # ---------- adım 2: seviyeler ----------
    def _build_step_values(self, frame):
        mode = self.state["mode"]
        title = {
            self.MODE_MOOD: "Ruh halini ayarla",
            self.MODE_ACTIVITY: "Aktivite seviyesini ayarla",
            self.MODE_BOTH: "Seviyeleri ayarla",
        }[mode]
        body = self._shell(frame, "ADIM 2 / 4", title)

        self._valence_slider = None
        self._energy_slider = None

        if mode in (self.MODE_MOOD, self.MODE_BOTH):
            self._valence_slider = HeroSlider(body, "Üzgün", "Mutlu", 1, 10,
                                               int(self.state["target_valence"] * 10), width=440)
            self._valence_slider.pack(pady=10)

        if mode in (self.MODE_ACTIVITY, self.MODE_BOTH):
            self._energy_slider = HeroSlider(body, "Sakin", "Enerjik", 1, 10,
                                              int(self.state["target_energy"] * 10), width=440)
            self._energy_slider.pack(pady=10)

        self._nav(frame, back_cmd=lambda: self._goto(self._build_step_mode, -1, 1),
                   next_cmd=self._to_step_details)

    def _to_step_details(self):
        if self._valence_slider:
            self.state["target_valence"] = self._valence_slider.get() / 10.0
        if self._energy_slider:
            self.state["target_energy"] = self._energy_slider.get() / 10.0
        self._goto(self._build_step_details, 1, 3)

    # ---------- adım 3: detaylar ----------
    def _build_step_details(self, frame):
        body = self._shell(frame, "ADIM 3 / 4", "Son birkaç detay")

        self.name_field = Underline(body, "Çalma listesi adı", self.state["playlist_name"], width=440)
        self.name_field.pack(fill="x", pady=(10, 30))

        self.count_slider = HeroSlider(body, "5 şarkı", "100 şarkı", 5, 100,
                                        self.state["total_songs"], width=440)
        self.count_slider.pack()

        self._nav(frame, back_cmd=lambda: self._goto(self._build_step_values, -1, 2),
                   next_text="Oluştur", next_cmd=self._validate_and_run)

    def _validate_and_run(self):
        name = self.name_field.get()
        if not name:
            messagebox.showwarning("Eksik bilgi", "Lütfen çalma listesine bir isim ver.", parent=self)
            return
        if not self.cfg.get("csv_path"):
            messagebox.showwarning("Veri dosyası seçilmedi",
                                    "Görev çubuğu menüsünden bir veri dosyası (.csv) seç.", parent=self)
            return
        if not (self.cfg.get("spotify_client_id") and self.cfg.get("spotify_client_secret")):
            messagebox.showwarning("Spotify ayarları eksik",
                                    "Görev çubuğu menüsünden Spotify Ayarları'nı doldur.", parent=self)
            return

        self.state["playlist_name"] = name
        self.state["total_songs"] = self.count_slider.get()
        self._goto(self._build_step_progress, 1, 4)

    # ---------- adım 4: ilerleme ----------
    def _build_step_progress(self, frame):
        body = self._shell(frame, "ADIM 4 / 4", "Hazırlanıyor")

        self.pulse = Pulse(body, width=440)
        self.pulse.pack(pady=(4, 16))
        self.pulse.start()

        self.log_text = tk.Text(body, bg=BG, fg=MUTED, font=MONO, relief="flat",
                                 height=12, wrap="word", bd=0, highlightthickness=0)
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")

        self.result_bar = tk.Frame(frame, bg=BG)
        self.result_bar.place(relx=0.5, rely=1.0, anchor="s", y=-26)

        threading.Thread(target=self._run_pipeline, daemon=True).start()

    def _log(self, msg):
        def append():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", msg + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.after(0, append)

    def _run_pipeline(self):
        try:
            self._log("Veri seti yükleniyor…")
            df, features = core.load_and_clean_data(self.cfg["csv_path"], log=self._log)

            mode = self.state["mode"]
            weights = {
                self.MODE_MOOD: (0.001, 1.0),
                self.MODE_ACTIVITY: (1.0, 0.001),
                self.MODE_BOTH: (1.0, 1.0),
            }[mode]

            self._log("En yakın şarkılar hesaplanıyor…")
            result = core.build_result_dataframe(
                df, features, mode,
                self.state["target_energy"], self.state["target_valence"], weights,
                self.state["total_songs"], log=self._log
            )

            self._log("Spotify'a bağlanılıyor (tarayıcı açılabilir)…")
            sp = core.get_spotify_client(
                self.cfg["spotify_client_id"], self.cfg["spotify_client_secret"],
                self.cfg["spotify_redirect_uri"], str(config.SPOTIFY_CACHE_PATH), log=self._log
            )

            self._log("Şarkılar Spotify'da aranıyor…")
            track_ids, not_found = [], []
            for i, (_, row) in enumerate(result.iterrows(), start=1):
                self._log(f"  {i}/{len(result)}  {row['track_name']} — {row['artists']}")
                tid = core.get_track_id(sp, row['track_name'], row['artists'])
                if tid:
                    track_ids.append(tid)
                else:
                    not_found.append(f"{row['track_name']} - {row['artists']}")

            if not track_ids:
                raise core.SpotifyConnectionError("Hiçbir şarkı Spotify'da bulunamadı!")

            self._log("Çalma listesi oluşturuluyor…")
            _, url = core.create_playlist_and_add_tracks(
                sp, self.state["playlist_name"], track_ids,
                description="Senin için özel olarak hazırlandı", log=self._log
            )

            if not_found:
                self._log("\nBulunamayanlar:")
                for item in not_found:
                    self._log(f"  {item}")

            self.after(0, lambda: self._finish_success(url))

        except core.SpotifyConnectionError as e:
            self.after(0, lambda: self._finish_error(str(e)))
        except FileNotFoundError:
            self.after(0, lambda: self._finish_error(
                "Veri dosyası bulunamadı. Görev çubuğu menüsünden yeniden seç."))
        except Exception as e:
            self.after(0, lambda: self._finish_error(f"Beklenmeyen hata: {e}"))

    def _finish_success(self, url):
        self.pulse.stop()
        self.pulse.pack_forget()
        self._log("\nTamamlandı.")

        def open_link():
            # Ayrı thread'de açılır: tarayıcı başlatma bir anlığına takılırsa
            # bile arayüz donmasın / pencere tepkisiz görünmesin.
            threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()

        SolidButton(self.result_bar, "Spotify'da Aç", open_link, width=160).pack(
            side="left", padx=(0, 28))
        GhostButton(self.result_bar, "Kapat", self.destroy).pack(side="left")

    def _finish_error(self, message):
        self.pulse.stop()
        self.pulse.pack_forget()
        self._log(f"\nHata: {message}")
        GhostButton(self.result_bar, "Kapat", self.destroy).pack()
        messagebox.showerror("Hata oluştu", message, parent=self)
