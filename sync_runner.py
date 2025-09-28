# sync_runner.py (Fiyat ve Varyant Mantığı Düzeltilmiş Sürüm)

import logging
import threading
import time
import json
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback

from connectors.shopify_api import ShopifyAPI
from connectors.sentos_api import SentosAPI
from operations import core_sync, media_sync, stock_sync
from utils import get_apparel_sort_key, get_variant_color, get_variant_size

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def _find_shopify_product(shopify_api, sentos_product):
    if sku := sentos_product.get('sku', '').strip():
        if product := shopify_api.product_cache.get(f"sku:{sku}"): return product
    if name := sentos_product.get('name', '').strip():
        if product := shopify_api.product_cache.get(f"title:{name}"): return product
    return None

def _update_product(shopify_api, sentos_api, sentos_product, existing_product, sync_mode):
    product_name = sentos_product.get('name', 'Bilinmeyen Ürün') 
    shopify_gid = existing_product['gid']
    logging.info(f"Mevcut ürün güncelleniyor: '{product_name}' (GID: {shopify_gid}) | Mod: {sync_mode}")
    all_changes = []
    
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

def _calculate_price(main_product):
    """'shopify_sync' dosyasından alınan fiyat hesaplama mantığı."""
    try:
        # Öncelikli olarak prices->shopify->sale_price veya list_price deneniyor
        if prices := main_product.get('prices', {}).get('shopify', {}):
            for key in ['sale_price', 'list_price']:
                if val_str := prices.get(key, '0'):
                    price = float(str(val_str).replace(',', '.'))
                    if price > 0: return f"{price:.2f}"
        # Eğer yukarıdaki yapı yoksa, ana üründeki sale_price deneniyor
        if main_price_str := main_product.get('sale_price', '0'):
             price = float(str(main_price_str).replace(',', '.'))
             return f"{price:.2f}"
    except (ValueError, TypeError, AttributeError):
        pass # Hata durumunda varsayılan fiyata düş
    return "0.00"


def _create_product(shopify_api, sentos_api, sentos_product):
    product_name = sentos_product.get('name', 'Bilinmeyen Ürün').strip()
    logging.info(f"Yeni ürün oluşturuluyor ('İki Adımlı Strateji' ile): {product_name}")
    changes = []
    try:
        sentos_variants = sentos_product.get('variants', []) or [sentos_product]
        
        # Ana üründen fiyatı hesapla
        product_price = _calculate_price(sentos_product)

        has_color_option = any(get_variant_color(v) for v in sentos_variants)
        has_size_option = any(get_variant_size(v) for v in sentos_variants)
        
        product_input = {
            "title": product_name,
            "descriptionHtml": sentos_product.get('description_detail') or sentos_product.get('description', ''),
            "vendor": sentos_product.get('vendor', 'Vervegrand'),
            "productType": str(sentos_product.get('category', '')),
            "status": "DRAFT",
        }

        product_options = []
        if has_color_option:
            colors = sorted(list(set(get_variant_color(v) for v in sentos_variants if get_variant_color(v))))
            product_options.append({"name": "Renk", "values": [{"name": c} for c in colors]})
        if has_size_option:
            sizes = sorted(list(set(get_variant_size(v) for v in sentos_variants if get_variant_size(v))), key=get_apparel_sort_key)
            product_options.append({"name": "Beden", "values": [{"name": s} for s in sizes]})
        if product_options:
            product_input["productOptions"] = product_options

        create_q = "mutation productCreate($input: ProductInput!) { productCreate(input: $input) { product { id } userErrors { field message } } }"
        created_product_data = shopify_api.execute_graphql(create_q, {'input': product_input}).get('productCreate', {})
        
        if not created_product_data.get('product'):
            errors = created_product_data.get('userErrors', [])
            raise Exception(f"Ürün iskeleti oluşturulamadı: {errors}")
        
        product_gid = created_product_data['product']['id']
        changes.append(f"Ana ürün '{product_name}' DRAFT olarak oluşturuldu.")
        logging.info(f"Ürün iskeleti oluşturuldu (GID: {product_gid}).")

        variants_input = []
        for v in sentos_variants:
            option_values = []
            if has_color_option:
                option_values.append({"optionName": "Renk", "name": get_variant_color(v) or "Tek Renk"})
            if has_size_option:
                option_values.append({"optionName": "Beden", "name": get_variant_size(v) or "Tek Beden"})
            
            variants_input.append({
                "price": product_price,  # DÜZELTME: Fiyat artık dinamik olarak atanıyor.
                "barcode": v.get('barcode'),
                "optionValues": option_values,
                "inventoryItem": {
                    "tracked": True,
                    "sku": v.get('sku', '')
                }
            })

        bulk_q = """
        mutation productVariantsBulkCreate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
            productVariantsBulkCreate(
                productId: $productId, 
                variants: $variants, 
                strategy: REMOVE_STANDALONE_VARIANT
            ) {
                productVariants { id sku inventoryItem { id } }
                userErrors { field message }
            }
        }"""
        created_vars_data = shopify_api.execute_graphql(bulk_q, {'productId': product_gid, 'variants': variants_input}).get('productVariantsBulkCreate', {})
        
        if errors := created_vars_data.get('userErrors', []):
            raise Exception(f"Varyantlar oluşturulamadı: {errors}")

        created_variants = created_vars_data.get('productVariants', [])
        changes.append(f"{len(created_variants)} varyant eklendi.")
        logging.info(f"{len(created_variants)} varyant 'REMOVE_STANDALONE_VARIANT' stratejisi ile oluşturuldu.")

        if created_variants:
            stock_sync._activate_variants_at_location(shopify_api, created_variants)
            adjustments = stock_sync._prepare_inventory_adjustments(sentos_variants, created_variants)
            if adjustments:
                changes.append(f"{len(adjustments)} varyantın stoğu güncellendi.")
                stock_sync._adjust_inventory_bulk(shopify_api, adjustments)
        
        changes.extend(media_sync.sync_media(shopify_api, sentos_api, product_gid, sentos_product, set_alt_text=True))
        
        activate_q = "mutation productUpdate($input: ProductUpdateInput!) { productUpdate(input: $input) { product { id status } userErrors { field message } } }"
        activate_result = shopify_api.execute_graphql(activate_q, {"input": {"id": product_gid, "status": "ACTIVE"}})

        if activate_result.get('productUpdate', {}).get('userErrors', []):
             logging.warning(f"Ürün aktive edilirken hata oluştu: {activate_result['productUpdate']['userErrors']}")
             changes.append("Ürün aktive edilemedi, taslak olarak kaldı.")
        else:
            changes.append("Ürün durumu 'Aktif' olarak ayarlandı.")
            logging.info(f"Ürün '{product_name}' başarıyla oluşturuldu ve aktive edildi.")

        return changes

    except Exception as e:
        logging.error(f"Ürün oluşturma hatası: {e}\n{traceback.format_exc()}")
        raise

def _process_single_product(shopify_api, sentos_api, sentos_product, sync_mode, progress_callback, stats, details, lock):
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
                status, status_icon = 'skipped', "⏭️"
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
            products_to_process = [p for p in sentos_products if not _find_shopify_product(shopify_api, p)]
            logging.info(f"{len(products_to_process)} adet eksik ürün bulundu.")
        
        stats['total'] = len(products_to_process)

        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="SyncWorker") as executor:
            futures = [executor.submit(_process_single_product, shopify_api, sentos_api, p, sync_mode, progress_callback, stats, details, lock) for p in products_to_process]
            for future in as_completed(futures):
                if stop_event.is_set(): 
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                processed, total = stats['processed'], stats['total']
                progress = 55 + int((processed / total) * 45) if total > 0 else 100
                progress_callback({'progress': progress, 'message': f"İşlenen: {processed}/{total}", 'stats': stats.copy()})

        duration = time.monotonic() - start_time
        results = {'stats': stats, 'details': details, 'duration': str(timedelta(seconds=duration))}
        progress_callback({'status': 'done', 'results': results})

    except Exception as e:
        logging.critical(f"Senkronizasyon görevi kritik bir hata oluştu: {e}\n{traceback.format_exc()}")
        progress_callback({'status': 'error', 'message': str(e)})

def sync_products_from_sentos_api(store_url, access_token, sentos_api_url, sentos_api_key, sentos_api_secret, sentos_cookie, test_mode, progress_callback, stop_event, max_workers=2, sync_mode="Tam Senkronizasyon (Tümünü Oluştur ve Güncelle)"):
    shopify_config = {'store_url': store_url, 'access_token': access_token}
    sentos_config = {'api_url': sentos_api_url, 'api_key': sentos_api_key, 'api_secret': sentos_api_secret, 'cookie': sentos_cookie}
    _run_core_sync_logic(shopify_config, sentos_config, sync_mode, max_workers, test_mode, progress_callback, stop_event)

def sync_missing_products_only(store_url, access_token, sentos_api_url, sentos_api_key, sentos_api_secret, sentos_cookie, test_mode, progress_callback, stop_event, max_workers=2):
    shopify_config = {'store_url': store_url, 'access_token': access_token}
    sentos_config = {'api_url': sentos_api_url, 'api_key': sentos_api_key, 'api_secret': sentos_api_secret, 'cookie': sentos_cookie}
    _run_core_sync_logic(shopify_config, sentos_config, "Sadece Eksikleri Oluştur", max_workers, test_mode, progress_callback, stop_event, find_missing_only=True)

def sync_single_product_by_sku(store_url, access_token, sentos_api_url, sentos_api_key, sentos_api_secret, sentos_cookie, sku):
    try:
        shopify_api = ShopifyAPI(store_url, access_token)
        sentos_api = SentosAPI(sentos_api_url, sentos_api_key, sentos_api_secret, sentos_cookie)
        
        # Media sync için patch
        patch_shopify_api(shopify_api)
        
        # --- YENİ EKLENEN/DEĞİŞTİRİLEN KISIM BAŞLANGICI ---

        # Adım 1: Önce tam SKU ile Sentos'ta ürünü ara.
        sentos_product = sentos_api.get_product_by_sku(sku)

        # Adım 2: Bulunamazsa, SKU'dan ana model kodunu türetip tekrar ara.
        if not sentos_product:
            logging.warning(f"'{sku}' tam SKU'su ile Sentos'ta ürün bulunamadı. Ana model kodu türetilip tekrar aranacak.")
            # Genellikle ana model kodu, varyant bilgisinden (örn: -S-SIYAH) önceki kısımdır.
            base_sku = sku.split('-')[0].strip()
            
            # Eğer türetilen SKU, orijinal SKU ile aynıysa veya boşsa, tekrar arama yapmaya gerek yok.
            if base_sku and base_sku != sku:
                logging.info(f"Türetilen ana model kodu: '{base_sku}'. Bu kod ile tekrar arama yapılıyor...")
                sentos_product = sentos_api.get_product_by_sku(base_sku)
            
        # Adım 3: Hala bulunamadıysa hata ver.
        if not sentos_product:
            return {'success': False, 'message': f"'{sku}' veya türetilmiş ana SKU ile Sentos'ta ürün bulunamadı."}
        
        # --- YENİ EKLENEN/DEĞİŞTİRİLEN KISIM SONU ---

        shopify_api.load_all_products_for_cache()
        existing_product = _find_shopify_product(shopify_api, sentos_product)
        
        if not existing_product:
            # Sentos'ta ürün var ama Shopify'da yoksa, bu daha bilgilendirici bir mesajdır.
            return {'success': False, 'message': f"Ürün Sentos'ta bulundu ancak '{sentos_product.get('name', sku)}' adıyla Shopify'da eşleşen bir ürün bulunamadı. Lütfen önce tam senkronizasyon çalıştırın."}
        
        changes_made = _update_product(shopify_api, sentos_api, sentos_product, existing_product, "Tam Senkronizasyon (Tümünü Oluştur ve Güncelle)")
        product_name = sentos_product.get('name', sku)
        return {'success': True, 'product_name': product_name, 'changes': changes_made}
        
    except Exception as e:
        logging.error(f"Tekil ürün {sku} senkronizasyonunda hata: {e}\n{traceback.format_exc()}")
        return {'success': False, 'message': str(e)}