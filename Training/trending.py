import os
import re
import sys
import time
from collections import Counter
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ClientError
from langdetect import detect, LangDetectException
from dotenv import load_dotenv

def setup_client():
    """Setup dan login Instagram client hanya dengan session ID"""
    load_dotenv()
    SESSIONID = os.getenv("IG_SESSIONID")
    
    if not SESSIONID:
        print("❌ IG_SESSIONID tidak ditemukan di file .env")
        print("💡 Cara mendapatkan session ID:")
        print("1. Login ke Instagram di browser")
        print("2. Buka Developer Tools (F12)")
        print("3. Buka tab Application/Storage")
        print("4. Cari cookie 'sessionid'")
        print("5. Copy value-nya dan simpan di file .env sebagai IG_SESSIONID")
        sys.exit(1)
    
    cl = Client()
    # Settings yang lebih kompatibel
    cl.setting = {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "device_settings": {
            "app_version": "269.0.0.18.75",
            "android_version": 26,
            "android_release": "8.0.0",
            "dpi": "420dpi",
            "resolution": "1080x1920",
            "manufacturer": "samsung",
            "device": "SM-G935F",
            "model": "herolte",
            "cpu": "samsungexynos8890"
        },
        "country": "ID",
        "locale": "id_ID",
        "timezone_offset": 25200  # GMT+7
    }
    
    try:
        cl.login_by_sessionid(SESSIONID)
        print("✅ Berhasil login dengan sessionid.")
        return cl
    except Exception as e:
        print(f"❌ Gagal login dengan sessionid: {e}")
        sys.exit(1)

def discover_trending_hashtags(cl, max_iterations=5):
    """
    Discover trending hashtags secara otomatis tanpa predefined hashtags
    """
    print("🎯 Memulai pencarian trending hashtag otomatis...")
    
    all_hashtags = []
    discovered_hashtags = set()
    iteration = 0
    
    # Start dengan beberapa seed hashtag umum
    current_hashtags = ["indonesia", "jakarta", "bandung", "bali", "surabaya"]
    
    while iteration < max_iterations and current_hashtags:
        print(f"\n📊 Iterasi {iteration + 1}/{max_iterations}")
        print(f"🔍 Mengeksplorasi {len(current_hashtags)} hashtag...")
        
        next_hashtags = set()
        
        for hashtag in current_hashtags:
            if hashtag in discovered_hashtags:
                continue
                
            try:
                print(f"   📥 Mengambil data untuk #{hashtag}...")
                
                # Ambil media dari hashtag
                media_list = cl.hashtag_medias_recent(hashtag, amount=15)
                
                hashtag_count = 0
                for media in media_list:
                    try:
                        caption = media.caption_text if hasattr(media, 'caption_text') else ""
                        if caption:
                            # Extract semua hashtag dari caption
                            tags = re.findall(r"#\w+", caption)
                            for tag in tags:
                                tag_lower = tag.lower()
                                all_hashtags.append(tag_lower)
                                
                                # Tambahkan ke hashtag baru untuk eksplorasi selanjutnya
                                if (tag_lower not in discovered_hashtags and 
                                    tag_lower != hashtag and 
                                    len(tag_lower) > 2):
                                    next_hashtags.add(tag_lower.replace('#', ''))
                                
                                hashtag_count += 1
                                
                    except Exception:
                        continue
                
                discovered_hashtags.add(hashtag)
                print(f"   ✅ #{hashtag}: ditemukan {hashtag_count} hashtag")
                
                # Delay untuk menghindari rate limit
                time.sleep(2)
                
            except Exception as e:
                print(f"   ⚠️ Gagal mengambil #{hashtag}: {str(e)[:50]}...")
                discovered_hashtags.add(hashtag)
                continue
        
        # Update hashtag untuk iterasi berikutnya
        current_hashtags = list(next_hashtags)[:10]  # Batasi untuk iterasi berikutnya
        iteration += 1
        
        if not current_hashtags:
            print("   ℹ️  Tidak ada hashtag baru yang ditemukan")
    
    return all_hashtags

def get_trending_from_explore(cl):
    """
    Ambil trending hashtag dari explore page
    """
    print("🔍 Mengambil data dari Explore Page...")
    
    all_hashtags = []
    
    try:
        # Ambil media dari explore page
        explore_media = cl.explore_medias(amount=20)
        
        for media in explore_media:
            try:
                caption = media.caption_text if hasattr(media, 'caption_text') else ""
                if caption:
                    # Cek bahasa Indonesia
                    try:
                        if detect(caption) == "id":
                            tags = re.findall(r"#\w+", caption)
                            all_hashtags.extend(tag.lower() for tag in tags)
                    except LangDetectException:
                        # Jika tidak bisa detect bahasa, tetap ambil hashtag
                        tags = re.findall(r"#\w+", caption)
                        all_hashtags.extend(tag.lower() for tag in tags)
            except Exception:
                continue
                
        print(f"✅ Explore Page: ditemukan {len(all_hashtags)} hashtag")
        
    except Exception as e:
        print(f"⚠️ Gagal mengambil dari Explore Page: {e}")
    
    return all_hashtags

def analyze_and_display_trending(hashtags, top_n=25):
    """Analisis dan tampilkan trending hashtags"""
    if not hashtags:
        print("❌ Tidak ada hashtag yang ditemukan.")
        return None
    
    counter = Counter(hashtags)
    total_hashtags = len(hashtags)
    unique_hashtags = len(counter)
    
    print(f"\n📊 Statistik Penemuan:")
    print(f"   Total hashtag dikumpulkan: {total_hashtags}")
    print(f"   Unique hashtag ditemukan: {unique_hashtags}")
    
    # Filter hanya hashtag yang muncul minimal 2 kali
    trending_filtered = [(tag, count) for tag, count in counter.most_common() if count >= 2]
    
    if not trending_filtered:
        print("❌ Tidak ada hashtag yang memenuhi kriteria trending.")
        return None
    
    trending = trending_filtered[:top_n]
    
    print(f"\n🔥 Top {len(trending)} Trending Hashtags Indonesia:")
    print("=" * 60)
    
    for i, (tag, count) in enumerate(trending, 1):
        percentage = (count / total_hashtags) * 100
        bar = "█" * min(int(count / 2), 20)  # Visual bar
        print(f"{i:2d}. {tag:25} {bar:20} {count:3d}x ({percentage:5.1f}%)")
    
    return trending

def main():
    """Main function"""
    print("🚀 Instagram Auto Trending Hashtag Discovery")
    print("=" * 55)
    print("🔍 Script akan secara otomatis menemukan trending hashtag")
    print("   tanpa perlu predefined hashtag dalam code!")
    print("=" * 55)
    
    try:
        # Setup client hanya dengan session ID
        cl = setup_client()
        
        all_hashtags = []
        
        # Method 1: Discovery otomatis
        print("\n🎯 METHOD 1: Auto Discovery dari Jaringan Hashtag...")
        discovered_hashtags = discover_trending_hashtags(cl, max_iterations=3)
        all_hashtags.extend(discovered_hashtags)
        
        # Method 2: Dari Explore Page
        print("\n🎯 METHOD 2: Mengambil dari Explore Page...")
        explore_hashtags = get_trending_from_explore(cl)
        all_hashtags.extend(explore_hashtags)
        
        if all_hashtags:
            trending = analyze_and_display_trending(all_hashtags)
            
            if trending:
                print(f"\n💡 Insight:")
                print(f"   • {len(trending)} hashtag trending ditemukan")
                print(f"   • Gunakan kombinasi hashtag populer dan niche")
                print(f"   • Update hashtag secara berkala untuk hasil terbaru")
        else:
            print("\n❌ Tidak ada hashtag yang berhasil dikumpulkan.")
            print("💡 Saran:")
            print("   - Cek koneksi internet")
            print("   - Pastikan session ID masih valid")
            print("   - Coba jalankan lagi beberapa saat kemudian")
        
        print(f"\n✅ Proses discovery selesai!")
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Program dihentikan oleh user.")
    except Exception as e:
        print(f"\n❌ Error tidak terduga: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()