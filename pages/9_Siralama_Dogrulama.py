# pages/9_Siralama_Dogrulama.py (DÜZELTILMIŞ)

import streamlit as st
import pandas as pd
from connectors.shopify_api import ShopifyAPI

st.set_page_config(page_title="Metafield Tanım Doğrulama", layout="wide")

if not st.session_state.get("authentication_status"):
    st.error("Bu sayfaya erişmek için lütfen giriş yapın.")
    st.stop()

st.markdown("<h1>🔬 Metafield Tanım Doğrulama Aracı</h1>", unsafe_allow_html=True)
st.markdown(
    "Bu araç, `custom_sort.total_stock` metafield tanımının Shopify'da mevcut olup olmadığını kontrol eder "
    "ve sortable özelliklerini doğrular."
)

st.info(
    "**Bu araç ne yapar?**\n\n"
    "1. Shopify'daki tüm PRODUCT metafield tanımlarını listeler\n"
    "2. `custom_sort.total_stock` tanımının mevcut olup olmadığını kontrol eder\n"
    "3. Metafield tanımının özelliklerini görüntüler\n"
    "4. Sortable özelliğinin aktif olup olmadığını gösterir"
)

if st.button("🔍 Metafield Tanımlarını Kontrol Et", use_container_width=True):
    try:
        shopify_api = ShopifyAPI(st.session_state.shopify_store, st.session_state.shopify_token)
        
        with st.spinner("Shopify'dan metafield tanımları sorgulanıyor..."):
            result = shopify_api.get_metafield_definitions()

        if result.get('success'):
            definitions = result.get('data', [])
            
            if definitions:
                st.success(f"Toplam {len(definitions)} metafield tanımı bulundu!")
                
                # Özel metafield'ımızı ara
                target_definition = None
                for definition in definitions:
                    if (definition.get('namespace') == 'custom_sort' and 
                        definition.get('key') == 'total_stock'):
                        target_definition = definition
                        break
                
                # Sonuçları göster
                if target_definition:
                    st.balloons()
                    st.success("🎉 HARİKA! `custom_sort.total_stock` metafield tanımı bulundu!")
                    
                    # Detayları göster
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("**Tanım Detayları:**")
                        st.write(f"- **Ad**: {target_definition.get('name', 'N/A')}")
                        st.write(f"- **Namespace**: {target_definition.get('namespace', 'N/A')}")
                        st.write(f"- **Key**: {target_definition.get('key', 'N/A')}")
                        st.write(f"- **Tip**: {target_definition.get('type', 'N/A')}")
                        
                    with col2:
                        st.write("**Özellikler:**")
                        st.write(f"- **Owner Type**: {target_definition.get('ownerType', 'N/A')}")
                        st.write(f"- **Açıklama**: {target_definition.get('description', 'Yok') or 'Yok'}")
                        
                        # Capabilities kontrolü
                        capabilities = target_definition.get('capabilities', {})
                        if capabilities:
                            st.write("**Yetenekler:**")
                            for capability, value in capabilities.items():
                                st.write(f"- **{capability}**: {value}")
                        else:
                            st.write("**Yetenekler**: Tanımlı değil")
                    
                    # JSON formatında tam veriyi göster
                    with st.expander("Tam JSON Verisi", expanded=False):
                        st.json(target_definition)
                        
                else:
                    st.warning("⚠️ `custom_sort.total_stock` metafield tanımı bulunamadı!")
                    st.info("Bu durum şunları gösterebilir:\n"
                           "- Metafield tanımı henüz oluşturulmamış\n"
                           "- Farklı bir namespace/key kombinasyonu kullanılmış\n"
                           "- API erişim yetkileri eksik")
                
                # Tüm tanımları tablo halinde göster
                with st.expander("Tüm Metafield Tanımları", expanded=False):
                    df = pd.DataFrame(definitions)
                    if not df.empty:
                        # Sütunları düzenle
                        display_columns = ['name', 'namespace', 'key', 'type', 'ownerType']
                        available_columns = [col for col in display_columns if col in df.columns]
                        if available_columns:
                            st.dataframe(df[available_columns], use_container_width=True)
                        else:
                            st.dataframe(df, use_container_width=True)
                    else:
                        st.write("Gösterilecek veri yok")
                        
            else:
                st.warning("Hiç metafield tanımı bulunamadı.")
        else:
            st.error(f"Sorgulama başarısız! Hata: {result.get('message')}")

    except Exception as e:
        st.error(f"Beklenmedik bir hata oluştu: {e}")

# Ek bilgi bölümü
with st.expander("📚 Metafield Sortable Özelliği Hakkında", expanded=False):
    st.markdown("""
    **Sortable Metafield Nasıl Çalışır?**
    
    1. **API Tanımı**: Metafield tanımı API aracılığıyla "sortable" özelliği ile oluşturulmalı
    2. **Shopify Admin**: Tanım oluşturulduktan sonra, Shopify Admin panelinde koleksiyon sıralama seçeneklerinde görünmesi 10-60 dakika sürebilir
    3. **Gecikme Normal**: Shopify'ın iç sistemlerinin senkronize olması zaman alır
    4. **Manuel Kontrol**: En kesin kontrol yöntemi Admin panelinden koleksiyon > Sırala menüsüne bakmaktır
    
    **Eğer metafield tanımı varsa ama Admin'de görünmüyorsa:**
    - 1-2 saat daha bekleyin
    - Tarayıcı cache'inizi temizleyin
    - Shopify Admin'i yeniden açın
    - Sorunu Shopify Destek'e bildirin
    """)