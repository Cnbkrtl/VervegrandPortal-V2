# operations/stock_sync.py - 10-Worker için optimize edilmiş

import logging
import time
from utils import get_variant_color, get_variant_size, get_apparel_sort_key
import json 

def sync_stock_and_variants(shopify_api, product_gid, sentos_product):
    """API 2024-10 uyumlu stok ve varyant sync"""
    changes = []
    logging.info(f"Ürün {product_gid} için varyantlar ve stoklar senkronize ediliyor...")
    
    ex_vars = _get_shopify_variants(shopify_api, product_gid)
    ex_skus = {str(v.get('inventoryItem',{}).get('sku','')).strip() for v in ex_vars if v.get('inventoryItem',{}).get('sku')}
    s_vars = sentos_product.get('variants', []) or [sentos_product]
    
    new_vars = [v for v in s_vars if str(v.get('sku','')).strip() not in ex_skus]
    if new_vars:
        msg = f"{len(new_vars)} yeni varyant eklendi."
        changes.append(msg)
        _add_variants_individual(shopify_api, product_gid, new_vars)  # Yeni fonksiyon
        time.sleep(1)
    
    # Stok güncelleme
    all_now_variants = _get_shopify_variants(shopify_api, product_gid)
    if adjustments := _prepare_inventory_adjustments(s_vars, all_now_variants):
        msg = f"{len(adjustments)} varyantın stok seviyesi güncellendi."
        changes.append(msg)
        _adjust_inventory_bulk(shopify_api, adjustments)
        
    if not new_vars and not adjustments:
        changes.append("Stok ve varyantlar kontrol edildi (Değişiklik yok).")
        
    logging.info(f"Ürün {product_gid} için varyant ve stok senkronizasyonu tamamlandı.")
    return changes

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
    
def _add_variants_individual(shopify_api, product_gid, new_variants):
    """Düzeltilmiş optionValues ile bulk create"""
    if not new_variants:
        return
        
    logging.info(f"{len(new_variants)} yeni varyant optionValues ile ekleniyor...")
    success_count = 0
    
    # Product options'ları kontrol et ve al
    product_options = _ensure_and_get_product_options(shopify_api, product_gid, new_variants)
    
    if not product_options:
        logging.error("Product options alınamadı veya eklenemedi")
        return
    
    # Default "Title" option varsa kaldır
    valid_options = [opt for opt in product_options if opt.get('name', '').lower() != 'title']
    
    if not valid_options:
        logging.error("Geçerli options bulunamadı")
        return
    
    logging.info(f"Kullanılacak options: {[opt.get('name') for opt in valid_options]}")
    
    # Variants input hazırla
    variants_input = []
    for variant in new_variants:
        price_str = str(variant.get('price', '0.00')).replace(',', '.')
        
        variant_input = {
            "price": price_str,
            "inventoryItem": { 
                "tracked": True,
                "sku": variant.get('sku', '')
            }
        }
        
        # Barcode ekle
        if barcode := variant.get('barcode'):
            variant_input['barcode'] = barcode
            
        # optionValues oluştur
        option_values = []
        
        color = get_variant_color(variant)
        size = get_variant_size(variant)
        
        for option in valid_options:
            option_id = option.get('id')
            option_name = option.get('name', '').lower()
            
            if 'renk' in option_name or 'color' in option_name:
                if color:
                    option_values.append({
                        "optionId": option_id,
                        "name": color
                    })
                else:
                    # Varsayılan değer
                    option_values.append({
                        "optionId": option_id,
                        "name": "Varsayılan"
                    })
            elif 'beden' in option_name or 'size' in option_name:
                if size:
                    option_values.append({
                        "optionId": option_id,
                        "name": size
                    })
                else:
                    # Varsayılan değer
                    option_values.append({
                        "optionId": option_id,
                        "name": "Varsayılan"
                    })
        
        if option_values:
            variant_input['optionValues'] = option_values
            
        variants_input.append(variant_input)
        
        # Debug log
        logging.info(f"Varyant {variant.get('sku')}: {option_values}")

    # Bulk create
    bulk_variant_mutation = """
    mutation productVariantsBulkCreate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
        productVariantsBulkCreate(productId: $productId, variants: $variants) {
            productVariants { 
                id
                inventoryItem { id sku }
                selectedOptions { name value }
            }
            userErrors { field, message }
        }
    }
    """
    
    try:
        result = shopify_api.execute_graphql(bulk_variant_mutation, {
            "productId": product_gid,
            "variants": variants_input
        })
        
        created_variants = result.get('productVariantsBulkCreate', {}).get('productVariants', [])
        errors = result.get('productVariantsBulkCreate', {}).get('userErrors', [])
        
        if errors:
            logging.error(f"Bulk varyant ekleme hataları: {errors}")
            # Debug: Input'u logla
            logging.error(f"Gönderilen variants input (ilk 3): {variants_input[:3]}")
        else:
            success_count = len(created_variants)
            logging.info(f"✅ {success_count} varyant başarıyla eklendi")
            
            # Created variants'ları logla
            for var in created_variants:
                selected_opts = var.get('selectedOptions', [])
                sku = var.get('inventoryItem', {}).get('sku', '')
                logging.info(f"Oluşturulan varyant {sku}: {selected_opts}")
            
            # Inventory activation
            for variant in created_variants:
                try:
                    inventory_item_id = variant.get('inventoryItem', {}).get('id')
                    if inventory_item_id:
                        _activate_single_variant_inventory(shopify_api, inventory_item_id)
                except Exception as e:
                    logging.warning(f"Inventory aktivasyon hatası: {e}")
            
    except Exception as e:
        logging.error(f"Bulk varyant ekleme hatası: {e}")
    
    logging.info(f"{success_count}/{len(new_variants)} varyant başarıyla eklendi.") 

def _ensure_and_get_product_options(shopify_api, product_gid, variants):
    """Product options'ları kontrol eder, gerekirse ekler ve option bilgilerini döner"""
    if not variants:
        return []
        
    try:
        # Hangi options gerekli
        has_color = any(get_variant_color(v) for v in variants)
        has_size = any(get_variant_size(v) for v in variants)
        
        if not (has_color or has_size):
            return []
            
        # Mevcut options'ları kontrol et
        check_query = """
        query checkProductOptions($id: ID!) {
            product(id: $id) {
                options { 
                    id 
                    name
                    values
                }
            }
        }
        """
        
        result = shopify_api.execute_graphql(check_query, {"id": product_gid})
        existing_options = result.get('product', {}).get('options', [])
        
        logging.info(f"Mevcut product options: {existing_options}")
        
        # Mevcut option isimlerini kontrol et
        existing_option_names = [opt.get('name', '').lower() for opt in existing_options]
        
        # Gerekli options'ları belirle
        needed_options = []
        if has_color and not any('renk' in name or 'color' in name for name in existing_option_names):
            needed_options.append("Renk")
        if has_size and not any('beden' in name or 'size' in name for name in existing_option_names):
            needed_options.append("Beden")
            
        logging.info(f"Eklenmesi gereken options: {needed_options}")
        
        if needed_options:
            # productSet mutation ile options ekle (daha güvenilir)
            success = _add_options_with_product_set(shopify_api, product_gid, needed_options, variants)
            
            if success:
                # Güncel options listesini al
                time.sleep(3)  # Options'ların işlenmesi için bekleme
                updated_result = shopify_api.execute_graphql(check_query, {"id": product_gid})
                updated_options = updated_result.get('product', {}).get('options', [])
                logging.info(f"Güncellenen product options: {updated_options}")
                return updated_options
            else:
                logging.error("Options eklenemedi, mevcut options ile devam ediliyor")
                return existing_options
            
        return existing_options
                
    except Exception as e:
        logging.error(f"Product options kontrol/ekleme hatası: {e}")
        return []

def _add_options_with_product_set(shopify_api, product_gid, needed_options, variants):
    """productSet mutation ile options ekler"""
    try:
        # Mevcut product bilgilerini al
        product_query = """
        query getProduct($id: ID!) {
            product(id: $id) {
                id
                title
                descriptionHtml
                vendor
                productType
                status
                options {
                    id
                    name
                    values
                }
            }
        }
        """
        
        product_result = shopify_api.execute_graphql(product_query, {"id": product_gid})
        current_product = product_result.get('product', {})
        
        if not current_product:
            logging.error("Product bilgisi alınamadı")
            return False
        
        # Mevcut options + yeni options
        current_options = current_product.get('options', [])
        product_options_input = []
        
        # Mevcut options'ları ekle
        for opt in current_options:
            if opt.get('name', '').lower() != 'title':  # Default Title option'ını atlama
                product_options_input.append({
                    "name": opt['name'],
                    "values": opt.get('values', [])
                })
        
        # Yeni options ekle ve değerlerini variants'lardan topla
        for option_name in needed_options:
            values = set()
            
            if option_name.lower() == 'renk':
                for v in variants:
                    if color := get_variant_color(v):
                        values.add(color)
            elif option_name.lower() == 'beden':
                for v in variants:
                    if size := get_variant_size(v):
                        values.add(size)
            
            if values:
                product_options_input.append({
                    "name": option_name,
                    "values": list(values)
                })
        
        logging.info(f"ProductSet ile eklenecek options: {product_options_input}")
        
        # productSet mutation
        product_set_mutation = """
        mutation productSet($synchronous: Boolean!, $input: ProductSetInput!) {
            productSet(synchronous: $synchronous, input: $input) {
                product {
                    id
                    options { id name values }
                }
                userErrors { field message }
            }
        }
        """
        
        product_set_input = {
            "id": product_gid,
            "title": current_product.get('title'),
            "descriptionHtml": current_product.get('descriptionHtml', ''),
            "vendor": current_product.get('vendor', ''),
            "productType": current_product.get('productType', ''),
            "status": current_product.get('status', 'ACTIVE'),
            "productOptions": product_options_input
        }
        
        result = shopify_api.execute_graphql(product_set_mutation, {
            "synchronous": True,
            "input": product_set_input
        })
        
        if errors := result.get('productSet', {}).get('userErrors', []):
            logging.error(f"ProductSet ile options ekleme hataları: {errors}")
            return False
        
        updated_product = result.get('productSet', {}).get('product', {})
        if updated_product:
            logging.info(f"ProductSet başarılı: {updated_product.get('options', [])}")
            return True
        
        return False
        
    except Exception as e:
        logging.error(f"ProductSet ile options ekleme hatası: {e}")
        return False

def _activate_single_variant_inventory(shopify_api, inventory_item_id):
    """Inventory aktivasyonu"""
    try:
        location_id = shopify_api.get_default_location_id()
        
        activation_mutation = """
        mutation inventoryActivate($inventoryItemId: ID!, $locationId: ID!) {
            inventoryActivate(inventoryItemId: $inventoryItemId, locationId: $locationId) {
                inventoryLevel { id }
                userErrors { field message }
            }
        }
        """
        
        shopify_api.execute_graphql(activation_mutation, {
            "inventoryItemId": inventory_item_id,
            "locationId": location_id
        })
            
    except Exception as e:
        logging.error(f"Inventory aktivasyon hatası: {e}")

def _prepare_inventory_adjustments(sentos_variants, shopify_variants):
    """Stok ayarlamaları hazırlar"""
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

def _adjust_inventory_bulk(shopify_api, adjustments):
    """Bulk inventory güncellemesi - API 2024-10 uyumlu"""
    if not adjustments: 
        return
    
    try:
        location_id = shopify_api.get_default_location_id()
        
        mutation = """
        mutation inventorySetOnHandQuantities($input: InventorySetOnHandQuantitiesInput!) {
            inventorySetOnHandQuantities(input: $input) {
                inventoryAdjustmentGroup {
                    id
                }
                userErrors {
                    field
                    message
                    code
                }
            }
        }
        """
        
        # Batch halinde işle
        batch_size = 50
        for i in range(0, len(adjustments), batch_size):
            batch = adjustments[i:i + batch_size]
            
            set_quantities = []
            for adj in batch:
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
                logging.error(f"Bulk stok güncelleme batch {i//batch_size + 1} hataları: {errors}")
            else:
                adjustment_group = result.get('inventorySetOnHandQuantities', {}).get('inventoryAdjustmentGroup')
                if adjustment_group:
                    logging.info(f"Batch {i//batch_size + 1}: {len(set_quantities)} varyant stoğu güncellendi")
            
            if i + batch_size < len(adjustments):
                time.sleep(0.5)
                
    except Exception as e:
        logging.error(f"Bulk stok güncelleme sırasında hata: {e}")

def _activate_single_variant_inventory(shopify_api, inventory_item_id):
    """Tek varyant için inventory aktivasyonu"""
    try:
        location_id = shopify_api.get_default_location_id()
        
        activation_mutation = """
        mutation inventoryActivate($inventoryItemId: ID!, $locationId: ID!) {
            inventoryActivate(inventoryItemId: $inventoryItemId, locationId: $locationId) {
                inventoryLevel { id }
                userErrors { field message }
            }
        }
        """
        
        result = shopify_api.execute_graphql(activation_mutation, {
            "inventoryItemId": inventory_item_id,
            "locationId": location_id
        })
        
        if errors := result.get('inventoryActivate', {}).get('userErrors', []):
            logging.warning(f"Inventory aktivasyon hatası: {errors}")
        else:
            logging.debug("Inventory başarıyla aktive edildi")
            
    except Exception as e:
        logging.error(f"Inventory aktivasyon hatası: {e}")