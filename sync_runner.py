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
    # Ana ürün SKU'suna göre ara
    if sku := sentos_product.get('sku', '').strip():
        if product := shopify_api.product_cache.get(f"sku:{sku}"): 
            return product
    
    # Ürün başlığına göre ara (ikincil yöntem)
    if name := sentos_product.get('name', '').strip():
        if product := shopify_api.product_cache.get(f"title:{name}"): 
            return product
            
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
    """Shopify'da yeni bir ürün oluşturur - Basitleştirilmiş versiyon"""
    product_name = sentos_product.get('name', 'Bilinmeyen Ürün')
    logging.info(f"Yeni ürün oluşturuluyor (API 2024-10 Uyumlu): {product_name}")
    
    changes = []
    patch_shopify_api(shopify_api)

    try:
        # Varyant bilgilerini analiz et
        variants = sentos_product.get('variants', [])
        
        # Option values'ları topla
        color_values = set()
        size_values = set()
        
        for variant in variants:
            if color := get_variant_color(variant):
                color_values.add(color)
            if size := get_variant_size(variant):
                size_values.add(size)
        
        # ProductSet ile ürün + options + variants tek seferde oluştur
        product_options = []
        if color_values:
            product_options.append({
                "name": "Renk",
                "values": [{"name": color} for color in color_values]
            })
        if size_values:
            product_options.append({
                "name": "Beden", 
                "values": [{"name": size} for size in size_values]
            })
        
        # Variants hazırla
        variants_input = []
        for variant in variants:
            price_str = str(variant.get('price', '0.00')).replace(',', '.')
            
            variant_data = {
            "price": price_str,
            "inventoryItem": {
                "tracked": True,
                "sku": variant.get('sku', '')
            },
            # Bu satırları ekleyin:
            "inventoryManagement": "SHOPIFY",
            "inventoryPolicy": "DENY"
        }
            
            if barcode := variant.get('barcode'):
                variant_data['barcode'] = barcode
            
            # Option values
            option_values = []
            if color := get_variant_color(variant):
                option_values.append({"optionName": "Renk", "name": color})
            if size := get_variant_size(variant):
                option_values.append({"optionName": "Beden", "name": size})
                
            if option_values:
                variant_data['optionValues'] = option_values
            
            variants_input.append(variant_data)
        
        # ProductSet mutation - tek seferde her şeyi oluştur
        product_set_mutation = """
        mutation productSet($synchronous: Boolean!, $input: ProductSetInput!) {
            productSet(synchronous: $synchronous, input: $input) {
                product {
                    id
                    title
                    status
                }
                userErrors { field message }
            }
        }
        """
        
        product_set_input = {
            "title": product_name,
            "vendor": sentos_product.get('vendor', 'Vervegrand'),
            "productType": str(sentos_product.get('category', '')),
            "descriptionHtml": sentos_product.get('description_detail') or sentos_product.get('description', ''),
            "status": "ACTIVE",
            "productOptions": product_options,
            "variants": variants_input
        }
        
        result = shopify_api.execute_graphql(product_set_mutation, {
            "synchronous": True,
            "input": product_set_input
        })
        
        if errors := result.get('productSet', {}).get('userErrors', []):
            raise Exception(f"ProductSet hatası: {errors}")
            
        product = result.get('productSet', {}).get('product', {})
        product_gid = product.get('id')
        
        if not product_gid:
            raise Exception("Ürün oluşturuldu ancak ID alınamadı.")
        
        changes.append(f"✅ Ürün '{product_name}' tek seferde oluşturuldu (options + variants)")
        
        # Sadece medya sync yap
        if sentos_product.get('id'):
            try:
                media_changes = media_sync.sync_media(shopify_api, sentos_api, product_gid, sentos_product, set_alt_text=True)
                changes.extend(media_changes)
            except Exception as e:
                logging.error(f"Medya sync hatası: {e}")
                changes.append(f"⚠️ Medya sync hatası: {e}")

        if product_gid:
            _fix_inventory_tracking(shopify_api, product_gid)
            changes.append("Inventory tracking düzeltildi")        
        
        logging.info(f"✅ Yeni ürün '{product_name}' başarıyla oluşturuldu.")
        return changes
        
    except Exception as e:
        error_msg = f"'{product_name}' oluşturulurken kritik hata: {e}"
        logging.error(error_msg)
        traceback.print_exc()
        return [f"❌ {error_msg}"]
    
def _fix_inventory_tracking(shopify_api, product_gid):
    """Oluşturulan ürünün inventory tracking'ini düzelt"""
    try:
        # Ürünün variant'larını al
        variants_query = """
        query getProductVariants($id: ID!) {
            product(id: $id) {
                variants(first: 100) {
                    edges {
                        node {
                            id
                            inventoryItem { id }
                        }
                    }
                }
            }
        }
        """
        
        result = shopify_api.execute_graphql(variants_query, {"id": product_gid})
        variants = result.get('product', {}).get('variants', {}).get('edges', [])
        
        # Her variant için inventory tracking'i aktive et
        for variant_edge in variants:
            variant = variant_edge.get('node', {})
            inventory_item_id = variant.get('inventoryItem', {}).get('id')
            
            if inventory_item_id:
                # Inventory Item'ı güncelle
                update_mutation = """
                mutation inventoryItemUpdate($id: ID!, $input: InventoryItemUpdateInput!) {
                    inventoryItemUpdate(id: $id, input: $input) {
                        inventoryItem { id tracked }
                        userErrors { field message }
                    }
                }
                """
                
                shopify_api.execute_graphql(update_mutation, {
                    "id": inventory_item_id,
                    "input": {"tracked": True}
                })
                
                logging.info(f"Inventory tracking aktive edildi: {inventory_item_id}")
                
        # Location'da inventory level'larını ayarla
        location_id = shopify_api.get_default_location_id()
        
        for variant_edge in variants:
            variant = variant_edge.get('node', {})
            inventory_item_id = variant.get('inventoryItem', {}).get('id')
            
            if inventory_item_id:
                # Inventory level'ını set et
                set_mutation = """
                mutation inventorySetOnHandQuantities($input: InventorySetOnHandQuantitiesInput!) {
                    inventorySetOnHandQuantities(input: $input) {
                        inventoryAdjustmentGroup { id }
                        userErrors { field message }
                    }
                }
                """
                
                shopify_api.execute_graphql(set_mutation, {
                    "input": {
                        "reason": "correction",
                        "setQuantities": [{
                            "inventoryItemId": inventory_item_id,
                            "locationId": location_id,
                            "quantity": 0  # Başlangıç stok
                        }]
                    }
                })
        
        logging.info("Inventory tracking ve levels düzeltildi")
        
    except Exception as e:
        logging.error(f"Inventory tracking düzeltme hatası: {e}")    
    
def _prepare_inventory_adjustments_simple(sentos_variants, shopify_variants):
    """Sadece stok seviyelerini güncellemek için basit adjustment hazırlar"""
    sku_map = {
        str(v.get('inventoryItem', {}).get('sku', '')).strip(): v.get('inventoryItem', {}).get('id') 
        for v in shopify_variants 
        if v.get('inventoryItem', {}).get('sku')
    }
    
    adjustments = []
    for v in sentos_variants:
        sku = str(v.get('sku', '')).strip()
        if sku and (inventory_item_id := sku_map.get(sku)):
            qty = sum(s.get('stock', 0) for s in v.get('stocks', []) if isinstance(s, dict) and s.get('stock'))
            if qty >= 0:
                adjustments.append({
                    "inventoryItemId": inventory_item_id, 
                    "availableQuantity": int(qty)
                })
    return adjustments

def _adjust_inventory_bulk_simple(shopify_api, adjustments):
    """Basit bulk inventory güncelleme"""
    if not adjustments:
        return
        
    try:
        location_id = shopify_api.get_default_location_id()
        
        mutation = """
        mutation inventorySetOnHandQuantities($input: InventorySetOnHandQuantitiesInput!) {
            inventorySetOnHandQuantities(input: $input) {
                inventoryAdjustmentGroup { id }
                userErrors { field, message, code }
            }
        }
        """
        
        set_quantities = []
        for adj in adjustments:
            set_quantities.append({
                "inventoryItemId": adj["inventoryItemId"],
                "locationId": location_id,
                "quantity": adj["availableQuantity"]
            })
        
        variables = {
            "input": {
                "reason": "correction",
                "setQuantities": set_quantities
            }
        }
        
        result = shopify_api.execute_graphql(mutation, variables)
        
        if errors := result.get('inventorySetOnHandQuantities', {}).get('userErrors', []):
            logging.error(f"Stok güncellemesi hatası: {errors}")
        else:
            logging.info(f"Stok seviyeleri başarıyla güncellendi")
            
    except Exception as e:
        logging.error(f"Stok güncellemesi sırasında hata: {e}")    


def _get_shopify_variants(shopify_api, product_gid):
    """Ürüne ait mevcut varyantları çeker"""
    query = """
    query getProductVariants($id: ID!) {
        product(id: $id) {
            variants(first: 250) {
                edges {
                    node {
                        id
                        inventoryItem {
                            id
                            sku
                        }
                        selectedOptions {
                            name
                            value
                        }
                    }
                }
            }
        }
    }
    """
    
    try:
        data = shopify_api.execute_graphql(query, {"id": product_gid})
        return [e['node'] for e in data.get("product", {}).get("variants", {}).get("edges", [])]
    except Exception as e:
        logging.error(f"Varyant bilgileri alınırken hata: {e}")
        return []  

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
    start_time = time.monotonic()
    stats = {'total': 0, 'created': 0, 'updated': 0, 'failed': 0, 'skipped': 0, 'processed': 0}
    details = []
    lock = threading.Lock()
    try:
        shopify_api = ShopifyAPI(shopify_config['store_url'], shopify_config['access_token'])
        sentos_api = SentosAPI(sentos_config['api_url'], sentos_config['api_key'], sentos_config['api_secret'], sentos_config.get('cookie'))
        
        shopify_api.load_all_products_for_cache(progress_callback)
        sentos_products = sentos_api.get_all_products(progress_callback)
        
        if test_mode: sentos_products = sentos_products[:20]

        products_to_process = sentos_products
        if find_missing_only:
            logging.info(f"Toplam {len(sentos_products)} Sentos ürünü bulundu. Eksikler için filtreleme başlıyor...")
            products_to_process = [p for p in sentos_products if not _find_shopify_product(shopify_api, p)]
            # --- YENİ TEŞHİS SATIRI ---
            logging.info(f"Filtreleme sonrası OLUŞTURULACAK ÜRÜN SAYISI: {len(products_to_process)}")
        
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