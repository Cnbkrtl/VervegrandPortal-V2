# operations/core_sync.py - 10-Worker için optimize edilmiş

import logging

def sync_details(shopify_api, product_gid, sentos_product):
    """10-worker için optimize edilmiş ürün detay güncelleme"""
    changes = []
    
    try:
        input_data = {
            "id": product_gid, 
            "title": sentos_product.get('name', '').strip(), 
            "descriptionHtml": sentos_product.get('description_detail') or sentos_product.get('description', '')
        }
        
        query = """
        mutation productUpdate($input: ProductInput!) {
            productUpdate(input: $input) {
                product { id }
                userErrors { field message }
            }
        }
        """
        
        result = shopify_api.execute_graphql(query, {'input': input_data})
        
        if errors := result.get('productUpdate', {}).get('userErrors', []):
            logging.error(f"Ürün detay güncelleme hataları: {errors}")
            changes.append(f"Hata: {errors[0].get('message', 'Bilinmeyen hata')}")
        else:
            changes.append("Başlık ve açıklama güncellendi.")
            logging.info(f"Ürün {product_gid} için temel detaylar güncellendi.")
            
    except Exception as e:
        error_msg = f"Ürün detay güncelleme hatası: {e}"
        logging.error(error_msg)
        changes.append(error_msg)
    
    return changes

def sync_product_type(shopify_api, product_gid, sentos_product):
    """10-worker için optimize edilmiş kategori güncelleme"""
    changes = []
    
    try:
        if category := sentos_product.get('category'):
            input_data = {"id": product_gid, "productType": str(category)}
            
            query = """
            mutation productUpdate($input: ProductInput!) {
                productUpdate(input: $input) {
                    product { id }
                    userErrors { field message }
                }
            }
            """
            
            result = shopify_api.execute_graphql(query, {'input': input_data})
            
            if errors := result.get('productUpdate', {}).get('userErrors', []):
                logging.error(f"Kategori güncelleme hataları: {errors}")
                changes.append(f"Kategori güncelleme hatası: {errors[0].get('message', 'Bilinmeyen hata')}")
            else:
                changes.append(f"Kategori '{category}' olarak ayarlandı.")
                logging.info(f"Ürün {product_gid} için kategori '{category}' olarak ayarlandı.")
                
    except Exception as e:
        error_msg = f"Kategori güncelleme hatası: {e}"
        logging.error(error_msg)
        changes.append(error_msg)
    
    return changes