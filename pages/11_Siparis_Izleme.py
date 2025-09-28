# pages/1_Siparis_Izleme.py (Detaylı Görünüm İçin Yeniden Tasarlandı)

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

# --- Filtreleme Arayüzü ---
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
            try:
                st.session_state['shopify_orders_display'] = shopify_api.get_orders_by_date_range(start_datetime, end_datetime)
            except Exception as e:
                st.error(f"Siparişler çekilirken bir hata oluştu: {e}")
                st.session_state['shopify_orders_display'] = []

# --- Sipariş Listesi ---
if 'shopify_orders_display' in st.session_state:
    if not st.session_state['shopify_orders_display']:
        st.success("Belirtilen tarih aralığında sipariş bulunamadı veya henüz siparişler getirilmedi.")
    else:
        st.header(f"Bulunan Siparişler ({len(st.session_state['shopify_orders_display'])} adet)")

        for order in st.session_state['shopify_orders_display']:
            # --- Status Renkleri ---
            financial_status = order.get('displayFinancialStatus', 'Bilinmiyor')
            fulfillment_status = order.get('displayFulfillmentStatus', 'Bilinmiyor')
            status_colors = {'PAID': 'green', 'PENDING': 'orange', 'REFUNDED': 'gray', 'FULFILLED': 'blue', 'UNFULFILLED': 'orange'}
            
            # --- Ana Başlık ---
            customer_name = (order.get('customer') or {}).get('firstName', '') + ' ' + (order.get('customer') or {}).get('lastName', '')
            st.subheader(f"Sipariş {order['name']} ({pd.to_datetime(order['createdAt']).strftime('%d %B %Y')})")
            st.markdown("---")

            # --- Sipariş Detayları (3 Sütunlu Yapı) ---
            col1, col2, col3 = st.columns([2, 1.2, 1.2])

            # --- SÜTUN 1: ÜRÜNLER VE ÖDEME ÖZETİ ---
            with col1:
                st.markdown(f"**Ödeme:** <span style='background-color:{status_colors.get(financial_status, 'gray')}; color:white; padding: 4px; border-radius: 5px;'>{financial_status}</span> &nbsp;&nbsp; **Gönderim:** <span style='background-color:{status_colors.get(fulfillment_status, 'gray')}; color:white; padding: 4px; border-radius: 5px;'>{fulfillment_status}</span>", unsafe_allow_html=True)
                
                # --- Ürünler Tablosu ---
                line_items_data = []
                for item in order.get('lineItems', {}).get('nodes', []):
                    original_price = float(item.get('originalUnitPriceSet', {}).get('shopMoney', {}).get('amount', 0.0))
                    discounted_price = float(item.get('discountedUnitPriceSet', {}).get('shopMoney', {}).get('amount', 0.0))
                    quantity = item.get('quantity', 0)
                    currency_code = item.get('originalUnitPriceSet', {}).get('shopMoney', {}).get('currencyCode', '')
                    
                    line_items_data.append({
                        "Ürün": item.get('title', 'N/A'),
                        "SKU": (item.get('variant') or {}).get('sku', 'N/A'),
                        "Fiyat": f"{original_price:.2f} x {quantity}",
                        "İndirim": f"{(original_price - discounted_price) * quantity:.2f}",
                        "Toplam": f"{discounted_price * quantity:.2f} {currency_code}"
                    })
                st.table(pd.DataFrame(line_items_data))

                # --- Fiyat Özeti ---
                subtotal = float(order.get('subtotalPriceSet', {}).get('shopMoney', {}).get('amount', 0.0))
                total_discount = float(order.get('totalDiscountsSet', {}).get('shopMoney', {}).get('amount', 0.0))
                shipping = float(order.get('totalShippingPriceSet', {}).get('shopMoney', {}).get('amount', 0.0))
                tax = float(order.get('totalTaxSet', {}).get('shopMoney', {}).get('amount', 0.0))
                total = float(order.get('totalPriceSet', {}).get('shopMoney', {}).get('amount', 0.0))
                currency = order.get('totalPriceSet', {}).get('shopMoney', {}).get('currencyCode', '')

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

            # --- SÜTUN 2: NOTLAR VE MÜŞTERİ BİLGİLERİ ---
            with col2:
                # --- Notlar ---
                st.markdown("**Notlar**")
                note = order.get('note')
                st.info(note if note else "Müşteriden not yok.")
                
                # --- Müşteri ---
                st.markdown("**Müşteri**")
                customer = order.get('customer') or {}
                st.write(f"**{customer.get('firstName', '')} {customer.get('lastName', '')}**")
                st.write(f"{customer.get('numberOfOrders', 0)} sipariş")
                st.write(f"📧 {customer.get('email', 'E-posta yok')}")
                st.write(f"📞 {customer.get('phone', 'Telefon yok')}")

            # --- SÜTUN 3: ADRESLER ---
            with col3:
                # --- Kargo Adresi ---
                st.markdown("**Kargo Adresi**")
                shipping_addr = order.get('shippingAddress') or {}
                st.text(f"""
{shipping_addr.get('name', '')}
{shipping_addr.get('address1', '')}
{shipping_addr.get('address2', '') or ''}
{shipping_addr.get('city', '')}, {shipping_addr.get('provinceCode', '')} {shipping_addr.get('zip', '')}
{shipping_addr.get('country', '')}
                """)
                
                # --- Fatura Adresi ---
                st.markdown("**Fatura Adresi**")
                billing_addr = order.get('billingAddress') or {}
                if billing_addr == shipping_addr:
                    st.write("_Kargo adresiyle aynı_")
                else:
                    st.text(f"""
{billing_addr.get('name', '')}
{billing_addr.get('address1', '')}
{billing_addr.get('address2', '') or ''}
{billing_addr.get('city', '')}, {billing_addr.get('provinceCode', '')} {billing_addr.get('zip', '')}
{billing_addr.get('country', '')}
                    """)
            
            st.markdown("---")