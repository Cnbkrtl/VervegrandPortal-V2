# operations/core_sync.py (ProductUpdateInput Hatası Düzeltilmiş Sürüm)

import logging

def sync_details(shopify_api, product_gid, sentos_product):
    """Ürün başlığı ve açıklamasını doğru input tipiyle günceller."""
    changes = []
    
    try:
        # DÜZELTME: GraphQL sorgusundaki input tipi 'ProductUpdateInput!' olarak güncellendi.
        query = """
        mutation productUpdate($input: ProductUpdateInput!) {
            productUpdate(input: $input) {
                product { id }
                userErrors { field message }
            }
        }
        """
        
        input_data = {
            "id": product_gid, 
            "title": sentos_product.get('name', '').strip(), 
            "descriptionHtml": sentos_product.get('description_detail') or sentos_product.get('description', '')
        }
        
        result = shopify_api.execute_graphql(query, {'input': input_data})
        
        if errors := result.get('productUpdate', {}).get('userErrors', []):
            logging.error(f"Ürün detay güncelleme hataları: {errors}")
            changes.append(f"Hata: {errors[0].get('message', 'Bilinmeyen güncelleme hatası')}")
        else:
            changes.append("Başlık ve açıklama güncellendi.")
            logging.info(f"Ürün {product_gid} için temel detaylar güncellendi.")
            
    except Exception as e:
        error_msg = f"Ürün detay güncelleme sırasında kritik hata: {e}"
        logging.error(error_msg)
        changes.append(error_msg)
    
    return changes

def sync_product_type(shopify_api, product_gid, sentos_product):
    """Ürün kategorisini (productType) doğru input tipiyle günceller."""
    changes = []
    
    try:
        if category := sentos_product.get('category'):
            # DÜZELTME: GraphQL sorgusundaki input tipi 'ProductUpdateInput!' olarak güncellendi.
            query = """
            mutation productUpdate($input: ProductUpdateInput!) {
                productUpdate(input: $input) {
                    product { id }
                    userErrors { field message }
                }
            }
            """
            
            input_data = {"id": product_gid, "productType": str(category)}
            
            result = shopify_api.execute_graphql(query, {'input': input_data})
            
            if errors := result.get('productUpdate', {}).get('userErrors', []):
                logging.error(f"Kategori güncelleme hataları: {errors}")
                changes.append(f"Kategori güncelleme hatası: {errors[0].get('message', 'Bilinmeyen güncelleme hatası')}")
            else:
                changes.append(f"Kategori '{category}' olarak ayarlandı.")
                logging.info(f"Ürün {product_gid} için kategori '{category}' olarak ayarlandı.")
                
    except Exception as e:
        error_msg = f"Kategori güncelleme sırasında kritik hata: {e}"
        logging.error(error_msg)
        changes.append(error_msg)
    
    return changes