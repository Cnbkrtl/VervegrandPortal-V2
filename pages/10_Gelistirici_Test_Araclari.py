# pages/10_Gelistirici_Test_Araclari.py

import streamlit as st
from connectors.shopify_api import ShopifyAPI

st.set_page_config(page_title="Geliştirici Test Araçları", layout="wide")

if not st.session_state.get("authentication_status"):
    st.error("Bu sayfaya erişmek için lütfen giriş yapın.")
    st.stop()

st.markdown("<h1>🧪 Geliştirici Test Araçları</h1>", unsafe_allow_html=True)
st.markdown(
    "Bu sayfa, standart yöntemler başarısız olduğunda, farklı API versiyonları ve oluşturma metotlarını "
    "deneyerek metafield tanımını oluşturmaya zorlamak için kullanılır."
)

st.warning(
    "**BAŞLAMADAN ÖNCE:** Shopify Admin panelinizden `custom_sort.total_stock` "
    "adıyla daha önce oluşturduğunuz metafield tanımını sildiğinizden emin olun."
)

st.subheader("Test Parametrelerini Seçin")

# 1. API Versiyonu Seçimi
api_version = st.selectbox(
    "1. Test Edilecek API Versiyonu:",
    ['2024-10', '2024-07', '2024-04', '2024-01'],
    help="Shopify'ın farklı API versiyonları. En yeniden eskiye doğru deneyin."
)

# 2. Oluşturma Metodu Seçimi
creation_method = st.selectbox(
    "2. Test Edilecek Oluşturma Metodu:",
    ['modern', 'legacy', 'hybrid'],
    format_func=lambda x: {
        'modern': 'Modern Yöntem (capabilities objesi)',
        'legacy': 'Eski Yöntem (ana seviye `sortable`)',
        'hybrid': 'Hibrit Yöntem (ikisi bir arada)'
    }[x],
    help="Farklı sorgu yapıları. 'Modern' ile başlayın, sonra diğerlerini deneyin."
)

if st.button(f"🚀 Testi Başlat ({api_version} - {creation_method})", type="primary", use_container_width=True):
    if st.session_state.get('shopify_status') != 'connected':
        st.error("Shopify bağlantısı kurulu değil.")
    else:
        try:
            # Seçilen API versiyonu ile ShopifyAPI'yi başlat
            shopify_api = ShopifyAPI(
                st.session_state.shopify_store, 
                st.session_state.shopify_token,
                api_version=api_version
            )
            
            with st.spinner(f"'{api_version}' API versiyonu ve '{creation_method}' metodu ile tanım oluşturuluyor..."):
                result = shopify_api.create_product_sortable_metafield_definition(method=creation_method)

            if result.get('success'):
                st.success(f"İŞLEM BAŞARILI! Sonuç: {result.get('message')}")
                st.balloons()
                st.info(
                    "Şimdi 10 dakika bekleyip koleksiyon sayfasını kontrol edin. "
                    "Eğer seçenek görünmüyorsa, farklı bir kombinasyon deneyin."
                )
            else:
                st.error(f"İŞLEM BAŞARISIZ! Hata: {result.get('message')}")

        except Exception as e:
            st.error(f"Beklenmedik bir hata oluştu: {e}")