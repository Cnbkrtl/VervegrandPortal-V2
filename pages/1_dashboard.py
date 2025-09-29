# pages/1_dashboard.py - Detaylı Dashboard

import streamlit as st
import sys
import os
from datetime import datetime, timedelta
import json
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import time

# Projenin ana dizinini Python'un arama yoluna ekle
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from connectors.shopify_api import ShopifyAPI
from connectors.sentos_api import SentosAPI

# Dashboard helper fonksiyonları - local olarak tanımla
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
        'recent_syncs_week': 0
    }
    
    try:
        sync_file = os.path.join(project_root, 'sync_history.json')
        if not os.path.exists(sync_file):
            return stats
            
        with open(sync_file, 'r', encoding='utf-8') as f:
            sync_history = json.load(f)
        
        if not sync_history:
            return stats
        
        stats['total_syncs'] = len(sync_history)
        
        if sync_history:
            stats['last_sync_time'] = sync_history[0].get('timestamp')
        
        stats['recent_syncs'] = sync_history[:10]
        
        for sync in sync_history:
            sync_stats = sync.get('stats', {})
            stats['total_products_processed'] += sync_stats.get('processed', 0)
            stats['total_created'] += sync_stats.get('created', 0)
            stats['total_updated'] += sync_stats.get('updated', 0)
            stats['total_failed'] += sync_stats.get('failed', 0)
        
        total_processed = stats['total_products_processed']
        if total_processed > 0:
            success_count = total_processed - stats['total_failed']
            stats['success_rate'] = (success_count / total_processed) * 100
        
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
        st.error(f"Sync history istatistikleri alınırken hata: {e}")
    
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
        config_file = os.path.join(project_root, 'config.yaml')
        if not os.path.exists(config_file):
            health['issues'].append('Konfigürasyon dosyası bulunamadı')
            health['recommendations'].append('config.yaml dosyasını oluşturun')
        
        log_dir = os.path.join(project_root, 'logs')
        if not os.path.exists(log_dir):
            health['issues'].append('Log dizini bulunamadı')
        
        stats = get_sync_history_stats()
        if stats['total_syncs'] == 0:
            health['issues'].append('Henüz hiç sync işlemi yapılmamış')
            health['recommendations'].append('İlk sync işlemini başlatın')
        elif stats['success_rate'] < 90:
            health['issues'].append(f'Düşük başarı oranı: %{stats["success_rate"]:.1f}')
            health['recommendations'].append('Hata loglarını kontrol edin')
        
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

# CSS'i yükle
def load_css():
    try:
        with open("style.css") as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning("style.css dosyası bulunamadı. Lütfen ana dizine ekleyin.")

# --- Giriş Kontrolü ve Sayfa Kurulumu ---
if not st.session_state.get("authentication_status"):
    st.error("Lütfen bu sayfaya erişmek için giriş yapın.")
    st.stop()

load_css()

# Page config
st.set_page_config(page_title="Dashboard", layout="wide")

# --- DASHBOARD SAYFASI ---
st.markdown("""
<div class="main-header">
    <h1>🏠 Gelişmiş Dashboard</h1>
    <p>Sentos ve Shopify API Entegrasyon Paneli - Detaylı Sistem Genel Bakışı</p>
</div>
""", unsafe_allow_html=True)

# API bağlantı fonksiyonları
@st.cache_resource(ttl=300)  # 5 dakika cache
def get_shopify_client():
    if st.session_state.get('shopify_status') != 'connected':
        return None
    return ShopifyAPI(st.session_state.get('shopify_store'), st.session_state.get('shopify_token'))

@st.cache_resource(ttl=300)  # 5 dakika cache
def get_sentos_client():
    if st.session_state.get('sentos_status') != 'connected':
        return None
    return SentosAPI(
        st.session_state.get('sentos_api_url', ''),
        st.session_state.get('sentos_api_key', ''),
        st.session_state.get('sentos_api_secret', ''),
        st.session_state.get('sentos_api_cookie', '')
    )

# Yenile butonu
col_refresh, col_auto = st.columns([1, 4])
with col_refresh:
    if st.button("🔄 Verileri Yenile", use_container_width=True):
        st.cache_resource.clear()
        st.rerun()

with col_auto:
    auto_refresh = st.checkbox("⏰ Otomatik yenileme (30s)", value=False)

if auto_refresh:
    st.markdown("---")
    time.sleep(30)
    st.rerun()

# --- SISTEM SAĞLIK DURUMU ---
st.markdown("### 🩺 Sistem Sağlık Durumu")
health = get_system_health()

health_cols = st.columns([2, 1, 1])
with health_cols[0]:
    if health['status'] == 'healthy':
        st.success("✅ Sistem sağlıklı çalışıyor")
    elif health['status'] == 'warning':
        st.warning("⚠️ Sistem uyarıları mevcut")
    else:
        st.error("❌ Sistem sorunları tespit edildi")

with health_cols[1]:
    if health['issues']:
        with st.expander("Sorunlar", expanded=True):
            for issue in health['issues']:
                st.write(f"• {issue}")

with health_cols[2]:
    if health['recommendations']:
        with st.expander("Öneriler"):
            for rec in health['recommendations']:
                st.write(f"• {rec}")

st.markdown("---")

# --- ANA İSTATİSTİKLER ---
main_cols = st.columns(2)

with main_cols[0]:
    st.markdown('<div class="status-card">', unsafe_allow_html=True)
    st.markdown("### 🏪 Shopify Detayları")
    
    shopify_api = get_shopify_client()
    if shopify_api:
        with st.spinner("Shopify verileri yükleniyor..."):
            try:
                shopify_stats = shopify_api.get_dashboard_stats()
                
                shop_info = shopify_stats.get('shop_info', {})
                
                # Shopify mağaza bilgileri
                info_cols = st.columns(2)
                with info_cols[0]:
                    st.metric("Bugünkü Sipariş", shopify_stats.get('orders_today', 0))
                    st.metric("Bu Haftaki Sipariş", shopify_stats.get('orders_this_week', 0))
                with info_cols[1]:
                    currency = shop_info.get('currencyCode', 'USD')
                    st.metric("Bugünkü Gelir", f"{shopify_stats.get('revenue_today', 0):.2f} {currency}")
                    st.metric("Bu Haftaki Gelir", f"{shopify_stats.get('revenue_this_week', 0):.2f} {currency}")
                
                # Mağaza bilgileri
                st.info(f"""
                **Mağaza:** {shop_info.get('name', 'N/A')}  
                **Plan:** {shop_info.get('plan', {}).get('displayName', 'N/A')}  
                **Domain:** {shop_info.get('primaryDomain', {}).get('host', 'N/A')}  
                **Ürün Sayısı:** {shopify_stats.get('products_count', 0)}
                """)
                
                # Son siparişler
                recent_orders = shopify_stats.get('recent_orders', [])
                if recent_orders:
                    st.write("**Son Siparişler:**")
                    for order in recent_orders[:3]:
                        order_name = order.get('name', 'N/A')
                        order_total = order.get('totalPriceSet', {}).get('shopMoney', {})
                        customer = order.get('customer', {})
                        customer_name = f"{customer.get('firstName', '')} {customer.get('lastName', '')}".strip()
                        
                        st.write(f"• {order_name} - {order_total.get('amount', 0)} {order_total.get('currencyCode', '')} ({customer_name})")
                
            except Exception as e:
                st.error(f"Shopify verileri alınamadı: {str(e)}")
    else:
        st.warning("Shopify bağlantısı yok. Ayarlar sayfasından bağlantıyı kontrol edin.")
    
    st.markdown('</div>', unsafe_allow_html=True)

with main_cols[1]:
    st.markdown('<div class="status-card">', unsafe_allow_html=True)
    st.markdown("### 🔗 Sentos API Detayları")
    
    sentos_api = get_sentos_client()
    if sentos_api:
        with st.spinner("Sentos verileri yükleniyor..."):
            try:
                sentos_stats = sentos_api.get_dashboard_stats()
                
                info_cols = st.columns(2)
                with info_cols[0]:
                    st.metric("Toplam Ürün", sentos_stats.get('total_products', 0))
                    st.metric("Kategori Sayısı", sentos_stats.get('categories_count', 0))
                
                with info_cols[1]:
                    st.metric("API Durumu", 
                            "✅ Bağlı" if sentos_stats['api_status'] == 'connected' else "❌ Hata")
                
                # Son güncellenen ürünler
                recent_updates = sentos_stats.get('recent_updates', [])
                if recent_updates:
                    st.write("**Son Güncellenen Ürünler:**")
                    for product in recent_updates[:3]:
                        st.write(f"• {product.get('name', 'N/A')[:50]}...")
                
            except Exception as e:
                st.error(f"Sentos verileri alınamadı: {str(e)}")
    else:
        st.warning("Sentos bağlantısı yok. Ayarlar sayfasından bağlantıyı kontrol edin.")
    
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")

# --- SYNC İSTATİSTİKLERİ ---
st.markdown("### 🔄 Senkronizasyon İstatistikleri")

sync_stats = get_sync_history_stats()

sync_cols = st.columns(4)
with sync_cols[0]:
    st.metric("Toplam Sync", sync_stats['total_syncs'])
with sync_cols[1]:
    st.metric("Başarı Oranı", f"%{sync_stats['success_rate']:.1f}")
with sync_cols[2]:
    st.metric("Son Sync", format_sync_time(sync_stats['last_sync_time']))
with sync_cols[3]:
    st.metric("Bu Hafta Sync", sync_stats.get('recent_syncs_week', 0))

# Sync detayları
detail_cols = st.columns(3)
with detail_cols[0]:
    st.metric("İşlenen Ürün", sync_stats['total_products_processed'])
with detail_cols[1]:
    st.metric("Güncellenen", sync_stats['total_updated'], 
              delta=sync_stats['total_updated'] - sync_stats['total_created'])
with detail_cols[2]:
    st.metric("Hatalı", sync_stats['total_failed'], 
              delta=-sync_stats['total_failed'] if sync_stats['total_failed'] > 0 else None)

# --- SON SYNC'LER GRAFİĞİ ---
if sync_stats['recent_syncs']:
    st.markdown("### 📊 Son Sync İşlemleri")
    
    # Grafik verilerini hazırla
    chart_data = []
    for sync in sync_stats['recent_syncs'][:10]:
        try:
            timestamp = datetime.fromisoformat(sync['timestamp'].replace('Z', '+00:00'))
            stats = sync.get('stats', {})
            
            chart_data.append({
                'Tarih': timestamp.strftime('%d/%m %H:%M'),
                'Başarılı': stats.get('updated', 0) + stats.get('created', 0),
                'Başarısız': stats.get('failed', 0),
                'Atlanan': stats.get('skipped', 0)
            })
        except:
            continue
    
    if chart_data:
        df = pd.DataFrame(chart_data)
        
        # Bar chart
        fig = px.bar(df, x='Tarih', y=['Başarılı', 'Başarısız', 'Atlanan'],
                     title="Son Sync İşlemleri",
                     color_discrete_map={'Başarılı': '#00cc96', 'Başarısız': '#ef553b', 'Atlanan': '#ffa15a'})
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

# --- HIZLI İŞLEMLER ---
st.markdown("---")
st.markdown("### ⚡ Hızlı İşlemler")

action_cols = st.columns(4)
with action_cols[0]:
    if st.button("🔄 Hemen Sync Başlat", use_container_width=True):
        st.info("Sync işlemi 'Sync' sayfasından başlatılabilir.")

with action_cols[1]:
    if st.button("📊 Sipariş Analizi", use_container_width=True):
        st.switch_page("pages/11_Siparis_Izleme.py")

with action_cols[2]:
    if st.button("⚙️ Ayarları Kontrol Et", use_container_width=True):
        st.switch_page("pages/2_settings.py")

with action_cols[3]:
    if st.button("📜 Log'ları İncele", use_container_width=True):
        st.switch_page("pages/4_logs.py")

# --- SİSTEM BİLGİLERİ ---
with st.expander("🔧 Sistem Bilgileri", expanded=False):
    system_cols = st.columns(2)
    
    with system_cols[0]:
        st.write("**Bağlantı Durumları:**")
        st.write(f"• Shopify: {st.session_state.get('shopify_status', 'unknown')}")
        st.write(f"• Sentos: {st.session_state.get('sentos_status', 'unknown')}")
        
    with system_cols[1]:
        st.write("**Son Aktiviteler:**")
        if sync_stats['recent_syncs']:
            for sync in sync_stats['recent_syncs'][:3]:
                try:
                    timestamp = datetime.fromisoformat(sync['timestamp'].replace('Z', '+00:00'))
                    st.write(f"• Sync: {timestamp.strftime('%d/%m/%Y %H:%M')}")
                except:
                    continue