"""
API Yapı Analizi - Shopify ve Sentos API'larının gerçek yapılarını incele
"""

import requests
import json
from requests.auth import HTTPBasicAuth
import config_manager

def analyze_shopify_product():
    """Mevcut bir Shopify ürününün tam yapısını analiz et"""
    
    credentials = config_manager.load_all_keys()
    
    if not credentials:
        print("❌ Ayarlar bulunamadı!")
        return None
    
    headers = {
        'X-Shopify-Access-Token': credentials['shopify_token'],
        'Content-Type': 'application/json'
    }
    
    # GraphQL ile ilk ürünü al
    url = f"https://{credentials['shopify_store']}/admin/api/2024-10/graphql.json"
    
    query = """
    query getFirstProduct {
      products(first: 1) {
        edges {
          node {
            id
            title
            handle
            description
            status
            vendor
            productType
            createdAt
            updatedAt
            totalInventory
            tags
            variants(first: 50) {
              edges {
                node {
                  id
                  title
                  sku
                  inventoryQuantity
                  price
                  compareAtPrice
                  weight
                  weightUnit
                  barcode
                  position
                  selectedOptions {
                    name
                    value
                  }
                  inventoryItem {
                    id
                    tracked
                    requiresShipping
                  }
                }
              }
            }
            images(first: 50) {
              edges {
                node {
                  id
                  url
                  altText
                  width
                  height
                }
              }
            }
          }
        }
      }
    }
    """
    
    try:
        payload = {"query": query}
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            
            # GraphQL hata kontrolü
            if data.get('errors'):
                print(f"❌ GraphQL errors: {data['errors']}")
                return None
                
            products_data = data.get('data', {}).get('products', {})
            edges = products_data.get('edges', [])
            
            if edges:
                product = edges[0]['node']
                print("🔍 SHOPIFY ÜRÜN YAPISI (GraphQL):")
                print("=" * 80)
                print(json.dumps(product, indent=2, ensure_ascii=False))
                print("=" * 80)
                
                # Ana alanları listele
                print("\n📋 SHOPIFY ANA ALANLAR:")
                for key in product.keys():
                    value_type = type(product[key]).__name__
                    if isinstance(product[key], dict) and 'edges' in product[key]:
                        # GraphQL edge yapısı
                        edges = product[key]['edges']
                        print(f"  {key}: GraphQL Connection (count: {len(edges)})")
                    elif isinstance(product[key], list) and product[key]:
                        item_type = type(product[key][0]).__name__
                        print(f"  {key}: {value_type}[{item_type}] (count: {len(product[key])})")
                    else:
                        print(f"  {key}: {value_type}")
                
                # Variants yapısını detaylandır
                if product.get('variants', {}).get('edges'):
                    variant = product['variants']['edges'][0]['node']
                    print("\n🎯 SHOPIFY VARIANT YAPISI:")
                    for key in variant.keys():
                        value_type = type(variant[key]).__name__
                        if isinstance(variant[key], list) and variant[key]:
                            item_type = type(variant[key][0]).__name__
                            print(f"  {key}: {value_type}[{item_type}] (count: {len(variant[key])})")
                        else:
                            print(f"  {key}: {value_type}")
                
                return product
            else:
                print("❌ Shopify'da ürün bulunamadı!")
                return None
        else:
            print(f"❌ Shopify GraphQL API hatası: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Shopify analiz hatası: {str(e)}")
        return None

def analyze_sentos_product():
    """Sentos API'dan bir ürünün tam yapısını analiz et"""
    
    credentials = config_manager.load_all_keys()
    
    if not credentials:
        print("❌ Ayarlar bulunamadı!")
        return None
    
    auth = HTTPBasicAuth(credentials['sentos_api_key'], credentials['sentos_api_secret'])
    
    # İlk ürünü al
    url = f"{credentials['sentos_api_url']}/product?page=0&size=1"
    
    try:
        response = requests.get(url, auth=auth)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('data'):
                product = data['data'][0]
                print("🔍 SENTOS ÜRÜN YAPISI:")
                print("=" * 80)
                print(json.dumps(product, indent=2, ensure_ascii=False))
                print("=" * 80)
                
                # Ana alanları listele
                print("\n📋 SENTOS ANA ALANLAR:")
                for key in product.keys():
                    value_type = type(product[key]).__name__
                    if isinstance(product[key], list) and product[key]:
                        item_type = type(product[key][0]).__name__
                        print(f"  {key}: {value_type}[{item_type}] (count: {len(product[key])})")
                    else:
                        print(f"  {key}: {value_type}")
                
                # Variants yapısını detaylandır
                if product.get('variants'):
                    variant = product['variants'][0]
                    print("\n🎯 SENTOS VARIANT YAPISI:")
                    for key in variant.keys():
                        value_type = type(variant[key]).__name__
                        if isinstance(variant[key], list) and variant[key]:
                            item_type = type(variant[key][0]).__name__
                            print(f"  {key}: {value_type}[{item_type}] (count: {len(variant[key])})")
                        else:
                            print(f"  {key}: {value_type}")
                
                return product
            else:
                print("❌ Sentos'ta ürün bulunamadı!")
                return None
        else:
            print(f"❌ Sentos API hatası: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Sentos analiz hatası: {str(e)}")
        return None

def compare_structures(shopify_product, sentos_product):
    """İki API yapısını karşılaştır ve mapping öner"""
    
    if not shopify_product or not sentos_product:
        print("❌ Karşılaştırma için her iki ürün de gerekli!")
        return
    
    print("\n🔄 ALAN KARŞILAŞTIRMASI:")
    print("=" * 80)
    
    # Temel mapping önerileri
    mapping_suggestions = {
        # Shopify Field -> Sentos Field
        'title': ['name', 'title', 'product_name'],
        'body_html': ['description', 'description_detail', 'product_description'],
        'vendor': ['brand', 'manufacturer', 'supplier'],
        'product_type': ['category', 'type', 'product_type'],
        'tags': ['tags', 'categories', 'keywords'],
        'handle': ['slug', 'permalink', 'url_key'],
        'variants': ['variants', 'options', 'variations']
    }
    
    print("📋 ÖNERİLEN ALAN EŞLEŞTİRMELERİ:")
    for shopify_field, sentos_candidates in mapping_suggestions.items():
        print(f"\nShopify.{shopify_field} -> Sentos:")
        found_fields = []
        for candidate in sentos_candidates:
            if candidate in sentos_product:
                found_fields.append(f"✅ {candidate}")
            else:
                found_fields.append(f"❌ {candidate}")
        print("  " + ", ".join(found_fields))
    
    # Variant karşılaştırması
    if shopify_product.get('variants') and sentos_product.get('variants'):
        shopify_variant = shopify_product['variants'][0]
        sentos_variant = sentos_product['variants'][0]
        
        print(f"\n🎯 VARIANT ALAN KARŞILAŞTIRMASI:")
        variant_mapping = {
            'price': ['price', 'sale_price', 'cost'],
            'sku': ['sku', 'code', 'product_code'],
            'barcode': ['barcode', 'upc', 'ean'],
            'inventory_quantity': ['stock', 'quantity', 'inventory'],
            'option1': ['color', 'size', 'option1'],
            'option2': ['size', 'color', 'option2']
        }
        
        for shopify_field, sentos_candidates in variant_mapping.items():
            print(f"\nVariant.{shopify_field} -> Sentos:")
            found_fields = []
            for candidate in sentos_candidates:
                if candidate in sentos_variant:
                    found_fields.append(f"✅ {candidate}")
                else:
                    found_fields.append(f"❌ {candidate}")
            print("  " + ", ".join(found_fields))

def create_minimal_shopify_product():
    """En minimal Shopify ürün oluşturma denemesi - GraphQL ile"""
    
    credentials = config_manager.load_all_keys()
    
    if not credentials:
        print("❌ Ayarlar bulunamadı!")
        return None
    
    headers = {
        'X-Shopify-Access-Token': credentials['shopify_token'],
        'Content-Type': 'application/json'
    }
    
    url = f"https://{credentials['shopify_store']}/admin/api/2024-10/graphql.json"
    
    # GraphQL mutation ile farklı minimal kombinasyonları test et
    test_cases = [
        {
            'name': 'Sadece title',
            'input': {
                'title': 'Test Product - Only Title'
            }
        },
        {
            'name': 'Title + vendor',
            'input': {
                'title': 'Test Product - Title + Vendor',
                'vendor': 'Test Vendor'
            }
        },
        {
            'name': 'Title + product_type',
            'input': {
                'title': 'Test Product - Title + Type',
                'productType': 'Test Type'
            }
        },
        {
            'name': 'Title + vendor + product_type',
            'input': {
                'title': 'Test Product - Complete',
                'vendor': 'Test Vendor',
                'productType': 'Test Type'
            }
        },
        {
            'name': 'Title + status',
            'input': {
                'title': 'Test Product - With Status',
                'status': 'DRAFT'
            }
        }
    ]
    
    # GraphQL mutation
    mutation = """
    mutation productCreate($input: ProductInput!) {
      productCreate(input: $input) {
        product {
          id
          title
          vendor
          productType
          status
        }
        userErrors {
          field
          message
        }
      }
    }
    """
    
    for test_case in test_cases:
        print(f"\n🧪 TEST: {test_case['name']}")
        print(f"📦 Input: {json.dumps(test_case['input'], indent=2)}")
        
        try:
            payload = {
                "query": mutation,
                "variables": {
                    "input": test_case['input']
                }
            }
            
            response = requests.post(url, headers=headers, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                
                # GraphQL hata kontrolü
                if data.get('errors'):
                    print(f"❌ GraphQL errors: {data['errors']}")
                    continue
                
                product_create = data.get('data', {}).get('productCreate', {})
                user_errors = product_create.get('userErrors', [])
                
                if user_errors:
                    print(f"❌ User errors: {user_errors}")
                    continue
                
                created_product = product_create.get('product', {})
                if created_product:
                    print(f"✅ BAŞARILI! Product ID: {created_product.get('id')}")
                    
                    # Oluşan ürünü sil (test için) - GraphQL mutation ile
                    delete_mutation = """
                    mutation productDelete($input: ProductDeleteInput!) {
                      productDelete(input: $input) {
                        deletedProductId
                        userErrors {
                          field
                          message
                        }
                      }
                    }
                    """
                    
                    delete_payload = {
                        "query": delete_mutation,
                        "variables": {
                            "input": {
                                "id": created_product['id']
                            }
                        }
                    }
                    
                    delete_response = requests.post(url, headers=headers, json=delete_payload)
                    if delete_response.status_code == 200:
                        delete_data = delete_response.json()
                        if not delete_data.get('errors') and not delete_data.get('data', {}).get('productDelete', {}).get('userErrors'):
                            print("🗑️ Test ürünü silindi")
                    
                    return test_case['input']
                else:
                    print("❌ Ürün oluşturulamadı")
            else:
                print(f"❌ BAŞARISIZ: {response.status_code}")
                print(f"📋 Response: {response.text}")
                
        except Exception as e:
            print(f"❌ Hata: {str(e)}")
    
    return None

if __name__ == "__main__":
    print("🚀 API YAPI ANALİZİ BAŞLATIYOR...")
    print("=" * 80)
    
    # 1. Shopify ürün yapısını analiz et
    shopify_product = analyze_shopify_product()
    
    print("\n" + "=" * 80)
    
    # 2. Sentos ürün yapısını analiz et
    sentos_product = analyze_sentos_product()
    
    print("\n" + "=" * 80)
    
    # 3. Yapıları karşılaştır
    compare_structures(shopify_product, sentos_product)
    
    print("\n" + "=" * 80)
    
    # 4. Minimal Shopify ürün oluşturma testi
    print("\n🧪 MİNİMAL SHOPIFY ÜRÜN OLUŞTURMA TESTİ:")
    minimal_product = create_minimal_shopify_product()
    
    if minimal_product:
        print(f"\n✅ EN MİNİMAL BAŞARILI SHOPIFY ÜRÜN YAPISI:")
        print(json.dumps(minimal_product, indent=2, ensure_ascii=False))
    else:
        print("\n❌ Hiçbir minimal kombinasyon başarılı olmadı!")
    
    print("\n🏁 ANALİZ TAMAMLANDI!")
