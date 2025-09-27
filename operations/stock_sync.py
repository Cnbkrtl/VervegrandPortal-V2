# operations/stock_sync.py - 10-Worker için optimize edilmiş

import logging
import time
from utils import get_variant_color, get_variant_size, get_apparel_sort_key
import json 

def sync_stock_and_variants(shopify_api, product_gid, sentos_product):
    """10-worker sistemi için optimize edilmiş stok ve varyant sync"""
    changes = []
    logging.info(f"Ürün {product_gid} için varyantlar ve stoklar senkronize ediliyor...")
    
    ex_vars = _get_shopify_variants(shopify_api, product_gid)
    ex_skus = {str(v.get('inventoryItem',{}).get('sku','')).strip() for v in ex_vars if v.get('inventoryItem',{}).get('sku')}
    s_vars = sentos_product.get('variants', []) or [sentos_product]
    
    new_vars = [v for v in s_vars if str(v.get('sku','')).strip() not in ex_skus]
    if new_vars:
        msg = f"{len(new_vars)} yeni varyant eklendi."
        changes.append(msg)
        _add_variants_bulk(shopify_api, product_gid, new_vars, sentos_product)
        time.sleep(1)  # 10-worker için daha kısa bekleme
    
    # Stok güncelleme - 10-worker için optimize edilmiş
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
    """Ürüne ait mevcut varyantları çeker - 10-worker için cache-aware"""
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

def _prepare_inventory_adjustments(sentos_variants, shopify_variants):
    """10-worker için optimize edilmiş stok hazırlama"""
    sku_map = {
        str(v.get('inventoryItem', {}).get('sku', '')).strip(): v.get('inventoryItem', {}).get('id') 
        for v in shopify_variants 
        if v.get('inventoryItem', {}).get('sku')
    }
    
    adjustments = []
    for v in sentos_variants:
        sku = str(v.get('sku', '')).strip()
        if sku and (inventory_item_id := sku_map.get(sku)):
            # Stok hesaplama optimizasyonu
            qty = sum(s.get('stock', 0) for s in v.get('stocks', []) if isinstance(s, dict) and s.get('stock'))
            if qty >= 0:  # Negatif stok kontrolü
                adjustments.append({
                    "inventoryItemId": inventory_item_id, 
                    "availableQuantity": int(qty)
                })
    return adjustments

def _adjust_inventory_bulk(shopify_api, adjustments):
    """10-worker için optimize edilmiş bulk inventory güncelleme"""
    if not adjustments: 
        return
    
    try:
        location_id = shopify_api.get_default_location_id()
        
        # 2024-10 API - Doğru bulk inventory mutation
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
        
        # Batch halinde işle (10-worker için optimize)
        batch_size = 50  # Shopify limitleri için
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
                    logging.info(f"✅ Batch {i//batch_size + 1}: {len(set_quantities)} varyant stoğu güncellendi")
            
            # 10-worker için kısa bekleme
            if i + batch_size < len(adjustments):
                time.sleep(0.5)
                
    except Exception as e:
        logging.error(f"Bulk stok güncelleme sırasında hata: {e}")

def _add_variants_bulk(shopify_api, product_gid, new_variants, main_product):
    """10-worker için optimize edilmiş bulk varyant ekleme"""
    if not new_variants:
        return
        
    # Batch halinde işle
    batch_size = 50
    
    for batch_start in range(0, len(new_variants), batch_size):
        batch = new_variants[batch_start:batch_start + batch_size]
        
        variants_input = []
        for v in batch:
            variant_input = {
                "price": "0.00",
                "inventoryItem": {
                    "tracked": True,
                    "sku": v.get('sku', '')
                }
            }
            
            if barcode := v.get('barcode'):
                variant_input['barcode'] = barcode
                
            # Variant seçeneklerini hazırla
            options = []
            if color := get_variant_color(v):
                options.append(color)
            if size := get_variant_size(v):
                options.append(size)
                
            if options:
                # Product options'larını al
                product_options = _get_product_options(shopify_api, product_gid)
                option_values = []
    
                for i, option_value in enumerate(options):
                    if i < len(product_options):
                        option_values.append({
                            "optionId": product_options[i].get('id'),
                            "name": option_value
                        })
    
                if option_values:
                    variant_input['optionValues'] = option_values
                
            variants_input.append(variant_input)

        # 2024-10 API bulk mutation
        bulk_mutation = """
        mutation productVariantsBulkCreate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
            productVariantsBulkCreate(productId: $productId, variants: $variants) {
                productVariants {
                    id
                    inventoryItem {
                        id
                        sku
                    }
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        try:
            result = shopify_api.execute_graphql(bulk_mutation, {
                "productId": product_gid,
                "variants": variants_input
            })
            
            created_variants = result.get('productVariantsBulkCreate', {}).get('productVariants', [])
            errors = result.get('productVariantsBulkCreate', {}).get('userErrors', [])
            
            if errors:
                logging.error(f"Varyant batch {batch_start//batch_size + 1} ekleme hataları: {errors}")
            else:
                logging.info(f"✅ Batch {batch_start//batch_size + 1}: {len(created_variants)} varyant başarıyla eklendi")
                
            # Varyantları aktif konuma getir
            if created_variants:
                _activate_variants_at_location(shopify_api, created_variants)
                
            # 10-worker için kısa bekleme
            if batch_start + batch_size < len(new_variants):
                time.sleep(0.5)
                
        except Exception as e:
            logging.error(f"Bulk varyant batch {batch_start//batch_size + 1} ekleme hatası: {e}")

def _get_product_options(shopify_api, product_gid):
    """Product'ın options'larını al"""
    query = """
    query getProductOptions($id: ID!) {
        product(id: $id) {
            options { id name }
        }
    }
    """
    try:
        result = shopify_api.execute_graphql(query, {"id": product_gid})
        return result.get('product', {}).get('options', [])
    except Exception as e:
        logging.error(f"Product options alınamadı: {e}")
        return []            

def _activate_variants_at_location(shopify_api, variants):
    """10-worker için optimize edilmiş inventory aktivasyonu"""
    inventory_item_ids = [v['inventoryItem']['id'] for v in variants if v.get('inventoryItem', {}).get('id')]
    if not inventory_item_ids:
        return
        
    try:
        location_id = shopify_api.get_default_location_id()
        
        activation_mutation = """
        mutation inventoryBulkToggleActivation($inventoryItemUpdates: [InventoryBulkToggleActivationInput!]!) {
            inventoryBulkToggleActivation(inventoryItemUpdates: $inventoryItemUpdates) {
                inventoryLevels { id }
                userErrors { field message }
            }
        }
        """
        
        updates = [
            {
                "inventoryItemId": item_id,
                "locationId": location_id,
                "activate": True
            }
            for item_id in inventory_item_ids
        ]
        
        shopify_api.execute_graphql(activation_mutation, {"inventoryItemUpdates": updates})
        logging.info(f"✅ {len(inventory_item_ids)} varyant inventory aktivasyonu tamamlandı")
        
    except Exception as e:
        logging.error(f"Inventory aktivasyon hatası: {e}")