#!/usr/bin/env python3
# utils/dashboard_helpers.py

import json
import os
from datetime import datetime, timedelta
import logging

def get_sync_history_stats():
    """Sync history dosyasından sistem metriklerini çıkarır"""
    stats = {
        'last_sync_time': None,
        'total_syncs': 0,
        'success_rate': 0,
        'recent_syncs': [],
        'total_products_processed': 0,
        'total_created': 0,
        'total_updated': 0,
        'total_failed': 0,
        'avg_processing_time': 0
    }
    
    try:
        # Sync history dosyasını oku
        sync_file = os.path.join(os.path.dirname(__file__), '..', 'sync_history.json')
        if not os.path.exists(sync_file):
            return stats
            
        with open(sync_file, 'r', encoding='utf-8') as f:
            sync_history = json.load(f)
        
        if not sync_history:
            return stats
        
        # Genel istatistikler
        stats['total_syncs'] = len(sync_history)
        
        # Son sync zamanı
        if sync_history:
            last_sync = sync_history[0]  # İlk eleman en son sync
            stats['last_sync_time'] = last_sync.get('timestamp')
        
        # Son 10 sync'i al
        stats['recent_syncs'] = sync_history[:10]
        
        # Toplam işlem istatistikleri
        for sync in sync_history:
            sync_stats = sync.get('stats', {})
            stats['total_products_processed'] += sync_stats.get('processed', 0)
            stats['total_created'] += sync_stats.get('created', 0)
            stats['total_updated'] += sync_stats.get('updated', 0)
            stats['total_failed'] += sync_stats.get('failed', 0)
        
        # Başarı oranı (failed olmayan / toplam)
        total_processed = stats['total_products_processed']
        if total_processed > 0:
            success_count = total_processed - stats['total_failed']
            stats['success_rate'] = (success_count / total_processed) * 100
        
        # Son 7 günlük sync'ler
        seven_days_ago = datetime.now() - timedelta(days=7)
        recent_syncs_count = 0
        
        for sync in sync_history:
            try:
                sync_date = datetime.fromisoformat(sync['timestamp'].replace('Z', '+00:00'))
                if sync_date >= seven_days_ago:
                    recent_syncs_count += 1
            except:
                continue
        
        stats['recent_syncs_week'] = recent_syncs_count
        
    except Exception as e:
        logging.error(f"Sync history istatistikleri alınırken hata: {e}")
    
    return stats

def format_sync_time(timestamp_str):
    """Timestamp'i kullanıcı dostu formata çevirir"""
    if not timestamp_str:
        return "Henüz sync yapılmadı"
    
    try:
        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        now = datetime.now(timestamp.tzinfo)
        diff = now - timestamp
        
        if diff.days > 0:
            return f"{diff.days} gün önce"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} saat önce"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} dakika önce"
        else:
            return "Az önce"
    except:
        return timestamp_str

def get_system_health():
    """Sistem sağlık durumunu kontrol eder"""
    health = {
        'status': 'unknown',
        'issues': [],
        'recommendations': []
    }
    
    try:
        # Config dosyasını kontrol et
        config_file = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')
        if not os.path.exists(config_file):
            health['issues'].append('Konfigürasyon dosyası bulunamadı')
            health['recommendations'].append('config.yaml dosyasını oluşturun')
        
        # Log dosyasını kontrol et
        log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
        if not os.path.exists(log_dir):
            health['issues'].append('Log dizini bulunamadı')
        
        # Sync history kontrol et
        stats = get_sync_history_stats()
        if stats['total_syncs'] == 0:
            health['issues'].append('Henüz hiç sync işlemi yapılmamış')
            health['recommendations'].append('İlk sync işlemini başlatın')
        elif stats['success_rate'] < 90:
            health['issues'].append(f'Düşük başarı oranı: %{stats["success_rate"]:.1f}')
            health['recommendations'].append('Hata loglarını kontrol edin')
        
        # Genel durum
        if len(health['issues']) == 0:
            health['status'] = 'healthy'
        elif len(health['issues']) <= 2:
            health['status'] = 'warning'
        else:
            health['status'] = 'critical'
            
    except Exception as e:
        health['status'] = 'error'
        health['issues'].append(f'Sistem kontrolü sırasında hata: {str(e)}')
    
    return health