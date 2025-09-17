import os
import logging
import sys
import threading
import queue
import time
import re
from datetime import datetime

# Proje yolunu Python path'ine ekle
project_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_path)

from sync_runner import sync_products_from_sentos_api

# GitHub Actions için gelişmiş loglama
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def main():
    """
    10-worker sistemi ile zamanlanmış senkronizasyon
    """
    
    sync_mode_to_run = os.getenv("SYNC_MODE", "Sadece Stok ve Varyantlar")
    max_workers = int(os.getenv("MAX_WORKERS", "8"))  # GitHub Actions için konservatif
    
    print(f"🚀 GitHub Actions 10-Worker Sync başlıyor...")
    print(f"📅 Timestamp: {datetime.now().isoformat()}")
    print(f"📋 Mode: {sync_mode_to_run}")
    print(f"👥 Workers: {max_workers}")

    # GitHub Secrets'tan ayarları oku
    config = {
        "store_url": os.getenv("SHOPIFY_STORE"),
        "access_token": os.getenv("SHOPIFY_TOKEN"),
        "sentos_api_url": os.getenv("SENTOS_API_URL"),
        "sentos_api_key": os.getenv("SENTOS_API_KEY"),
        "sentos_api_secret": os.getenv("SENTOS_API_SECRET"),
        "sentos_cookie": os.getenv("SENTOS_COOKIE", ""),
    }

    # Eksik ayar kontrolü
    missing_keys = [key for key, value in config.items() if not value and key != "sentos_cookie"]
    if missing_keys:
        logging.error(f"❌ Eksik GitHub Secrets: {', '.join(missing_keys)}")
        sys.exit(1)

    try:
        # Progress tracking için queue ve event
        progress_queue = queue.Queue()
        stop_event = threading.Event()
        sync_completed = False
        sync_results = None
        
        def sync_progress_callback(update):
            progress_queue.put(update)
            
            # Console output için
            if 'message' in update:
                print(f"Progress: {update['message']}")
            if 'log_detail' in update:
                clean_log = re.sub('<[^<]+?>', '', update['log_detail'])
                if clean_log.strip():
                    print(f"Detail: {clean_log.strip()}")
            if 'stats' in update:
                stats = update['stats']
                print(f"Stats: {stats.get('processed', 0)}/{stats.get('total', 0)} "
                      f"(✅{stats.get('created', 0)+stats.get('updated', 0)} "
                      f"❌{stats.get('failed', 0)})")

        def sync_worker():
            nonlocal sync_completed, sync_results
            try:
                sync_products_from_sentos_api(
                    store_url=config["store_url"],
                    access_token=config["access_token"],
                    sentos_api_url=config["sentos_api_url"],
                    sentos_api_key=config["sentos_api_key"],
                    sentos_api_secret=config["sentos_api_secret"],
                    sentos_cookie=config["sentos_cookie"],
                    test_mode=False,
                    progress_callback=sync_progress_callback,
                    stop_event=stop_event,
                    sync_mode=sync_mode_to_run,
                    max_workers=max_workers
                )
            except Exception as e:
                logging.error(f"Sync worker error: {e}")
                progress_queue.put({'status': 'error', 'message': str(e)})

        # Sync thread başlat
        sync_thread = threading.Thread(target=sync_worker, daemon=True)
        sync_thread.start()
        
        # Progress monitoring loop
        start_time = time.time()
        timeout = 5400  # 90 dakika timeout
        
        while not sync_completed and time.time() - start_time < timeout:
            try:
                update = progress_queue.get(timeout=60)
                
                if update.get('status') == 'done':
                    sync_results = update.get('results', {})
                    sync_completed = True
                    break
                elif update.get('status') == 'error':
                    logging.error(f"❌ Sync failed: {update.get('message')}")
                    sys.exit(1)
                    
            except queue.Empty:
                if not sync_thread.is_alive():
                    logging.error("❌ Sync thread died unexpectedly")
                    sys.exit(1)
                print("⏳ Sync still running...")
                continue
        
        if not sync_completed:
            logging.error("❌ Sync timeout reached")
            stop_event.set()
            sys.exit(1)
        
        # Final sonuçları raporla
        if sync_results:
            stats = sync_results.get('stats', {})
            duration = sync_results.get('duration', 'Unknown')
            
            print(f"\n✅ Scheduled sync completed!")
            print(f"⏱️  Duration: {duration}")
            print(f"📊 Final Stats:")
            print(f"   - Total: {stats.get('processed', 0)}/{stats.get('total', 0)}")
            print(f"   - Created: {stats.get('created', 0)}")
            print(f"   - Updated: {stats.get('updated', 0)}")
            print(f"   - Failed: {stats.get('failed', 0)}")
            print(f"   - Skipped: {stats.get('skipped', 0)}")
            
            # GitHub Actions output
            if 'GITHUB_OUTPUT' in os.environ:
                with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                    f.write(f"sync_status=success\n")
                    f.write(f"total_processed={stats.get('processed', 0)}\n")
                    f.write(f"total_updated={stats.get('updated', 0)}\n")
                    f.write(f"total_failed={stats.get('failed', 0)}\n")
            
            # Hata varsa exit code 1
            if stats.get('failed', 0) > 0:
                logging.warning(f"⚠️  Completed with {stats.get('failed', 0)} failures")
                sys.exit(1)
        else:
            logging.error("❌ No sync results received")
            sys.exit(1)
            
        logging.info(f"✅ Zamanlanmış 10-worker sync tamamlandı: {sync_mode_to_run}")
        
    except Exception as e:
        logging.critical(f"❌ Kritik hata: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()