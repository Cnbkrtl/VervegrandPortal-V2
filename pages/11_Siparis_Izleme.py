# pages/1_Siparis_Izleme.py (Hesaplamalar ve Gösterim Düzeltildi)

import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
import sys
import os

# --- Projenin ana dizinini Python'un arama yoluna ekle ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# ---------------------------------------------------------------------

from connectors.shopify_api import ShopifyAPI

st.set_page_config(layout="wide")
st.title("📊 Shopify Sipariş İzleme Ekranı")

# --- Oturum ve API Kontrolleri (Değişiklik yok) ---
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

# --- Filtreleme Arayüzü (Değişiklik yok) ---
with st.expander("Siparişleri Filtrele ve Görüntüle", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Başlangıç Tarihi", datetime.now().date() - timedelta(days=7))
    with col2:
        end_date = st.date_input("Bitiş Tarihi", datetime.now().date())
    if st.button("Shopify Siparişlerini Getir", type="primary", use_container_width=True):
        start_datetime = datetime.combine(start_date, datetime.min.time()).isoformat()
        end_datetime = datetime.combine(end_date, datetime.max.time()).isoformat()
        with st.spinner("Shopify'dan tüm sipariş detayları çekiliyor..."):
            st.session_state['shopify_orders_display'] = shopify_api.get_orders_by_date_range(start_datetime, end_datetime)

# --- Sipariş Listesi (GÜNCELLENDİ) ---
if 'shopify_orders_display' in st.session_state:
    if not st.session_state['shopify_orders_display']:
        st.success("Belirtilen tarih aralığında sipariş bulunamadı.")
    else:
        st.header(f"Bulunan Siparişler ({len(st.session_state['shopify_orders_display'])} adet)")

        for order in st.session_state['shopify_orders_display']:
            financial_status = order.get('displayFinancialStatus', 'Bilinmiyor')
            fulfillment_status = order.get('displayFulfillmentStatus', 'Bilinmiyor')
            status_colors = {'PAID': 'green', 'PENDING': 'orange', 'REFUNDED': 'gray', 'FULFILLED': 'blue', 'UNFULFILLED': 'orange'}
            
            customer = order.get('customer') or {}
            customer_name = f"{customer.get('firstName', '')} {customer.get('lastName', '')}".strip()
            expander_title = f"Sipariş {order['name']} - Müşteri: {customer_name or 'Misafir'}"
            
            with st.container():
                st.subheader(expander_title)
                
                main_cols = st.columns([2.5, 1]) # Ana layout için sütunlar

                with main_cols[0]: # Sol taraf (Ürünler ve Özet)
                    st.markdown(f"**Ödeme:** <span style='background-color:{status_colors.get(financial_status, 'gray')}; color:white; padding: 4px; border-radius: 5px;'>{financial_status}</span> &nbsp;&nbsp; **Gönderim:** <span style='background-color:{status_colors.get(fulfillment_status, 'gray')}; color:white; padding: 4px; border-radius: 5px;'>{fulfillment_status}</span>", unsafe_allow_html=True)
                    
                    # --- Ürünler Tablosu (Hesaplamalar Düzeltildi) ---
                    st.write("**Ürünler**")
                    line_items_data = []
                    for item in order.get('lineItems', {}).get('nodes', []):
                        quantity = item.get('quantity', 0)
                        currency_code = item.get('originalUnitPriceSet', {}).get('shopMoney', {}).get('currencyCode', '')
                        
                        original_price = float(item.get('originalUnitPriceSet', {}).get('shopMoney', {}).get('amount', 0.0))
                        discounted_price = float(item.get('discountedUnitPriceSet', {}).get('shopMoney', {}).get('amount', 0.0))
                        
                        # Satır başına toplam indirimi doğru al
                        line_total_discount = float(item.get('totalDiscountSet', {}).get('shopMoney', {}).get('amount', 0.0))
                        
                        line_items_data.append({
                            "Ürün": item.get('title', 'N/A'),
                            "SKU": (item.get('variant') or {}).get('sku', 'N/A'),
                            "Fiyat": f"{original_price:.2f} x {quantity}",
                            "İndirim": f"{line_total_discount:.2f}",
                            "Toplam": f"{(discounted_price * quantity):.2f} {currency_code}"
                        })
                    
                    df = pd.DataFrame(line_items_data)
                    st.dataframe(df.style.format({"İndirim": "{:.2f}", "Toplam": "{:.2f}"}), use_container_width=True)

                    # --- Fiyat Özeti (Hesaplamalar Düzeltildi) ---
                    subtotal = float(order.get('currentSubtotalPriceSet', {}).get('shopMoney', {}).get('amount', 0.0))
                    total_discount = float(order.get('currentTotalDiscountsSet', {}).get('shopMoney', {}).get('amount', 0.0))
                    shipping = float(order.get('totalShippingPriceSet', {}).get('shopMoney', {}).get('amount', 0.0))
                    tax = float(order.get('currentTotalTaxSet', {}).get('shopMoney', {}).get('amount', 0.0))
                    total = float(order.get('currentTotalPriceSet', {}).get('shopMoney', {}).get('amount', 0.0))
                    currency = order.get('currentTotalPriceSet', {}).get('shopMoney', {}).get('currencyCode', '')

                    st.markdown(f"""
                    <div style="text-align: right; line-height: 1.8;">
                        Ara Toplam: <b>{subtotal:.2f} {currency}</b><br>
                        İndirimler: <b style="color: #28a745;">-{total_discount:.2f} {currency}</b><br>
                        Kargo: <b>{shipping:.2f} {currency}</b><br>
                        Vergiler: <b>{tax:.2f} {currency}</b><br>
                        <hr style="margin: 4px 0;">
                        <h4>Toplam: <b>{total:.2f} {currency}</b></h4>
                    </div>
                    """, unsafe_allow_html=True)

                with main_cols[1]: # Sağ taraf (Not, Müşteri, Adresler)
                    st.markdown("**Notlar**")
                    note = order.get('note')
                    st.info(note if note else "Müşteriden not yok.")
                    
                    st.markdown("**Müşteri**")
                    st.write(f"**{customer_name or 'Misafir'}** ({customer.get('numberOfOrders', 0)} sipariş)")
                    st.write(f"📧 {customer.get('email', 'N/A')}")
                    st.write(f"📞 {customer.get('phone', 'N/A')}")

                    st.markdown("**Kargo Adresi**")
                    shipping_addr = order.get('shippingAddress') or {}
                    st.text(f"""
{shipping_addr.get('name', '')}
{shipping_addr.get('address1', '')}
{shipping_addr.get('address2', '') or ''}
{shipping_addr.get('city', '')}, {shipping_addr.get('provinceCode', '')} {shipping_addr.get('zip', '')}
{shipping_addr.get('country', '')}
                    """)
                st.markdown("---")