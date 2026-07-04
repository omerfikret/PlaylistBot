import pandas as pd
import numpy as np
import random  # Rastgele seçim için

# -------------------------------
# 1. Veriyi Yükle ve Temizle (Virgül ondalık ayracı düzeltmesi ile)
# -------------------------------
def load_and_clean_data(file_path):
    # decimal=',' ile ondalık virgülü doğru oku
    df = pd.read_csv(file_path, decimal=',')
    df_clean = df.drop_duplicates(subset=['track_name', 'artists']).copy()
    # Sayısal dönüşüm (güvenlik için)
    df_clean['energy'] = pd.to_numeric(df_clean['energy'], errors='coerce')
    df_clean['valence'] = pd.to_numeric(df_clean['valence'], errors='coerce')
    # NaN değerleri temizle
    df_clean = df_clean.dropna(subset=['energy', 'valence'])
    print(f"✅ Toplam benzersiz şarkı: {len(df_clean)}")
    features = df_clean[['energy', 'valence']].values.astype(float)
    return df_clean, features

# -------------------------------
# 2. KNN ile En Yakın Şarkıları Bul (Tie-breaking ile)
# -------------------------------
def find_closest_songs(df, features, target_energy, target_valence, weights, top_n=20):
    w_e, w_v = weights
    distances = []
    for idx, (energy, valence) in enumerate(features):
        dist = np.sqrt(w_e * (energy - target_energy)**2 + w_v * (valence - target_valence)**2)
        distances.append((idx, dist))
    
    distances.sort(key=lambda x: (x[1], np.random.random()))
    top_indices = [idx for idx, _ in distances[:top_n]]
    top_distances = [dist for _, dist in distances[:top_n]]
    
    result_df = df.iloc[top_indices].copy()
    result_df['distance'] = top_distances
    return result_df

# -------------------------------
# 3. Kullanıcı Arayüzü (Konsol)
# -------------------------------
def main():
    print("="*60)
    print("🎵  KNN Playlist Önerici (Hedefe Uygun Sanatçı Eklemesi ile)  🎵")
    print("="*60)
    
    # DOSYA ADINI KONTROL EDİN (envanter_özel.csv veya turkce_sarkilar.csv)
    df, features = load_and_clean_data('datasets/envanter_özel.csv')
    
    print("\nLütfen bir mod seçin:")
    print("1 - Sadece Ruh Hali (mood) – valans (1: üzgün, 10: mutlu)")
    print("2 - Sadece Aktivite (activity) – enerji (1: sakin, 10: enerjik)")
    print("3 - Hem Ruh Hali hem Aktivite (both)")
    
    while True:
        try:
            mode = int(input("Seçiminiz (1/2/3): "))
            if mode in [1,2,3]:
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
        print("\nRuh hali seviyenizi girin (1: çok üzgün, 10: çok mutlu):")
        target_valence = get_scaled_input("Değer (1-10): ")
        weights = (0.001, 1.0)  # Ana ağırlık valence, ikincil energy
        print(f"Hedef valans: {target_valence:.1f} (ruh hali, ikincil enerji ile tie-breaking)")
    
    elif mode == 2:
        print("\nAktivite seviyenizi girin (1: çok sakin, 10: çok enerjik):")
        target_energy = get_scaled_input("Değer (1-10): ")
        weights = (1.0, 0.001)  # Ana ağırlık energy, ikincil valence
        print(f"Hedef enerji: {target_energy:.1f} (aktivite, ikincil valans ile tie-breaking)")
    
    else:  # mode == 3
        print("\nHem ruh hali hem aktivite için değerler girin:")
        target_valence = get_scaled_input("Ruh hali (1: üzgün, 10: mutlu): ")
        target_energy = get_scaled_input("Aktivite (1: sakin, 10: enerjik): ")
        weights = (1.0, 1.0)  # Eşit ağırlık
        print(f"Hedef valans: {target_valence:.1f}, Hedef enerji: {target_energy:.1f} (her iki özellik)")
    
    # -------------------------------
    # 4. KNN ile 20 şarkıyı bul
    # -------------------------------
    result = find_closest_songs(df, features, target_energy, target_valence, weights, top_n=20)
    
    # -------------------------------
    # 5. Hedef sanatçılardan hedefe UYGUN 5 şarkı daha ekle (rastgelelik korunarak)
    # -------------------------------
    target_artists = [
        "Ezhel", "Motive", "UZI", "maNga", "Duman", "mor ve ötesi",
        "Tarkan", "Sezen Aksu", "Mert Demir", "Melike Şahin", "Mabel Matiz",
        "Dolu Kadehi Ters Tut", "Adamlar", "Yüzyüzeyken Konuşuruz"
    ]
    
    # Hedef sanatçılara ait şarkıları filtrele
    target_mask = df['artists'].isin(target_artists)
    target_songs = df[target_mask].copy()
    
    if not target_songs.empty:
        # Bu filtreli veri için özellik matrisi
        target_features = target_songs[['energy', 'valence']].values.astype(float)
        w_e, w_v = weights
        
        # Mesafeleri hesapla
        distances = []
        for idx, (energy, valence) in enumerate(target_features):
            dist = np.sqrt(w_e * (energy - target_energy)**2 + w_v * (valence - target_valence)**2)
            # Orijinal indeksi koru
            original_idx = target_songs.index[idx]
            distances.append((original_idx, dist))
        
        # Mesafeye göre sırala
        distances.sort(key=lambda x: x[1])
        
        # Zaten KNN listesinde olanları çıkar
        knn_keys = set(zip(result['track_name'], result['artists']))
        candidate_indices = []
        for idx, dist in distances:
            row = target_songs.loc[idx]
            if (row['track_name'], row['artists']) not in knn_keys:
                candidate_indices.append((idx, dist))
        
        # En yakın 10 aday arasından rastgele 5'ini seç (eğer 10'dan az varsa hepsinden seç)
        num_candidates = len(candidate_indices)
        if num_candidates > 0:
            # Önce en yakın 10'u al (veya varsa hepsi)
            top_candidates = candidate_indices[:min(10, num_candidates)]
            # Rastgele 5 seç (veya mevcutsa hepsi)
            num_to_add = min(5, len(top_candidates))
            if num_to_add > 0:
                selected = random.sample(top_candidates, num_to_add)
                
                # Seçilenleri result'a ekle
                added_songs = []
                for idx, dist in selected:
                    row = target_songs.loc[idx].copy()
                    row['distance'] = dist
                    added_songs.append(row)
                
                added_df = pd.DataFrame(added_songs)
                result = pd.concat([result, added_df], ignore_index=True)
                print(f"\n✨ Hedef sanatçılardan, hedef değerlere en yakın {len(top_candidates)} şarkı arasından rastgele {num_to_add} şarkı eklendi.")
            else:
                print("\n⚠️  Eklenebilecek yeni şarkı bulunamadı.")
        else:
            print("\n⚠️  Hedef sanatçılara ait, KNN listesinde olmayan şarkı bulunamadı.")
    else:
        print("\n⚠️  Belirtilen sanatçılara ait hiç şarkı bulunamadı.")
    
    # -------------------------------
    # 6. Sonuçları göster
    # -------------------------------
    print("\n" + "="*60)
    print(f"🎧  Öneri Listesi (KNN + Hedefe Uygun Sanatçı Eklemesi)  (mod: {mode})")
    print("="*60)
    
    for i, (idx, row) in enumerate(result.iterrows(), start=1):
        if pd.notna(row['distance']):
            dist_str = f"{row['distance']:.6f}"
        else:
            dist_str = "🎲 Rastgele"
        # Hangi kaynaktan geldiğini belirtmek için (opsiyonel)
        source = "KNN" if pd.notna(row['distance']) else "Rastgele"
        print(f"{i:2d}. {row['track_name']} - {row['artists']}  (distance: {dist_str})")
    
    print("\n🎶 İyi dinlemeler!")

if __name__ == "__main__":
    main()