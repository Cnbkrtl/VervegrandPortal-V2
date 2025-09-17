# pages/4_logs.py - Aktif Log Sistemi

import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from operations.log_manager import log_manager
import config_manager

def load_css():
    try:
        with open("style.css") as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except FileNotFoundError:
        pass

if not st.session_state.get("authentication_status"):
    st.error("Lütfen bu sayfaya erişmek için giriş yapın.")
    st.stop()

load_css()

st.markdown("""
<div class="main-header">
    <h1>📝 Loglar ve Raporlar</h1>
    <p>Tüm senkronizasyon işlemleri, fiyat güncellemeleri ve sistem logları</p>
</div>
""", unsafe_allow_html=True)

# Sidebar filters
with st.sidebar:
    st.header("🔍 Filtreler")
    
    # Date range
    date_range = st.selectbox(
        "Zaman Aralığı",
        ["Son 24 Saat", "Son 7 Gün", "Son 30 Gün", "Tümü"],
        index=1
    )
    
    # Log type filter
    log_type_filter = st.selectbox(
        "Log Tipi",
        ["Tümü", "Senkronizasyon", "Fiyat Güncelleme", "Hatalar", "Sistem"],
        index=0
    )
    
    # Source filter
    source_filter = st.selectbox(
        "Kaynak",
        ["Tümü", "Web Arayüzü", "GitHub Actions", "Zamanlanmış"],
        index=0
    )
    
    # Auto refresh
    auto_refresh = st.checkbox("Otomatik Yenile (30s)", value=False)
    
    if auto_refresh:
        st.rerun()

# Stats summary
st.subheader("📊 Özet İstatistikler")

# Get date range in days
days_map = {
    "Son 24 Saat": 1,
    "Son 7 Gün": 7,
    "Son 30 Gün": 30,
    "Tümü": 365
}
days = days_map.get(date_range, 7)

try:
    stats = log_manager.get_stats_summary(days)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Toplam İşlem",
            stats['total_operations'],
            help="Tüm senkronizasyon işlemleri"
        )
    
    with col2:
        st.metric(
            "Başarı Oranı",
            f"{stats['success_rate']:.1f}%",
            delta=f"{stats['successful_operations']}/{stats['total_operations']}",
            help="Başarılı işlem oranı"
        )
    
    with col3:
        st.metric(
            "İşlenen Ürün",
            f"{stats['total_processed']:,}",
            delta=f"+{stats['total_created']:,} yeni",
            help="Toplam işlenen ürün sayısı"
        )
    
    with col4:
        st.metric(
            "Hata Sayısı",
            stats['error_count'],
            delta=f"{stats['total_failed']:,} başarısız ürün",
            delta_color="inverse",
            help="Toplam hata ve başarısız ürün sayısı"
        )

except Exception as e:
    st.error(f"İstatistik alınırken hata: {e}")

st.markdown("---")

# Recent logs table
st.subheader("🔄 Son İşlemler")

try:
    # Apply filters
    log_type_map = {
        "Senkronizasyon": "sync",
        "Fiyat Güncelleme": "price_update", 
        "Hatalar": "error",
        "Sistem": "system"
    }
    
    log_type = log_type_map.get(log_type_filter) if log_type_filter != "Tümü" else None
    
    logs = log_manager.get_recent_logs(limit=100, log_type=log_type)
    
    if logs:
        # Convert to DataFrame
        df = pd.DataFrame(logs)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Apply date filter
        if date_range != "Tümü":
            cutoff_date = datetime.now() - timedelta(days=days)
            df = df[df['timestamp'] >= cutoff_date]
        
        # Apply source filter
        source_map = {
            "Web Arayüzü": "web_ui",
            "GitHub Actions": "github_actions",
            "Zamanlanmış": "scheduled"
        }
        if source_filter != "Tümü":
            source_val = source_map.get(source_filter)
            if source_val:
                df = df[df['source'] == source_val]
        
        if not df.empty:
            # Format data for display
            display_df = df.copy()
            display_df['Zaman'] = display_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
            display_df['Tip'] = display_df['log_type'].map({
                'sync': '🔄 Senkronizasyon',
                'price_update': '💰 Fiyat Güncelleme', 
                'error': '❌ Hata',
                'system': '⚙️ Sistem'
            })
            display_df['Durum'] = display_df['status'].map({
                'started': '🟡 Başlatıldı',
                'running': '🔵 Devam Ediyor',
                'completed': '✅ Tamamlandı',
                'failed': '❌ Başarısız',
                'partial': '⚠️ Kısmi Başarı'
            })
            display_df['Kaynak'] = display_df['source'].map({
                'web_ui': '🖥️ Web Arayüzü',
                'github_actions': '🤖 GitHub Actions',
                'scheduled': '⏰ Zamanlanmış'
            })
            
            # Select columns for display
            cols_to_show = ['Zaman', 'Tip', 'Durum', 'Kaynak', 'sync_mode', 'processed', 'duration']
            available_cols = [col for col in cols_to_show if col in display_df.columns]
            
            st.dataframe(
                display_df[available_cols].rename(columns={
                    'sync_mode': 'Mod',
                    'processed': 'İşlenen',
                    'duration': 'Süre'
                }),
                use_container_width=True,
                hide_index=True
            )
            
            # Detailed view
    with st.expander("📋 Detaylı Görünüm"):
        if 'df' in locals() and not df.empty:
            selected_idx = st.selectbox(
                "Log seçin:",
                range(len(df)),
                format_func=lambda x: f"{df.iloc[x]['timestamp'].strftime('%Y-%m-%d %H:%M')} - {df.iloc[x]['log_type']}"
            )

            if selected_idx is not None:
                log_detail = df.iloc[selected_idx].to_dict()
                base_shopify_url = None
                try:
                    shopify_store_url_full = config_manager.get('shopify_store_url')
                    if shopify_store_url_full:
                        base_shopify_url = '/'.join(shopify_store_url_full.split('/')[:3])
                    else:
                        st.warning("Shopify mağaza URL'si config dosyasında bulunamadı veya boş.")
                except Exception as e:
                    st.error(f"Config dosyasından URL alınırken hata oluştu: {e}")

                col1, col2 = st.columns(2)
                with col1:
                    st.write("**Temel Bilgiler:**")
                    st.write(f"- **ID:** {log_detail.get('id')}")
                    st.write(f"- **Zaman:** {log_detail.get('timestamp')}")
                    st.write(f"- **Tip:** {log_detail.get('log_type')}")
                    st.write(f"- **Durum:** {log_detail.get('status')}")
                    st.write(f"- **Kaynak:** {log_detail.get('source')}")
                    if log_detail.get('user_id'):
                        st.write(f"- **Kullanıcı:** {log_detail.get('user_id')}")

                with col2:
                    st.write("**İstatistikler:**")
                    stats_keys = ['total_products', 'processed', 'created', 'updated', 'failed', 'skipped', 'duration', 'worker_count']
                    for key in stats_keys:
                        if pd.notna(log_detail.get(key)):
                             st.write(f"- **{key.replace('_', ' ').capitalize()}:** {log_detail[key]}")

                if pd.notna(log_detail.get('error_message')):
                    st.write("**Hata Mesajı:**")
                    st.error(log_detail['error_message'])

                if pd.notna(log_detail.get('details')):
                    st.write("**Detaylar ve Bağlantılar:**")
                    try:
                        details_data = json.loads(log_detail['details'])
                        if base_shopify_url and 'processed_products' in details_data and details_data.get('processed_products'):
                            st.write("**İşlenen Ürünlere Hızlı Erişim:**")
                            product_links = []
                            for product in details_data['processed_products']:
                                if 'id' in product:
                                    try:
                                        numeric_id = product['id'].split('/')[-1]
                                        product_url = f"{base_shopify_url}/admin/products/{numeric_id}"
                                        product_title = product.get('title', f"ID: {numeric_id}")
                                        product_links.append(f"- [{product_title}]({product_url})")
                                    except (IndexError, TypeError):
                                        product_links.append(f"- Ürün ID'si ayrıştırılamadı: {product.get('id')}")
                                else:
                                    product_links.append("- Ürün bilgisi eksik (ID yok)")
                            st.markdown("\n".join(product_links), unsafe_allow_html=True)
                            st.markdown("---")
                        
                        st.json(details_data)
                    except (json.JSONDecodeError, TypeError):
                        st.text(log_detail['details'])
        else:
            st.info("Görüntülenecek log bulunamadı.")

except Exception as e:
    st.error(f"Loglar yüklenirken bir hata oluştu: {e}")

# Charts section
if logs and not df.empty:
    st.markdown("---")
    st.subheader("📈 Görsel Analiz")
    
    tab1, tab2, tab3 = st.tabs(["Zaman Serisi", "Durum Dağılımı", "Kaynak Analizi"])
    
    with tab1:
        # Timeline chart
        timeline_df = df.groupby([df['timestamp'].dt.date, 'status']).size().reset_index(name='count')
        timeline_df['timestamp'] = pd.to_datetime(timeline_df['timestamp'])
        
        if not timeline_df.empty:
            fig = px.line(
                timeline_df, 
                x='timestamp', 
                y='count',
                color='status',
                title="Günlük İşlem Sayısı",
                labels={'count': 'İşlem Sayısı', 'timestamp': 'Tarih'}
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        # Status distribution
        status_counts = df['status'].value_counts()
        if not status_counts.empty:
            fig = px.pie(
                values=status_counts.values,
                names=status_counts.index,
                title="Durum Dağılımı"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        # Source analysis
        source_counts = df['source'].value_counts()
        if not source_counts.empty:
            fig = px.bar(
                x=source_counts.index,
                y=source_counts.values,
                title="Kaynak Bazında İşlem Sayısı",
                labels={'x': 'Kaynak', 'y': 'İşlem Sayısı'}
            )
            st.plotly_chart(fig, use_container_width=True)

# Cleanup section
st.markdown("---")
st.subheader("🧹 Bakım İşlemleri")

col1, col2 = st.columns(2)

with col1:
    if st.button("🗑️ Eski Logları Temizle (30+ gün)", type="secondary"):
        try:
            deleted_count = log_manager.cleanup_old_logs(30)
            st.success(f"✅ {deleted_count} eski log kaydı silindi.")
        except Exception as e:
            st.error(f"❌ Temizleme sırasında hata: {e}")

with col2:
    st.info("📌 **Not:** Loglar otomatik olarak 30 gün sonra temizlenir.")

# Auto refresh
if auto_refresh:
    import time
    time.sleep(30)
    st.rerun()