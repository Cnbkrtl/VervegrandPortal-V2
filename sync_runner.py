# sync_runner.py (Düzeltilmiş Sürüm)

import sys
import os
import logging
import threading
import time
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback
import json

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
    """
    DÜZELTME: Shopify 2024-10 API için tamamen yeniden yazılmış, modernize edilmiş ürün oluşturma fonksiyonu.
    Tüm sorunları (varyant, stok, aktivasyon, taslak) çözer.
    """
    product_name = sentos_product.get('name', 'Bilinmeyen Ürün')
    logging.info(f"=== YENİ ÜRÜN OLUŞTURULUYOR: {product_name} ===")
    
    changes = []
    patch_shopify_api(shopify_api)

    try:
        sentos_variants = sentos_product.get('variants', [])
        if not sentos_variants: # Varyantsız ürünler için ana ürünü varyant gibi kullan
            sentos_variants = [sentos_product]

        # ADIM 1: VARYANTLARI VE SEÇENEKLERİ HAZIRLA
        variants_input = []
        color_set = set()
        size_set = set()
        
        for v in sentos_variants:
            color = get_variant_color(v)
            size = get_variant_size(v)
            options = []
            
            if color:
                color_set.add(color)
                options.append(color)
            if size:
                size_set.add(size)
                options.append(size)

            # Stok hesaplama
            quantity = sum(s.get('stock', 0) for s in v.get('stocks', []) if isinstance(s, dict) and s.get('stock'))

            variants_input.append({
                "price": str(v.get('price', "0.00")),
                "sku": v.get('sku', ''),
                "barcode": v.get('barcode'),
                "options": options,
                "inventoryItem": { "tracked": True },
                # Geçici stok bilgisi
                "quantity": int(quantity)
            })

        # ADIM 2: ANA ÜRÜN BİLGİLERİNİ OLUŞTUR
        product_input = {
            "title": product_name.strip(),
            "vendor": sentos_product.get('vendor', 'Vervegrand'),
            "productType": str(sentos_product.get('category', '')),
            "descriptionHtml": sentos_product.get('description_detail') or sentos_product.get('description', ''),
            "status": "DRAFT", # Önce taslak olarak oluştur
            "variants": variants_input
        }
        
        # Seçenekleri (Options) ekle
        options_input = []
        if color_set: options_input.append({"name": "Renk", "values": sorted(list(color_set))})
        if size_set: options_input.append({"name": "Beden", "values": sorted(list(size_set), key=get_apparel_sort_key)})
        
        if options_input:
             product_input["options"] = options_input

        # ADIM 3: ÜRÜNÜ TEK SEFERDE OLUŞTUR
        create_mutation = """
        mutation productCreate($input: ProductInput!) {
          productCreate(input: $input) {
            product {
              id
              title
              variants(first: 100) {
                nodes {
                  id
                  sku
                  inventoryItem { id }
                }
              }
            }
            userErrors { field message }
          }
        }
        """
        
        result = shopify_api.execute_graphql(create_mutation, {"input": product_input})
        
        if errors := result.get('productCreate', {}).get('userErrors', []):
            raise Exception(f"Ürün oluşturma hatası: {json.dumps(errors)}")
        
        product = result.get('productCreate', {}).get('product', {})
        product_gid = product.get('id')
        
        if not product_gid:
            raise Exception("Ürün oluşturulamadı - GID alınamadı")
        
        logging.info(f"✅ Ana ürün ve {len(variants_input)} varyant taslak olarak oluşturuldu (GID: {product_gid})")
        changes.append(f"Ana ürün '{product_name}' ve {len(variants_input)} varyant oluşturuldu.")
        
        created_variants = product.get('variants', {}).get('nodes', [])

        # ADIM 4: ENVANTERİ AKTİVE ET VE STOKLARI AYARLA
        location_id = shopify_api.get_default_location_id()
        inventory_item_ids_to_activate = [v['inventoryItem']['id'] for v in created_variants if v.get('inventoryItem')]
        
        # Envanteri aktive et
        if inventory_item_ids_to_activate:
            stock_sync._activate_variants_at_location(shopify_api, created_variants)
            changes.append(f"{len(inventory_item_ids_to_activate)} varyant envanter takibine eklendi.")
        
        # Stokları ayarla
        inventory_adjustments = []
        sku_to_inventory_id = {v['sku']: v['inventoryItem']['id'] for v in created_variants if v.get('sku') and v.get('inventoryItem')}

        for v_input in variants_input:
            if (sku := v_input.get('sku')) and (inventory_item_id := sku_to_inventory_id.get(sku)):
                inventory_adjustments.append({
                    "inventoryItemId": inventory_item_id,
                    "availableQuantity": v_input['quantity']
                })
        
        if inventory_adjustments:
            stock_sync._adjust_inventory_bulk(shopify_api, inventory_adjustments)
            logging.info(f"✅ {len(inventory_adjustments)} varyantın stoğu ayarlandı.")
            changes.append(f"{len(inventory_adjustments)} varyant stoğu güncellendi.")

        # ADIM 5: MEDYA EKLE
        time.sleep(2) # Varyantların işlenmesi için kısa bir bekleme
        if sentos_product.get('id'):
            media_changes = media_sync.sync_media(
                shopify_api, sentos_api, product_gid, sentos_product, set_alt_text=True
            )
            changes.extend(media_changes)

        # ADIM 6: ÜRÜNÜ AKTİF YAP
        activate_mutation = """
        mutation productUpdate($input: ProductUpdateInput!) {
            productUpdate(input: $input) {
                product { id status }
                userErrors { field message }
            }
        }
        """
        # DÜZELTME: 'ProductUpdateInput' tipi kullanılıyor
        activate_input = {"id": product_gid, "status": "ACTIVE"}
        
        activate_result = shopify_api.execute_graphql(activate_mutation, {"input": activate_input})
        
        if not activate_result.get('productUpdate', {}).get('userErrors', []):
            logging.info(f"✅ Ürün başarıyla AKTİF duruma getirildi.")
            changes.append("Ürün durumu 'Aktif' olarak ayarlandı.")
        else:
            logging.error(f"Ürün aktive edilemedi: {activate_result.get('productUpdate', {}).get('userErrors')}")
            changes.append("Hata: Ürün aktive edilemedi.")
            
        return changes
        
    except Exception as e:
        error_msg = f"HATA: '{product_name}' oluşturulurken kritik bir hata oluştu: {e}"
        logging.error(error_msg)
        traceback.print_exc()
        # Hata mesajını daha anlaşılır kıl
        return [f"Kritik Hata: {e}"]


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
            # DÜZELTME: Hata mesajı kontrolü
            if changes_made and "Kritik Hata" in changes_made[0]:
                raise Exception(changes_made[0])

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
        # DÜZELTME: Hata mesajı formatı iyileştirildi
        error_message_str = str(e).replace('<', '&lt;').replace('>', '&gt;')
        error_html = f"""
        <div style='border-bottom: 1px solid #444; padding-bottom: 8px; margin-bottom: 8px; color: #f48a94;'>
            <strong>❌ Hata:</strong> {name} (SKU: {sku})
            <ul style='margin-top: 5px; margin-bottom: 0; padding-left: 20px;'>
                <li><small>GraphQL Error: {error_message_str}</small></li>
            </ul>
        </div>"""
        progress_callback({'log_detail': error_html})

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
                    eta_seconds = (total - processed) / max(rate, 0.1)
                else:
                    rate, eta_seconds = 0, 0
                
                progress_callback({
                    'progress': progress, 
                    'message': f"İşleniyor: {processed}/{total} | Hız: {rate:.2f} ü/sn | ETA: {int(eta_seconds)}s",
                    'stats': {**stats.copy()}
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
             # DÜZELTME: Eğer ürün Shopify'da yoksa oluşturmayı dene
            logging.info(f"Shopify'da ürün bulunamadı, '{sku}' SKU'lu ürün oluşturulacak.")
            changes_made = _create_product(shopify_api, sentos_api, sentos_product)
            if changes_made and "Hata" in changes_made[0]:
                 raise Exception(changes_made[0])
            product_name = sentos_product.get('name', sku)
            return {'success': True, 'product_name': product_name, 'changes': changes_made}

        changes_made = _update_product(shopify_api, sentos_api, sentos_product, existing_product, "Tam Senkronizasyon (Tümünü Oluştur ve Güncelle)")
        product_name = sentos_product.get('name', sku)
        return {'success': True, 'product_name': product_name, 'changes': changes_made}
        
    except Exception as e:
        logging.error(f"Tekil ürün {sku} senkronizasyonunda hata: {e}\n{traceback.format_exc()}")
        return {'success': False, 'message': str(e)}