# sync_runner.py (Düzeltilmiş Sürüm)

import sys
import os
import logging
import threading
import time
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback

from connectors.shopify_api import ShopifyAPI
from connectors.sentos_api import SentosAPI
from operations import core_sync, media_sync, stock_sync
from operations.media_sync import patch_shopify_api
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import get_apparel_sort_key, get_variant_color, get_variant_size

# --- Loglama Konfigürasyonu ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# --- İÇ MANTIK FONKSİYONLARI ---

def _find_shopify_product(shopify_api, sentos_product):
    """Sentos ürününü Shopify'da SKU veya başlığa göre arar."""
    if sku := sentos_product.get('sku', '').strip():
        if product := shopify_api.product_cache.get(f"sku:{sku}"): return product
    if name := sentos_product.get('name', '').strip():
        if product := shopify_api.product_cache.get(f"title:{name}"): return product
    return None

def _update_product(shopify_api, sentos_api, sentos_product, existing_product, sync_mode):
    """Mevcut bir ürünü belirtilen moda göre günceller."""
    product_name = sentos_product.get('name', 'Bilinmeyen Ürün') 
    shopify_gid = existing_product['gid']
    logging.info(f"Mevcut ürün güncelleniyor: '{product_name}' (GID: {shopify_gid}) | Mod: {sync_mode}")
    all_changes = []
    
    # Media sync için ShopifyAPI'yi patch et
    patch_shopify_api(shopify_api)
    
    if sync_mode in ["Tam Senkronizasyon (Tümünü Oluştur ve Güncelle)", "Sadece Açıklamalar"]:
         all_changes.extend(core_sync.sync_details(shopify_api, shopify_gid, sentos_product))
         all_changes.extend(core_sync.sync_product_type(shopify_api, shopify_gid, sentos_product))

    if sync_mode in ["Tam Senkronizasyon (Tümünü Oluştur ve Güncelle)", "Sadece Stok ve Varyantlar"]:
        all_changes.extend(stock_sync.sync_stock_and_variants(shopify_api, shopify_gid, sentos_product))

    if sync_mode in ["Tam Senkronizasyon (Tümünü Oluştur ve Güncelle)", "Sadece Resimler", "SEO Alt Metinli Resimler"]:
        set_alt = sync_mode in ["Tam Senkronizasyon (Tümünü Oluştur ve Güncelle)", "SEO Alt Metinli Resimler"]
        all_changes.extend(media_sync.sync_media(shopify_api, sentos_api, shopify_gid, sentos_product, set_alt_text=set_alt))
        
    logging.info(f"✅ Ürün '{product_name}' başarıyla güncellendi.")
    return all_changes

def _create_product(shopify_api, sentos_api, sentos_product):
    """Düzeltilmiş ürün oluşturma fonksiyonu - fiyat ve varyantlarla"""
    product_name = sentos_product.get('name', 'Bilinmeyen Ürün')
    logging.info(f"=== CREATING PRODUCT: {product_name} ===")
    
    changes = []
    patch_shopify_api(shopify_api)

    try:
        # Varyantları ve fiyat bilgisini al
        variants = sentos_product.get('variants', [])
        
        # Fiyat bilgisini al (ilk varyanttan veya ana üründen)
        product_price = "0.00"
        if variants and len(variants) > 0:
            # İlk varyantın fiyatını kullan
            first_variant = variants[0]
            if 'price' in first_variant:
                product_price = str(first_variant.get('price', 0))
        elif 'price' in sentos_product:
            # Ana ürün fiyatını kullan
            product_price = str(sentos_product.get('price', 0))
        
        logging.info(f"DEBUG - Product price: {product_price}")
        
        # Options'ları hazırla
        product_options = []
        color_values = set()
        size_values = set()
        
        if variants:
            for v in variants:
                color = get_variant_color(v)
                size = get_variant_size(v)
                if color:
                    color_values.add(color)
                if size:
                    size_values.add(size)
            
            if color_values:
                product_options.append({
                    "name": "Renk",
                    "values": list(color_values)
                })
            if size_values:
                product_options.append({
                    "name": "Beden", 
                    "values": list(size_values)
                })
        
        logging.info(f"DEBUG - Product options with values: {product_options}")
        
        # Eğer varyant yoksa veya tek varyantsa, basit ürün oluştur
        if not variants or len(variants) == 1:
            # Basit ürün (tek varyant)
            single_variant = variants[0] if variants else sentos_product
            
            product_input = {
                "title": product_name,
                "vendor": sentos_product.get('vendor', 'Vervegrand'),
                "productType": str(sentos_product.get('category', '')),
                "descriptionHtml": sentos_product.get('description_detail') or sentos_product.get('description', ''),
                "status": "DRAFT",
                "variants": [{
                    "price": product_price,
                    "sku": single_variant.get('sku', ''),
                    "barcode": single_variant.get('barcode', ''),
                    "inventoryItem": {
                        "tracked": True,
                        "sku": single_variant.get('sku', '')
                    }
                }]
            }
        else:
            # Çoklu varyantlı ürün - önce options ile oluştur
            product_input = {
                "title": product_name,
                "vendor": sentos_product.get('vendor', 'Vervegrand'),
                "productType": str(sentos_product.get('category', '')),
                "descriptionHtml": sentos_product.get('description_detail') or sentos_product.get('description', ''),
                "status": "DRAFT"
            }
            
            # Options'ları ekle (Shopify 2024-10 formatında)
            if product_options:
                product_input["productOptions"] = [opt["name"] for opt in product_options]
        
        logging.info(f"DEBUG - Final product input: {product_input}")
        
        # Ürünü oluştur
        create_mutation = """
        mutation productCreate($input: ProductInput!) {
            productCreate(input: $input) {
                product { 
                    id 
                    title
                    status
                    options { 
                        id 
                        name 
                        values
                    }
                    variants(first: 1) {
                        edges {
                            node {
                                id
                                price
                                sku
                            }
                        }
                    }
                }
                userErrors { field, message }
            }
        }
        """
        
        result = shopify_api.execute_graphql(create_mutation, {"input": product_input})
        
        if errors := result.get('productCreate', {}).get('userErrors', []):
            logging.error(f"Product creation errors: {errors}")
            raise Exception(f"Ürün oluşturma hatası: {errors}")
            
        product = result.get('productCreate', {}).get('product', {})
        product_gid = product.get('id')
        
        if not product_gid:
            raise Exception("Ürün oluşturulamadı - ID alınamadı")
        
        logging.info(f"Product created with GID: {product_gid}")
        changes.append(f"Ana ürün '{product_name}' oluşturuldu (GID: {product_gid})")
        
        # Çoklu varyantlar varsa bunları ekle
        if variants and len(variants) > 1:
            logging.info(f"Adding {len(variants)} variants with prices...")
            
            # Her varyant için fiyat bilgisini de ekle
            for variant in variants:
                variant_price = variant.get('price', product_price)
                if variant_price:
                    variant['price'] = str(variant_price)
            
            # stock_sync modülündeki fonksiyonu kullan ama fiyatları da gönder
            stock_changes = stock_sync.sync_stock_and_variants_with_prices(
                shopify_api, 
                product_gid, 
                sentos_product
            )
            changes.extend(stock_changes)
        elif variants and len(variants) == 1:
            # Tek varyant varsa sadece stoğu güncelle
            logging.info("Updating inventory for single variant...")
            stock_changes = stock_sync.sync_stock_and_variants(
                shopify_api,
                product_gid,
                sentos_product
            )
            changes.extend(stock_changes)
        
        # Medya ekle
        if sentos_product.get('id'):
            try:
                logging.info("Adding media...")
                media_changes = media_sync.sync_media(
                    shopify_api, 
                    sentos_api, 
                    product_gid, 
                    sentos_product, 
                    set_alt_text=True
                )
                changes.extend(media_changes)
            except Exception as e:
                logging.error(f"Media sync error: {e}")
                changes.append(f"Medya sync hatası: {e}")
        
        # Ürünü aktif yap
        logging.info("Activating product...")
        activate_mutation = """
        mutation productUpdate($input: ProductInput!) {
            productUpdate(input: $input) {
                product { 
                    id 
                    status
                    variants(first: 100) {
                        edges {
                            node {
                                id
                                price
                                sku
                                inventoryQuantity
                            }
                        }
                    }
                }
                userErrors { field, message }
            }
        }
        """
        
        activate_result = shopify_api.execute_graphql(activate_mutation, {
            "input": {"id": product_gid, "status": "ACTIVE"}
        })
        
        if activate_errors := activate_result.get('productUpdate', {}).get('userErrors', []):
            logging.error(f"Activation errors: {activate_errors}")
            changes.append(f"Aktivasyon hatası: {activate_errors}")
        else:
            activated_product = activate_result.get('productUpdate', {}).get('product', {})
            variant_count = len(activated_product.get('variants', {}).get('edges', []))
            logging.info(f"Product activated with {variant_count} variants")
            changes.append(f"Ürün aktif hale getirildi ({variant_count} varyant).")
        
        logging.info(f"=== PRODUCT CREATION COMPLETED: {product_name} ===")
        return changes
        
    except Exception as e:
        error_msg = f"CREATION FAILED FOR {product_name}: {e}"
        logging.error(error_msg)
        traceback.print_exc()
        return [f"HATA: {error_msg}"]

def _process_single_product(shopify_api, sentos_api, sentos_product, sync_mode, progress_callback, stats, details, lock):
    """10-worker için optimize edilmiş tek ürün işleme"""
    name = sentos_product.get('name', 'Bilinmeyen Ürün')
    sku = sentos_product.get('sku', 'SKU Yok')
    log_entry = {'name': name, 'sku': sku}
    
    try:
        if not name.strip():
            with lock: stats['skipped'] += 1
            return
        
        existing_product = _find_shopify_product(shopify_api, sentos_product)
        changes_made = []

        if existing_product:
            if "Sadece Eksik" not in sync_mode:
                changes_made = _update_product(shopify_api, sentos_api, sentos_product, existing_product, sync_mode)
                status, status_icon = 'updated', "🔄"
                with lock: stats['updated'] += 1
            else:
                status, status_icon = 'skipped', "⭐"
                with lock: stats['skipped'] += 1

        elif "Tam Senkronizasyon" in sync_mode or "Sadece Eksik" in sync_mode:
            changes_made = _create_product(shopify_api, sentos_api, sentos_product)
            status, status_icon = 'created', "✅"
            with lock: stats['created'] += 1
        else:
            with lock: stats['skipped'] += 1
            return
        
        changes_html = "".join([f'<li><small>{change}</small></li>' for change in changes_made])
        log_html = f"""
        <div style='border-bottom: 1px solid #444; padding-bottom: 8px; margin-bottom: 8px;'>
            <strong>{status_icon} {status.capitalize()}:</strong> {name} (SKU: {sku})
            <ul style='margin-top: 5px; margin-bottom: 0; padding-left: 20px;'>
                {changes_html if changes_made else "<li><small>Değişiklik bulunamadı.</small></li>"}
            </ul>
        </div>
        """
        progress_callback({'log_detail': log_html})
        with lock: details.append(log_entry)

    except Exception as e:
        error_message = f"❌ Hata: {name} (SKU: {sku}) - {e}"
        progress_callback({'log_detail': f"<div style='color: #f48a94;'>{error_message}</div>"})
        with lock: 
            stats['failed'] += 1
            log_entry.update({'status': 'failed', 'reason': str(e)})
            details.append(log_entry)
    finally:
        with lock: stats['processed'] += 1

def _run_core_sync_logic(shopify_config, sentos_config, sync_mode, max_workers, test_mode, progress_callback, stop_event, find_missing_only=False):
    """10-worker için optimize edilmiş ana sync mantığı"""
    start_time = time.monotonic()
    stats = {'total': 0, 'created': 0, 'updated': 0, 'failed': 0, 'skipped': 0, 'processed': 0}
    details = []
    lock = threading.Lock()

    try:
        shopify_api = ShopifyAPI(shopify_config['store_url'], shopify_config['access_token'])
        sentos_api = SentosAPI(sentos_config['api_url'], sentos_config['api_key'], sentos_config['api_secret'], sentos_config.get('cookie'))
        
        shopify_api.load_all_products_for_cache(progress_callback)
        sentos_products = sentos_api.get_all_products(progress_callback)
        
        if test_mode: 
            sentos_products = sentos_products[:20]

        products_to_process = sentos_products
        if find_missing_only:
            products_to_process = [p for p in sentos_products if not _find_shopify_product(shopify_api, p)]
            logging.info(f"{len(products_to_process)} adet eksik ürün bulundu.")
        
        stats['total'] = len(products_to_process)

        # 10-worker ile paralel işlem
        with ThreadPoolExecutor(max_workers=min(max_workers, 10), thread_name_prefix="SyncWorker") as executor:
            futures = [
                executor.submit(_process_single_product, shopify_api, sentos_api, p, sync_mode, progress_callback, stats, details, lock) 
                for p in products_to_process
            ]
            
            for future in as_completed(futures):
                if stop_event.is_set(): 
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                    
                processed, total = stats['processed'], stats['total']
                progress = 55 + int((processed / total) * 45) if total > 0 else 100
                
                # Gerçek zamanlı istatistikler
                elapsed_time = time.monotonic() - start_time
                if elapsed_time > 0:
                    rate = processed / elapsed_time
                    eta_minutes = (total - processed) / max(rate, 0.1) / 60
                else:
                    rate, eta_minutes = 0, 0
                
                progress_callback({
                    'progress': progress, 
                    'message': f"10-Worker: {processed}/{total}",
                    'stats': {**stats.copy(), 'rate': rate, 'eta': eta_minutes}
                })

        duration = time.monotonic() - start_time
        results = {'stats': stats, 'details': details, 'duration': str(timedelta(seconds=duration))}
        progress_callback({'status': 'done', 'results': results})

    except Exception as e:
        logging.critical(f"10-Worker sync kritik hatası: {e}\n{traceback.format_exc()}")
        progress_callback({'status': 'error', 'message': str(e)})

# --- ARAYÜZ (UI) İÇİN DIŞARIYA AÇIK FONKSİYONLAR ---

def sync_products_from_sentos_api(store_url, access_token, sentos_api_url, sentos_api_key, sentos_api_secret, sentos_cookie, test_mode, progress_callback, stop_event, max_workers=8, sync_mode="Tam Senkronizasyon (Tümünü Oluştur ve Güncelle)"):
    shopify_config = {'store_url': store_url, 'access_token': access_token}
    sentos_config = {'api_url': sentos_api_url, 'api_key': sentos_api_key, 'api_secret': sentos_api_secret, 'cookie': sentos_cookie}
    _run_core_sync_logic(shopify_config, sentos_config, sync_mode, max_workers, test_mode, progress_callback, stop_event)

def sync_missing_products_only(store_url, access_token, sentos_api_url, sentos_api_key, sentos_api_secret, sentos_cookie, test_mode, progress_callback, stop_event, max_workers=8):
    shopify_config = {'store_url': store_url, 'access_token': access_token}
    sentos_config = {'api_url': sentos_api_url, 'api_key': sentos_api_key, 'api_secret': sentos_api_secret, 'cookie': sentos_cookie}
    _run_core_sync_logic(shopify_config, sentos_config, "Sadece Eksikleri Oluştur", max_workers, test_mode, progress_callback, stop_event, find_missing_only=True)

def sync_single_product_by_sku(store_url, access_token, sentos_api_url, sentos_api_key, sentos_api_secret, sentos_cookie, sku):
    try:
        shopify_api = ShopifyAPI(store_url, access_token)
        sentos_api = SentosAPI(sentos_api_url, sentos_api_key, sentos_api_secret, sentos_cookie)
        
        # Media sync için patch
        patch_shopify_api(shopify_api)
        
        sentos_product = sentos_api.get_product_by_sku(sku)
        if not sentos_product:
            return {'success': False, 'message': f"'{sku}' SKU'su ile Sentos'ta ürün bulunamadı."}
        
        shopify_api.load_all_products_for_cache()
        existing_product = _find_shopify_product(shopify_api, sentos_product)
        
        if not existing_product:
            return {'success': False, 'message': f"'{sku}' SKU'su ile Shopify'da eşleşen ürün bulunamadı."}
        
        changes_made = _update_product(shopify_api, sentos_api, sentos_product, existing_product, "Tam Senkronizasyon (Tümünü Oluştur ve Güncelle)")
        product_name = sentos_product.get('name', sku)
        return {'success': True, 'product_name': product_name, 'changes': changes_made}
        
    except Exception as e:
        logging.error(f"Tekil ürün {sku} senkronizasyonunda hata: {e}\n{traceback.format_exc()}")
        return {'success': False, 'message': str(e)}