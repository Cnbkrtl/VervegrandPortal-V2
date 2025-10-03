# pages/11_Siparis_Izleme.py (Tam Detaylı Sürüm)

import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
import sys
import os
import json

# --- Projenin ana dizinini Python'un arama yoluna ekle ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# ---------------------------------------------------------------------

from connectors.shopify_api import ShopifyAPI

st.set_page_config(page_title="Sipariş İzleme", layout="wide")
st.title("📊 Shopify Sipariş İzleme ve Analiz Paneli")

# --- Oturum ve API Kontrolleri ---
if 'authentication_status' not in st.session_state or not st.session_state['authentication_status']:
    st.warning("Lütfen devam etmek için giriş yapın.")
    st.stop()
if 'shopify_status' not in st.session_state or st.session_state['shopify_status'] != 'connected':
    st.error("Shopify bağlantısı kurulu değil. Lütfen Ayarlar sayfasından bilgilerinizi kontrol edin.")
    st.stop()

@st.cache_resource
def get_shopify_client():
    return ShopifyAPI(st.session_state['shopify_store'], st.session_state['shopify_token'])
shopify_api = get_shopify_client()

# --- Filtreleme ve Analiz Arayüzü ---
with st.expander("🔍 Sipariş Filtreleme ve Arama", expanded=True):
    # Üst sıra: Tarih filtreleri
    date_cols = st.columns(3)
    with date_cols[0]:
        start_date = st.date_input("Başlangıç Tarihi", datetime.now().date() - timedelta(days=7))
    with date_cols[1]:
        end_date = st.date_input("Bitiş Tarihi", datetime.now().date())
    with date_cols[2]:
        sort_order = st.selectbox("Sıralama", ["En Yeni", "En Eski", "Tutar (Yüksek-Düşük)", "Tutar (Düşük-Yüksek)"])
    
    # Alt sıra: Status filtreleri
    filter_cols = st.columns(4)
    with filter_cols[0]:
        financial_filter = st.selectbox("Ödeme Durumu", ["Tümü", "PAID", "PENDING", "REFUNDED", "PARTIALLY_PAID"])
    with filter_cols[1]:
        fulfillment_filter = st.selectbox("Kargo Durumu", ["Tümü", "FULFILLED", "UNFULFILLED", "PARTIALLY_FULFILLED"])
    with filter_cols[2]:
        customer_search = st.text_input("Müşteri Ara", placeholder="İsim, email veya telefon")
    with filter_cols[3]:
        order_search = st.text_input("Sipariş No", placeholder="#1001, #1002...")
    
    fetch_button = st.button("📥 Shopify Siparişlerini Getir", type="primary", use_container_width=True)
    
    if fetch_button:
        start_datetime = datetime.combine(start_date, datetime.min.time()).isoformat()
        end_datetime = datetime.combine(end_date, datetime.max.time()).isoformat()
        with st.spinner("Shopify'dan detaylı sipariş verileri çekiliyor..."):
            try:
                orders_result = shopify_api.get_orders_by_date_range(start_datetime, end_datetime)
                st.session_state['shopify_orders_display'] = orders_result
                st.success(f"✅ Başarıyla {len(orders_result) if orders_result else 0} sipariş getirildi!")
            except Exception as e:
                st.error(f"❌ Shopify siparişleri getirilirken hata oluştu: {str(e)}")
                st.session_state['shopify_orders_display'] = None
                st.code(f"Hata detayı: {str(e)}", language="text")

# --- Sipariş Listesi ve Analiz ---
if 'shopify_orders_display' in st.session_state:
    if not st.session_state['shopify_orders_display']:
        st.success("Belirtilen tarih aralığında sipariş bulunamadı.")
    else:
        orders = st.session_state['shopify_orders_display']
        
        # Filtreleme uygula
        if financial_filter != "Tümü":
            orders = [o for o in orders if o.get('displayFinancialStatus') == financial_filter]
        if fulfillment_filter != "Tümü":
            orders = [o for o in orders if o.get('displayFulfillmentStatus') == fulfillment_filter]
        if customer_search:
            search_lower = customer_search.lower()
            orders = [o for o in orders if any([
                search_lower in (o.get('customer') or {}).get('firstName', '').lower(),
                search_lower in (o.get('customer') or {}).get('lastName', '').lower(),
                search_lower in (o.get('customer') or {}).get('email', '').lower(),
                search_lower in (o.get('customer') or {}).get('phone', '').lower()
            ])]
        if order_search:
            orders = [o for o in orders if order_search.lower() in o.get('name', '').lower()]
        
        # Sıralama uygula
        if sort_order == "En Eski":
            orders = sorted(orders, key=lambda x: x.get('createdAt', ''))
        elif sort_order == "Tutar (Yüksek-Düşük)":
            orders = sorted(orders, key=lambda x: float(x.get('totalPriceSet', {}).get('shopMoney', {}).get('amount', 0)), reverse=True)
        elif sort_order == "Tutar (Düşük-Yüksek)":
            orders = sorted(orders, key=lambda x: float(x.get('totalPriceSet', {}).get('shopMoney', {}).get('amount', 0)))
        else:  # En Yeni (varsayılan)
            orders = sorted(orders, key=lambda x: x.get('createdAt', ''), reverse=True)
        
        # Özet istatistikler
        if orders:
            total_revenue = sum(float(o.get('totalPriceSet', {}).get('shopMoney', {}).get('amount', 0)) for o in orders)
            avg_order_value = total_revenue / len(orders) if orders else 0
            total_items = sum(sum(item.get('quantity', 0) for item in o.get('lineItems', {}).get('nodes', [])) for o in orders)
            
            st.header(f"📊 Sipariş Analizi ({len(orders)} sipariş)")
            
            # Özet kartları
            summary_cols = st.columns(4)
            with summary_cols[0]:
                st.metric("Toplam Sipariş", len(orders))
            with summary_cols[1]:
                currency = orders[0].get('totalPriceSet', {}).get('shopMoney', {}).get('currencyCode', 'TRY')
                st.metric("Toplam Gelir", f"{total_revenue:.2f} {currency}")
            with summary_cols[2]:
                st.metric("Ortalama Sipariş", f"{avg_order_value:.2f} {currency}")
            with summary_cols[3]:
                st.metric("Toplam Ürün", total_items)
            
            # Status dağılımları
            status_cols = st.columns(2)
            with status_cols[0]:
                st.subheader("💳 Ödeme Durumu")
                financial_stats = {}
                for order in orders:
                    status = order.get('displayFinancialStatus', 'Bilinmiyor')
                    financial_stats[status] = financial_stats.get(status, 0) + 1
                st.bar_chart(financial_stats)
            
            with status_cols[1]:
                st.subheader("📦 Kargo Durumu")
                fulfillment_stats = {}
                for order in orders:
                    status = order.get('displayFulfillmentStatus', 'Bilinmiyor')
                    fulfillment_stats[status] = fulfillment_stats.get(status, 0) + 1
                st.bar_chart(fulfillment_stats)
        
        st.header(f"📋 Sipariş Detayları ({len(orders)} adet)")
        
        # Görünüm seçenekleri
        view_cols = st.columns(3)
        with view_cols[0]:
            view_mode = st.radio("Görünüm Modu", ["Detaylı Kart", "Kompakt Liste", "Tablo Görünümü"], horizontal=True)
        with view_cols[1]:
            show_raw_data = st.checkbox("Ham JSON Verilerini Göster")
        with view_cols[2]:
            items_per_page = st.selectbox("Sayfa Başına", [10, 25, 50, 100], index=1)
        
        # Sayfalama
        total_pages = (len(orders) + items_per_page - 1) // items_per_page
        if total_pages > 1:
            page = st.number_input("Sayfa", min_value=1, max_value=total_pages, value=1) - 1
            start_idx = page * items_per_page
            end_idx = min(start_idx + items_per_page, len(orders))
            page_orders = orders[start_idx:end_idx]
            st.info(f"Sayfa {page + 1}/{total_pages} - Sipariş {start_idx + 1}-{end_idx}")
        else:
            page_orders = orders

        
        # Sipariş gösterimi
        if view_mode == "Tablo Görünümü":
            # Tablo görünümü
            table_data = []
            for order in page_orders:
                customer = order.get('customer') or {}
                customer_name = f"{customer.get('firstName', '')} {customer.get('lastName', '')}".strip()
                total = float(order.get('totalPriceSet', {}).get('shopMoney', {}).get('amount', 0))
                currency = order.get('totalPriceSet', {}).get('shopMoney', {}).get('currencyCode', 'TRY')
                
                # Güvenli tarih formatı
                created_at = order.get('createdAt', '')
                if created_at:
                    try:
                        order_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        date_str = order_date.strftime('%d.%m.%Y %H:%M')
                    except:
                        date_str = created_at[:10] if len(created_at) >= 10 else 'N/A'
                else:
                    date_str = 'N/A'
                
                table_data.append({
                    "Sipariş No": order.get('name', 'N/A'),
                    "Tarih": date_str,
                    "Müşteri": customer_name or 'Misafir',
                    "Email": customer.get('email', 'N/A'),
                    "Tutar": f"{total:.2f} {currency}",
                    "Ödeme": order.get('displayFinancialStatus', 'N/A'),
                    "Kargo": order.get('displayFulfillmentStatus', 'N/A'),
                    "Not": (order.get('note', '') or '')[:50] + '...' if len(order.get('note', '') or '') > 50 else (order.get('note', '') or 'Yok')
                })
            
            df = pd.DataFrame(table_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
        
        elif view_mode == "Kompakt Liste":
            # Kompakt liste görünümü
            for order in page_orders:
                customer = order.get('customer') or {}
                customer_name = f"{customer.get('firstName', '')} {customer.get('lastName', '')}".strip()
                total = float(order.get('totalPriceSet', {}).get('shopMoney', {}).get('amount', 0))
                currency = order.get('totalPriceSet', {}).get('shopMoney', {}).get('currencyCode', 'TRY')
                financial_status = order.get('displayFinancialStatus', 'Bilinmiyor')
                fulfillment_status = order.get('displayFulfillmentStatus', 'Bilinmiyor')
                
                # Status renkleri
                status_colors = {
                    'PAID': 'green', 'PENDING': 'orange', 'REFUNDED': 'gray', 'PARTIALLY_PAID': 'yellow',
                    'FULFILLED': 'blue', 'UNFULFILLED': 'orange', 'PARTIALLY_FULFILLED': 'purple'
                }
                
                with st.container(border=True):
                    cols = st.columns([2, 1, 1, 1, 1])
                    with cols[0]:
                        st.write(f"**{order.get('name')}** - {customer_name or 'Misafir'}")
                        st.caption(f"📧 {customer.get('email', 'N/A')}")
                    with cols[1]:
                        st.write(f"**{total:.2f} {currency}**")
                    with cols[2]:
                        st.markdown(f"<span style='background-color:{status_colors.get(financial_status, 'gray')}; color:white; padding: 2px 6px; border-radius: 3px; font-size: 12px;'>{financial_status}</span>", unsafe_allow_html=True)
                    with cols[3]:
                        st.markdown(f"<span style='background-color:{status_colors.get(fulfillment_status, 'gray')}; color:white; padding: 2px 6px; border-radius: 3px; font-size: 12px;'>{fulfillment_status}</span>", unsafe_allow_html=True)
                    with cols[4]:
                        # Güvenli tarih formatı
                        created_at = order.get('createdAt', '')
                        if created_at:
                            try:
                                order_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                                st.caption(order_date.strftime('%d.%m.%Y\n%H:%M'))
                            except:
                                st.caption(created_at[:10] if len(created_at) >= 10 else 'N/A')
                        else:
                            st.caption('N/A')
        
        else:  # Detaylı Kart Görünümü
            for order in page_orders:
                financial_status = order.get('displayFinancialStatus', 'Bilinmiyor')
                fulfillment_status = order.get('displayFulfillmentStatus', 'Bilinmiyor')
                status_colors = {
                    'PAID': 'green', 'PENDING': 'orange', 'REFUNDED': 'gray', 'PARTIALLY_PAID': 'yellow',
                    'FULFILLED': 'blue', 'UNFULFILLED': 'orange', 'PARTIALLY_FULFILLED': 'purple'
                }
                
                customer = order.get('customer') or {}
                customer_name = f"{customer.get('firstName', '')} {customer.get('lastName', '')}".strip()
                
                # Güvenli tarih formatı
                created_at = order.get('createdAt', '')
                if created_at:
                    try:
                        order_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        date_str = order_date.strftime('%d.%m.%Y %H:%M')
                        date_display = order_date.strftime('%d %B %Y, %H:%M')
                    except:
                        date_str = created_at[:16] if len(created_at) >= 16 else 'N/A'
                        date_display = created_at[:16] if len(created_at) >= 16 else 'N/A'
                        order_date = None
                else:
                    date_str = 'N/A'
                    date_display = 'N/A'
                    order_date = None
                
                with st.expander(f"🛍️ **{order.get('name')}** - {customer_name or 'Misafir'} ({date_str})", expanded=False):
                    # Ana bilgiler
                    info_cols = st.columns([2, 1])
                    with info_cols[0]:
                        st.markdown(f"""
                        **📅 Sipariş Tarihi:** {date_display}  
                        **💳 Ödeme Durumu:** <span style='background-color:{status_colors.get(financial_status, 'gray')}; color:white; padding: 4px 8px; border-radius: 5px;'>{financial_status}</span>  
                        **📦 Kargo Durumu:** <span style='background-color:{status_colors.get(fulfillment_status, 'gray')}; color:white; padding: 4px 8px; border-radius: 5px;'>{fulfillment_status}</span>
                        """, unsafe_allow_html=True)
                        
                        # Sipariş kimliği ve kaynağı
                        st.markdown(f"**🆔 Sipariş ID:** `{order.get('id', 'N/A')}`")
                        
                    with info_cols[1]:
                        # Fiyat özeti - sağa hizalı
                        subtotal = float(order.get('currentSubtotalPriceSet', {}).get('shopMoney', {}).get('amount', 0.0))
                        total_discount = float(order.get('totalDiscountsSet', {}).get('shopMoney', {}).get('amount', 0.0))
                        shipping = float(order.get('totalShippingPriceSet', {}).get('shopMoney', {}).get('amount', 0.0))
                        tax = float(order.get('totalTaxSet', {}).get('shopMoney', {}).get('amount', 0.0))
                        total = float(order.get('totalPriceSet', {}).get('shopMoney', {}).get('amount', 0.0))
                        currency_code = order.get('totalPriceSet', {}).get('shopMoney', {}).get('currencyCode', 'TRY')
                        
                        st.markdown(f"""
                        <div style="text-align: right; line-height: 1.6; font-size: 14px;">
                            <b>💰 FİYAT ÖZETİ</b><br>
                            Ara Toplam: <b>{subtotal:.2f} {currency_code}</b><br>
                            {"İndirimler: <b style='color: #28a745;'>-" + f"{total_discount:.2f} {currency_code}</b><br>" if total_discount > 0 else ""}
                            {"Kargo: <b>" + f"{shipping:.2f} {currency_code}</b><br>" if shipping > 0 else ""}
                            {"Vergiler: <b>" + f"{tax:.2f} {currency_code}</b><br>" if tax > 0 else ""}
                            <hr style="margin: 8px 0;">
                            <h3 style="color: #1f77b4;">TOPLAM: {total:.2f} {currency_code}</h3>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    st.divider()
                    
                    # Alt içerik - 3 kolon
                    detail_cols = st.columns([2, 1.2, 1])
                    
                    with detail_cols[0]:
                        # Ürün listesi
                        st.markdown("### 🛍️ Sipariş Edilen Ürünler")
                        
                        line_items_data = []
                        for item in order.get('lineItems', {}).get('nodes', []):
                            quantity = item.get('quantity', 0)
                            currency_code = item.get('originalUnitPriceSet', {}).get('shopMoney', {}).get('currencyCode', 'TRY')
                            original_price = float(item.get('originalUnitPriceSet', {}).get('shopMoney', {}).get('amount', 0.0))
                            discounted_price = float(item.get('discountedUnitPriceSet', {}).get('shopMoney', {}).get('amount', 0.0))
                            
                            # YENİ: Satır bazında vergi tutarını hesapla
                            tax_amount = sum(float(tax.get('priceSet', {}).get('shopMoney', {}).get('amount', 0.0)) for tax in item.get('taxLines', []))

                            line_items_data.append({
                                "🏷️ Ürün": item.get('title', 'N/A'),
                                "SKU": (item.get('variant') or {}).get('sku', 'N/A'),
                                "📦 Adet": quantity,
                                "💵 Birim Fiyat": original_price,
                                "💰 İndirimli": discounted_price,
                                "📊 Vergi": tax_amount, # Vergi tutarı eklendi
                                "🧾 Toplam": (discounted_price * quantity) + tax_amount # Toplam vergi dahil hesaplandı
                            })
                        
                        df = pd.DataFrame(line_items_data)
                        st.dataframe(
                            df, 
                            use_container_width=True, 
                            hide_index=True,
                            column_config={
                                "💵 Birim Fiyat": st.column_config.NumberColumn(format=f"%.2f {currency_code}"),
                                "💰 İndirimli": st.column_config.NumberColumn(format=f"%.2f {currency_code}"),
                                "📊 Vergi": st.column_config.NumberColumn(format=f"%.2f {currency_code}"),
                                "🧾 Toplam": st.column_config.NumberColumn(format=f"%.2f {currency_code}")
                            }
                        )
                    
                    with detail_cols[1]:
                        # Müşteri bilgileri
                        st.markdown("### 👤 Müşteri Bilgileri")
                        st.markdown(f"""
                        **👤 İsim:** {customer_name or 'Misafir Müşteri'}  
                        **📧 Email:** {customer.get('email', 'Belirtilmemiş')}  
                        **📞 Telefon:** {customer.get('phone', 'Belirtilmemiş')}  
                        **🛍️ Toplam Sipariş:** {customer.get('numberOfOrders', 0)} sipariş  
                        **🆔 Müşteri ID:** `{customer.get('id', 'N/A') or 'N/A'}`
                        """)
                        
                        # Kargo adresi
                        st.markdown("### 📍 Kargo Adresi")
                        shipping_addr = order.get('shippingAddress', {})
                        if shipping_addr:
                            st.markdown(f"""
                            **📝 Adres Sahibi:** {shipping_addr.get('name', 'Belirtilmemiş')}  
                            **🏠 Adres 1:** {shipping_addr.get('address1', 'Belirtilmemiş')}  
                            {"**🏠 Adres 2:** " + shipping_addr.get('address2', '') if shipping_addr.get('address2') else ""}  
                            **🌆 Şehir:** {shipping_addr.get('city', 'Belirtilmemiş')}  
                            **🗺️ Bölge:** {shipping_addr.get('province', 'Belirtilmemiş')} ({shipping_addr.get('provinceCode', '')})  
                            **📮 Posta Kodu:** {shipping_addr.get('zip', 'Belirtilmemiş')}  
                            **🌍 Ülke:** {shipping_addr.get('country', 'Belirtilmemiş')} ({shipping_addr.get('countryCodeV2', '')})  
                            **📞 Telefon:** {shipping_addr.get('phone', 'Belirtilmemiş')}
                            """)
                        else:
                            st.info("Kargo adresi bilgisi mevcut değil")
                    
                    with detail_cols[2]:
                        # Ek bilgiler ve notlar
                        st.markdown("### 📝 Sipariş Notları")
                        if order.get('note'):
                            st.info(f"💬 **Müşteri Notu:** {order.get('note')}")
                        else:
                            st.caption("Müşteri notu bulunmuyor")
                        
                        # Etiketler varsa
                        if order.get('tags'):
                            st.markdown("### 🏷️ Etiketler")
                            tags = order.get('tags', '').split(', ') if order.get('tags') else []
                            for tag in tags[:5]:  # İlk 5 etiketi göster
                                st.markdown(f"<span style='background-color:#e1f5fe; color:#01579b; padding: 2px 6px; border-radius: 10px; font-size: 12px; display: inline-block; margin: 2px;'>🏷️ {tag}</span>", unsafe_allow_html=True)
                        
                        # Risk analizi (varsa)
                        if order.get('riskLevel'):
                            risk_colors = {'LOW': 'green', 'MEDIUM': 'orange', 'HIGH': 'red'}
                            risk_level = order.get('riskLevel', 'UNKNOWN')
                            st.markdown("### ⚠️ Risk Seviyesi")
                            st.markdown(f"<span style='background-color:{risk_colors.get(risk_level, 'gray')}; color:white; padding: 4px 8px; border-radius: 5px;'>{risk_level}</span>", unsafe_allow_html=True)
                        
                        # İade bilgileri varsa
                        if order.get('returns'):
                            st.markdown("### 🔄 İadeler")
                            st.info(f"Bu siparişte {len(order.get('returns', []))} iade bulunmaktadır")
                        
                        # Ham veri göster seçeneği
                        if show_raw_data:
                            st.markdown("### 🔧 Ham JSON Verisi")
                            with st.expander("JSON Verilerini Görüntüle", expanded=False):
                                st.json(order)

        # Toplam sayfa sayısı bilgisi
        if total_pages > 1:
            st.info(f"📄 Toplam {total_pages} sayfa • Gösterilen: {len(page_orders)} sipariş • Toplam: {len(orders)} sipariş")

# --- Alt bilgi ---
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; font-size: 12px; padding: 10px;'>
    <p>📊 Shopify Sipariş İzleme ve Analiz Sistemi</p>
    <p>💡 <b>İpucu:</b> Büyük veri setleri için filtreleme kullanın • Ham JSON verilerini görmek için ilgili seçeneği işaretleyin</p>
</div>
""", unsafe_allow_html=True)