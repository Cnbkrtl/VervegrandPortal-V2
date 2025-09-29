# pages/2_Stok_ve_Konum_Yonetimi.py

import streamlit as st
import pandas as pd
import sys
import os

# --- Projenin ana dizinini Python'un arama yoluna ekle ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# ---------------------------------------------------------------------

from connectors.shopify_api import ShopifyAPI
from connectors.sentos_api import SentosAPI

st.set_page_config(layout="wide")
st.title("📦 Stok ve Konum Yönetimi")
st.info("Bu sayfada, Shopify mağazanızdaki stok konumlarınızı Sentos depolarınız ile eşleştirebilirsiniz. Doğru stok yönetimi için bu eşleştirme kritik öneme sahiptir.")

# --- Oturum Durumunu Kontrol Et ---
if 'authentication_status' not in st.session_state or not st.session_state['authentication_status']:
    st.warning("Lütfen devam etmek için giriş yapın.")
    st.stop()

if 'shopify_status' not in st.session_state or st.session_state['shopify_status'] != 'connected':
    st.error("Shopify bağlantısı kurulu değil. Lütfen Ayarlar sayfasından bilgilerinizi kontrol edin.")
    st.stop()

# --- API Istemcilerini Başlat ---
@st.cache_resource
def get_api_clients():
    shopify_api = ShopifyAPI(st.session_state['shopify_store'], st.session_state['shopify_token'])
    sentos_api = SentosAPI(st.session_state['sentos_api_url'], st.session_state['sentos_api_key'], st.session_state['sentos_api_secret'], st.session_state.get('sentos_cookie'))
    return shopify_api, sentos_api

try:
    shopify_api, sentos_api = get_api_clients()
except Exception as e:
    st.error(f"API istemcileri başlatılırken bir hata oluştu: {e}")
    st.stop()

# --- Veri Çekme ---
@st.cache_data(ttl=300)
def load_data():
    shopify_locations = shopify_api.get_locations()
    sentos_warehouses = sentos_api.get_warehouses()
    return shopify_locations, sentos_warehouses

with st.spinner("Shopify konumları ve Sentos depoları yükleniyor..."):
    shopify_locations, sentos_warehouses = load_data()

if not shopify_locations:
    st.error("Shopify mağazanızda herhangi bir aktif stok konumu bulunamadı. Lütfen Shopify panelinden kontrol edin.")
    st.stop()

if not sentos_warehouses:
    st.error("Sentos hesabınızda herhangi bir depo bulunamadı. Lütfen Sentos panelinden kontrol edin.")
    st.stop()

# --- Eşleştirme Arayüzü ---
st.header("Konum-Depo Eşleştirmesi")

sentos_warehouse_options = {wh['id']: wh['name'] for wh in sentos_warehouses}
sentos_warehouse_options_list = list(sentos_warehouse_options.values())

for loc in shopify_locations:
    st.markdown("---")
    col1, col2 = st.columns([2, 3])
    
    with col1:
        st.subheader(f"📍 Shopify Konumu: `{loc['name']}`")
        st.caption(f"ID: `{loc['id']}`")
        address = loc.get('address', {})
        st.write(f"Adres: {address.get('city', 'N/A')}, {address.get('country', 'N/A')}")

    with col2:
        st.write("**Bu konumu hangi Sentos deposu ile eşleştirmek istersiniz?**")
        
        selected_warehouse_name = st.selectbox(
            label="Sentos Deposu Seçin",
            options=sentos_warehouse_options_list,
            key=f"warehouse_for_{loc['id']}",
            help="Bu Shopify konumundan gelen siparişlerin stokları, seçtiğiniz bu Sentos deposundan düşülecektir."
        )
        
        if st.button("Eşleştirmeyi Kaydet", key=f"save_{loc['id']}", type="primary"):
            selected_warehouse_id = [wh_id for wh_id, wh_name in sentos_warehouse_options.items() if wh_name == selected_warehouse_name][0]
            
            if selected_warehouse_id:
                with st.spinner("Eşleştirme güncelleniyor..."):
                    # Bu fonksiyonun Sentos API'sinde gerçek bir karşılığı olmalı.
                    # Örnek: result = sentos_api.update_shopify_location_mapping(1, loc['id'], selected_warehouse_id)
                    # if result.get('success'):
                    #     st.success(f"`{loc['name']}` konumu, `{selected_warehouse_name}` deposu ile başarıyla eşleştirildi!")
                    # else:
                    #     st.error(f"Eşleştirme başarısız: {result.get('message')}")
                    st.warning("Bu özellik henüz aktif değil. `sentos_api.py` içindeki ilgili fonksiyonun, Sentos panelinin kullandığı gerçek iç API isteği ile güncellenmesi gerekmektedir.")


st.markdown("---")
st.success("Tüm eşleştirmeler tamamlandığında, Sentos'un Shopify siparişlerindeki stokları doğru bir şekilde yönetmesi sağlanacaktır.")