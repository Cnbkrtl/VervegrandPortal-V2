# config_manager.py

import streamlit as st

def load_all_user_keys(username):
    """
    Tüm API anahtarlarını Streamlit Secrets'tan yükler.
    Bu sürümde tüm sırlar tek bir yerde olduğu için kullanıcı adına gerek yoktur,
    ancak gelecekteki olası çok kullanıcılı senaryolar için argüman korunmuştur.
    """
    # secrets.toml dosyasındaki değerleri st.secrets üzerinden okuyoruz.
    # Eğer bir sır bulunamazsa, None döner.
    return {
        "shopify_store": st.secrets.get("SHOPIFY_STORE"),
        "shopify_token": st.secrets.get("SHOPIFY_TOKEN"),
        "sentos_api_url": st.secrets.get("SENTOS_API_URL"),
        "sentos_api_key": st.secrets.get("SENTOS_API_KEY"),
        "sentos_api_secret": st.secrets.get("SENTOS_API_SECRET"),
        "sentos_cookie": st.secrets.get("SENTOS_COOKIE"),
        "gcp_service_account_json": st.secrets.get("GCP_SERVICE_ACCOUNT_JSON")
    }

# Not: save_user_keys fonksiyonu artık gerekli değil çünkü sırlar Streamlit arayüzünden yönetilecek.
# Bu dosya, eski yapıyla uyumluluk için sadece yükleme fonksiyonunu içerir.