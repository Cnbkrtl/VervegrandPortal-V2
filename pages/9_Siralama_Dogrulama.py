# pages/8_Siralama_Dogrulama.py

import streamlit as st
import pandas as pd
from connectors.shopify_api import ShopifyAPI

st.set_page_config(page_title="Sıralama Doğrulama", layout="wide")

if not st.session_state.get("authentication_status"):
    st.error("Bu sayfaya erişmek için lütfen giriş yapın.")
    st.stop()

st.markdown("<h1>🔬 Sıralama Seçenekleri Doğrulama Aracı</h1>", unsafe_allow_html=True)
st.markdown(
    "Bu araç, bir koleksiyon için Shopify API'sinin hangi sıralama seçeneklerini tanıdığını doğrudan gösterir. "
    "Eğer metafield'ınız burada listeleniyorsa, kurulum başarılıdır ve sadece arayüzün güncellenmesi bekleniyordur."
)

st.info(
    "**Koleksiyon GID'sini Nasıl Bulurum?**\n\n"
    "1. Shopify Admin panelinde ilgili koleksiyonun sayfasına gidin.\n"
    "2. Tarayıcınızın adres çubuğundaki URL'nin sonuna bakın. `.../collections/` kısmından sonra gelen **sayısal ID**'yi kopyalayın.\n"
    "   (Örnek: `.../collections/447854641453` ise, ID `447854641453`'tür.)\n"
    "3. Aşağıdaki kutucuğa yapıştırın."
)

collection_numeric_id = st.text_input("Koleksiyonun Sayısal ID'sini Buraya Girin:", placeholder="Örn: 447854641453")

if st.button("🔍 Sıralama Seçeneklerini Sorgula", use_container_width=True):
    if not collection_numeric_id.isdigit():
        st.error("Lütfen sadece sayısal ID girin.")
    else:
        collection_gid = f"gid://shopify/Collection/{collection_numeric_id}"
        
        try:
            shopify_api = ShopifyAPI(st.session_state.shopify_store, st.session_state.shopify_token)
            with st.spinner(f"'{collection_gid}' için API'den sıralama anahtarları sorgulanıyor..."):
                result = shopify_api.get_collection_available_sort_keys(collection_gid)

            if result.get('success'):
                st.success("Sorgulama başarılı! API'nin tanıdığı sıralama anahtarları:")
                sort_keys = result.get('data', [])
                if sort_keys:
                    df = pd.DataFrame(sort_keys)
                    st.dataframe(df, use_container_width=True)

                    # Metafield'ın varlığını kontrol et
                    is_metafield_found = any('METAFIELD' in key['key'] for key in sort_keys)
                    if is_metafield_found:
                        st.balloons()
                        st.success(
                            "🎉 HARİKA HABER! API, metafield sıralama seçeneğini tanıyor. "
                            "Kurulumunuz %100 doğru. Sadece Shopify Admin arayüzünün güncellenmesini beklemeniz gerekiyor."
                        )
                    else:
                        st.warning(
                            "⚠️ Metafield sıralama anahtarı henüz API tarafından tanınmıyor. "
                            "Lütfen 24 saat kadar bekledikten sonra tekrar kontrol edin. "
                            "Bu süre sonunda hala görünmüyorsa, durumu Shopify Destek ekibine bildirmek gerekebilir."
                        )
                else:
                    st.warning("Bu koleksiyon için herhangi bir sıralama anahtarı bulunamadı.")
            else:
                st.error(f"Sorgulama başarısız! Hata: {result.get('message')}")

        except Exception as e:
            st.error(f"Beklenmedik bir hata oluştu: {e}")