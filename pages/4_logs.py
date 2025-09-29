# pages/4_logs.py - Gelişmiş Log ve Monitoring Sistemi

import streamlit as st
import pandas as pd
import json
import sqlite3
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import sys
import time
import io
import csv

# Projenin ana dizinini Python'un arama yoluna ekle
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from operations.log_manager import LogManager, log_manager
    LOG_MANAGER_AVAILABLE = True
except ImportError:
    LOG_MANAGER_AVAILABLE = False

# Alternatif log source'ları
def get_sync_history_logs():
    """Sync history JSON'dan log verilerini çıkar"""
    logs = []
    try:
        sync_file = os.path.join(project_root, 'sync_history.json')
        if os.path.exists(sync_file):
            with open(sync_file, 'r', encoding='utf-8') as f:
                sync_history = json.load(f)
            
            for i, sync in enumerate(sync_history):
                logs.append({
                    'id': i + 1,
                    'timestamp': sync.get('timestamp'),
                    'log_type': 'sync',
                    'status': 'completed' if sync.get('stats', {}).get('failed', 0) == 0 else 'partial',
                    'source': 'system',
                    'sync_mode': 'auto',
                    'processed': sync.get('stats', {}).get('processed', 0),
                    'created': sync.get('stats', {}).get('created', 0),
                    'updated': sync.get('stats', {}).get('updated', 0),
                    'failed': sync.get('stats', {}).get('failed', 0),
                    'skipped': sync.get('stats', {}).get('skipped', 0),
                    'details': json.dumps(sync.get('details', [])),
                    'duration': None,
                    'error_message': None
                })
    except Exception as e:
        st.error(f"Sync history yüklenirken hata: {e}")
    
    return logs

def get_system_logs():
    """Sistem loglarını çek"""
    logs = []
    try:
        log_dir = os.path.join(project_root, 'logs')
        if os.path.exists(log_dir):
            # SQLite veritabanı varsa onu kontrol et
            db_path = os.path.join(log_dir, 'sync_logs.db')
            if os.path.exists(db_path):
                with sqlite3.connect(db_path) as conn:
                    cursor = conn.execute("""
                        SELECT id, timestamp, log_type, status, source, sync_mode,
                               processed, created, updated, failed, skipped, 
                               duration, error_message, details
                        FROM sync_logs 
                        ORDER BY timestamp DESC 
                        LIMIT 1000
                    """)
                    
                    columns = [desc[0] for desc in cursor.description]
                    for row in cursor.fetchall():
                        logs.append(dict(zip(columns, row)))
    except Exception as e:
        st.error(f"Sistem logları yüklenirken hata: {e}")
    
    return logs

def load_css():
    try:
        with open(os.path.join(project_root, "style.css")) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except FileNotFoundError:
        pass

# Giriş kontrolü
if not st.session_state.get("authentication_status"):
    st.error("Lütfen bu sayfaya erişmek için giriş yapın.")
    st.stop()

load_css()

# Page config
st.set_page_config(page_title="Logs & Monitoring", layout="wide")

st.markdown("""
<div class="main-header">
    <h1>📊 Gelişmiş Log ve Monitoring Sistemi</h1>
    <p>Kapsamlı sistem izleme, log analizi ve performans metrikleri</p>
</div>
""", unsafe_allow_html=True)

# Sidebar - Gelişmiş Filtreler
with st.sidebar:
    st.header("� Gelişmiş Filtreler")
    
    # Veri kaynağı seçimi
    data_source = st.selectbox(
        "Veri Kaynağı",
        ["SQLite Database", "Sync History JSON", "Kombine Görünüm"],
        index=2
    )
    
    # Zaman aralığı
    time_range = st.selectbox(
        "Zaman Aralığı",
        ["Son 1 Saat", "Son 6 Saat", "Son 24 Saat", "Son 7 Gün", "Son 30 Gün", "Tümü"],
        index=3
    )
    
    # Log seviyesi
    log_level = st.selectbox(
        "Log Seviyesi",
        ["Tümü", "Kritik Hatalar", "Uyarılar", "Bilgi", "Debug"],
        index=0
    )
    
    # İşlem türü
    operation_type = st.multiselect(
        "İşlem Türü",
        ["Senkronizasyon", "Fiyat Güncelleme", "Ürün Oluşturma", "Ürün Güncelleme", "Hata Ayıklama"],
        default=["Senkronizasyon"]
    )
    
    # Başarı durumu
    success_filter = st.selectbox(
        "Başarı Durumu",
        ["Tümü", "Başarılı", "Başarısız", "Kısmi Başarı", "Devam Eden"],
        index=0
    )
    
    # Canlı izleme
    live_monitoring = st.checkbox("🔴 Canlı İzleme (5s)", value=False)
    
    # Ayarlar
    st.header("⚙️ Görünüm Ayarları")
    show_charts = st.checkbox("📊 Grafikleri Göster", value=True)
    show_details = st.checkbox("📋 Detayları Göster", value=True)
    items_per_page = st.selectbox("Sayfa başına kayıt", [25, 50, 100, 200], index=1)

# Ana içerik
# Canlı yenileme
if live_monitoring:
    placeholder = st.empty()
    auto_refresh_placeholder = st.empty()
    
    with auto_refresh_placeholder:
        st.info("🔴 Canlı izleme aktif - 5 saniyede bir yenileniyor...")

# Veri yükleme
@st.cache_data(ttl=60)  # 1 dakika cache
def load_all_logs():
    all_logs = []
    
    if data_source in ["SQLite Database", "Kombine Görünüm"]:
        all_logs.extend(get_system_logs())
    
    if data_source in ["Sync History JSON", "Kombine Görünüm"]:
        all_logs.extend(get_sync_history_logs())
    
    return all_logs

# Veri yükleme ve işleme
logs_data = load_all_logs()

if not logs_data:
    st.warning("📭 Hiç log verisi bulunamadı. Henüz bir işlem yapılmamış olabilir.")
    st.stop()

# DataFrame'e çevir
df = pd.DataFrame(logs_data)
df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')

# Filtreleme işlemleri
# Zaman filtresi
time_map = {
    "Son 1 Saat": 1/24,
    "Son 6 Saat": 6/24,
    "Son 24 Saat": 1,
    "Son 7 Gün": 7,
    "Son 30 Gün": 30,
    "Tümü": 365
}

if time_range != "Tümü":
    cutoff_time = datetime.now() - timedelta(days=time_map[time_range])
    df = df[df['timestamp'] >= cutoff_time]

# Başarı durumu filtresi
if success_filter != "Tümü":
    status_map = {
        "Başarılı": ["completed"],
        "Başarısız": ["failed"],
        "Kısmi Başarı": ["partial"],
        "Devam Eden": ["running", "started"]
    }
    if success_filter in status_map:
        df = df[df['status'].isin(status_map[success_filter])]

# Ana Dashboard Metrikleri
if not df.empty:
    st.subheader("📊 Anlık Sistem Durumu")
    
    # Üst metrikler
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        total_ops = len(df)
        st.metric("Toplam İşlem", total_ops)
    
    with col2:
        successful_ops = len(df[df['status'] == 'completed'])
        success_rate = (successful_ops / total_ops * 100) if total_ops > 0 else 0
        st.metric("Başarı Oranı", f"{success_rate:.1f}%", 
                 delta=f"{successful_ops}/{total_ops}")
    
    with col3:
        total_processed = df['processed'].sum()
        st.metric("İşlenen Ürün", f"{total_processed:,}")
    
    with col4:
        total_failed = df['failed'].sum()
        st.metric("Başarısız", total_failed, 
                 delta=-total_failed if total_failed > 0 else None,
                 delta_color="inverse")
    
    with col5:
        if not df.empty and df['timestamp'].notna().any():
            last_operation = df['timestamp'].max()
            time_since = datetime.now() - last_operation
            if time_since.total_seconds() < 3600:
                time_str = f"{int(time_since.total_seconds()/60)} dk önce"
            elif time_since.total_seconds() < 86400:
                time_str = f"{int(time_since.total_seconds()/3600)} sa önce"
            else:
                time_str = f"{time_since.days} gün önce"
            st.metric("Son İşlem", time_str)

    # Sistem Sağlık Durumu
    st.markdown("---")
    health_cols = st.columns([2, 1, 1])
    
    with health_cols[0]:
        if success_rate >= 95:
            st.success("✅ Sistem Mükemmel Durumda")
        elif success_rate >= 85:
            st.warning("⚠️ Sistem Normal, Bazı Uyarılar Var")
        else:
            st.error("❌ Sistem Kritik Durumda")
    
    with health_cols[1]:
        recent_failures = len(df[(df['status'] == 'failed') & 
                               (df['timestamp'] >= datetime.now() - timedelta(hours=24))])
        st.metric("24s İçinde Hata", recent_failures)
    
    with health_cols[2]:
        avg_processing = df['processed'].mean() if not df.empty else 0
        st.metric("Ortalama İşlem", f"{avg_processing:.0f}")

# Görsel Analiz
if show_charts and not df.empty:
    st.markdown("---")
    st.subheader("📈 Görsel Analiz ve Trendler")
    
    # Üç ayrı grafik sekmesi
    chart_tab1, chart_tab2, chart_tab3, chart_tab4 = st.tabs([
        "⏱️ Zaman Serisi", "📊 Durum Analizi", "🔄 İşlem Performansı", "🎯 Detaylı Metrikler"
    ])
    
    with chart_tab1:
        # Zaman serisi analizi
        if len(df) > 1:
            # Günlük işlem sayısı
            daily_stats = df.groupby([df['timestamp'].dt.date, 'status']).size().reset_index(name='count')
            daily_stats['timestamp'] = pd.to_datetime(daily_stats['timestamp'])
            
            fig = px.area(daily_stats, x='timestamp', y='count', color='status',
                         title="Günlük İşlem Dağılımı",
                         labels={'count': 'İşlem Sayısı', 'timestamp': 'Tarih'})
            st.plotly_chart(fig, use_container_width=True)
            
            # Saatlik aktivite haritası
            if len(df) > 24:
                df['hour'] = df['timestamp'].dt.hour
                df['day'] = df['timestamp'].dt.day_name()
                hourly_heatmap = df.groupby(['day', 'hour']).size().reset_index(name='count')
                
                if not hourly_heatmap.empty:
                    fig = px.density_heatmap(hourly_heatmap, x='hour', y='day', z='count',
                                           title="Saatlik Aktivite Haritası")
                    st.plotly_chart(fig, use_container_width=True)
    
    with chart_tab2:
        # Durum analizi
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            status_dist = df['status'].value_counts()
            fig = px.pie(values=status_dist.values, names=status_dist.index,
                        title="İşlem Durumu Dağılımı")
            st.plotly_chart(fig, use_container_width=True)
        
        with col_chart2:
            source_dist = df['source'].value_counts()
            fig = px.bar(x=source_dist.values, y=source_dist.index, 
                        orientation='h', title="Kaynak Dağılımı")
            st.plotly_chart(fig, use_container_width=True)
    
    with chart_tab3:
        # Performance metrikleri
        if 'processed' in df.columns and df['processed'].sum() > 0:
            # İşlem performance'ı
            perf_metrics = df.groupby(df['timestamp'].dt.date).agg({
                'processed': 'sum',
                'created': 'sum',
                'updated': 'sum',
                'failed': 'sum'
            }).reset_index()
            
            fig = make_subplots(rows=2, cols=2,
                              subplot_titles=('İşlenen Ürünler', 'Oluşturulan', 'Güncellenen', 'Başarısız'))
            
            fig.add_trace(go.Scatter(x=perf_metrics['timestamp'], y=perf_metrics['processed'],
                                   name='İşlenen'), row=1, col=1)
            fig.add_trace(go.Scatter(x=perf_metrics['timestamp'], y=perf_metrics['created'],
                                   name='Oluşturulan'), row=1, col=2)
            fig.add_trace(go.Scatter(x=perf_metrics['timestamp'], y=perf_metrics['updated'],
                                   name='Güncellenen'), row=2, col=1)
            fig.add_trace(go.Scatter(x=perf_metrics['timestamp'], y=perf_metrics['failed'],
                                   name='Başarısız'), row=2, col=2)
            
            fig.update_layout(height=600, title_text="Günlük Performance Metrikleri")
            st.plotly_chart(fig, use_container_width=True)
    
    with chart_tab4:
        # Detaylı metrikler
        if len(df) > 0:
            # Success rate trend
            df_sorted = df.sort_values('timestamp')
            df_sorted['success_rate_rolling'] = (
                df_sorted['status'].eq('completed').rolling(window=10, min_periods=1).mean() * 100
            )
            
            fig = px.line(df_sorted, x='timestamp', y='success_rate_rolling',
                         title="Başarı Oranı Trendi (10 İşlem Ortalaması)")
            fig.add_hline(y=95, line_dash="dash", line_color="green", 
                         annotation_text="Hedef: %95")
            st.plotly_chart(fig, use_container_width=True)

# Detaylı Log Tablosu
if show_details:
    st.markdown("---")
    st.subheader("📋 Detaylı Log Kayıtları")
    
    # Arama ve filtreleme
    search_cols = st.columns([3, 1])
    with search_cols[0]:
        search_query = st.text_input("🔍 Log içeriğinde ara:", 
                                   placeholder="Ürün adı, hata mesajı, ID...")
    with search_cols[1]:
        sort_order = st.selectbox("Sıralama", ["Yeni → Eski", "Eski → Yeni"])
    
    # Arama filtresi uygula
    display_df = df.copy()
    if search_query:
        mask = (
            display_df['details'].str.contains(search_query, case=False, na=False) |
            display_df['error_message'].str.contains(search_query, case=False, na=False)
        )
        display_df = display_df[mask]
    
    # Sıralama
    if sort_order == "Eski → Yeni":
        display_df = display_df.sort_values('timestamp')
    else:
        display_df = display_df.sort_values('timestamp', ascending=False)
    
    # Sayfalama
    total_records = len(display_df)
    total_pages = (total_records - 1) // items_per_page + 1 if total_records > 0 else 1
    
    page_cols = st.columns([1, 2, 1])
    with page_cols[1]:
        current_page = st.selectbox(
            f"Sayfa (Toplam: {total_pages}, Kayıt: {total_records})",
            range(1, total_pages + 1),
            index=0
        )
    
    # Sayfa verilerini al
    start_idx = (current_page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    page_df = display_df.iloc[start_idx:end_idx]
    
    if not page_df.empty:
        # Tablo gösterimi
        for idx, row in page_df.iterrows():
            with st.expander(
                f"🔸 {row['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if pd.notna(row['timestamp']) else 'N/A'} - "
                f"{row['log_type']} - {row['status']} "
                f"({row.get('processed', 0)} işlenen)",
                expanded=False
            ):
                detail_cols = st.columns([2, 2, 1])
                
                with detail_cols[0]:
                    st.write("**📊 İstatistikler:**")
                    stats_html = f"""
                    - **İşlenen:** {row.get('processed', 0)}
                    - **Oluşturulan:** {row.get('created', 0)}
                    - **Güncellenen:** {row.get('updated', 0)}
                    - **Başarısız:** {row.get('failed', 0)}
                    - **Atlanan:** {row.get('skipped', 0)}
                    """
                    st.markdown(stats_html)
                
                with detail_cols[1]:
                    st.write("**ℹ️ Detaylar:**")
                    info_html = f"""
                    - **ID:** {row.get('id', 'N/A')}
                    - **Kaynak:** {row.get('source', 'N/A')}
                    - **Mod:** {row.get('sync_mode', 'N/A')}
                    - **Süre:** {row.get('duration', 'N/A')}
                    """
                    st.markdown(info_html)
                
                with detail_cols[2]:
                    # İşlem durumu göstergesi
                    status = row.get('status', 'unknown')
                    if status == 'completed':
                        st.success("✅ Başarılı")
                    elif status == 'failed':
                        st.error("❌ Başarısız")
                    elif status == 'partial':
                        st.warning("⚠️ Kısmi")
                    else:
                        st.info("ℹ️ Diğer")
                
                # Hata mesajı
                if pd.notna(row.get('error_message')):
                    st.error(f"**Hata:** {row['error_message']}")
                
                # JSON detaylar
                if pd.notna(row.get('details')):
                    with st.expander("📄 JSON Detayları"):
                        try:
                            details_data = json.loads(row['details'])
                            st.json(details_data)
                        except:
                            st.text(row['details'])

# Export İşlemleri
st.markdown("---")
st.subheader("📥 Export ve Paylaşım")

export_cols = st.columns(4)

with export_cols[0]:
    if st.button("📊 Excel Export", use_container_width=True):
        if not df.empty:
            # Excel dosyası oluştur
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # Ana veriler
                export_df = df.copy()
                export_df['timestamp'] = export_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
                export_df.to_excel(writer, sheet_name='Logs', index=False)
                
                # Özet istatistikler
                summary_data = {
                    'Metrik': ['Toplam İşlem', 'Başarılı', 'Başarısız', 'Başarı Oranı'],
                    'Değer': [len(df), successful_ops, len(df) - successful_ops, f"{success_rate:.1f}%"]
                }
                pd.DataFrame(summary_data).to_excel(writer, sheet_name='Özet', index=False)
            
            st.download_button(
                label="📁 Excel Dosyasını İndir",
                data=output.getvalue(),
                file_name=f"logs_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

with export_cols[1]:
    if st.button("📄 CSV Export", use_container_width=True):
        if not df.empty:
            csv_buffer = io.StringIO()
            export_df = df.copy()
            export_df['timestamp'] = export_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
            export_df.to_csv(csv_buffer, index=False)
            
            st.download_button(
                label="📁 CSV Dosyasını İndir",
                data=csv_buffer.getvalue(),
                file_name=f"logs_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )

with export_cols[2]:
    if st.button("🧹 Log Temizleme", use_container_width=True):
        st.warning("Bu özellik geliştirilme aşamasında...")

with export_cols[3]:
    if st.button("⚠️ Alert Kurulumu", use_container_width=True):
        st.info("Alert sistemi geliştirilme aşamasında...")

# Canlı yenileme
if live_monitoring:
    time.sleep(5)
    st.rerun()

