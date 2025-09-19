# pages/7_Metafield_Yonetimi.py

import streamlit as st
from connectors.shopify_api import ShopifyAPI

# --- Sayfa Kurulumu ve Kontroller ---
st.set_page_config(page_title="Metafield Yönetimi", layout="wide")

if not st.session_state.get("authentication_status"):
    st.error("Bu sayfaya erişmek için lütfen giriş yapın.")
    st.stop()

# --- Arayüz ---
st.markdown("<h1>🛠️ Metafield Kurulum Aracı</h1>", unsafe_allow_html=True)
st.markdown("<p>Bu araç, koleksiyon sıralaması için gerekli olan ürün metafield tanımını API aracılığıyla kesin olarak oluşturur.</p>", unsafe_allow_html=True)

st.warning(
    "**ÖNEMLİ:** Bu işlemi yapmadan önce, Shopify Admin panelinizden `custom_sort.total_stock` "
    "adıyla daha önce oluşturduğunuz metafield tanımını sildiğinizden emin olun."
)

st.info(
    "Aşağıdaki butona tıkladığınızda, uygulamanız Shopify mağazanıza bağlanacak ve 'Sıralanabilir' (Sortable) "
    "yeteneği aktif edilmiş bir `custom_sort.total_stock` metafield tanımı oluşturacaktır."
)

if st.button("🚀 Stok Sıralama Metafield Tanımını API ile Oluştur", type="primary", use_container_width=True):
    if st.session_state.get('shopify_status') != 'connected':
        st.error("Shopify bağlantısı kurulu değil. Lütfen Ayarlar sayfasını kontrol edin.")
    else:
        try:
            shopify_api = ShopifyAPI(st.session_state.shopify_store, st.session_state.shopify_token)
            with st.spinner("API ile metafield tanımı oluşturuluyor..."):
                result = shopify_api.create_product_sortable_metafield_definition()

            if result.get('success'):
                st.success(f"İşlem Başarılı! Sonuç: {result.get('message')}")
                st.balloons()
                st.markdown("---")
                st.info(
                    "Şimdi **10 dakika kadar bekleyip**, sıralamak istediğiniz koleksiyonun sayfasına giderek 'Sırala' "
                    "menüsünü kontrol edebilirsiniz. 'Toplam Stok Siralamasi' seçeneği artık görünür olmalıdır."
                )
            else:
                st.error(f"İşlem Başarısız! Hata: {result.get('message')}")
        except Exception as e:
            st.error(f"Beklenmedik bir hata oluştu: {e}")