# connectors/shopify_api.py (Rate Limit Geliştirilmiş)

import requests
import time
import json
import logging
from datetime import datetime, timedelta

class ShopifyAPI:
    """Shopify Admin API ile iletişimi yöneten sınıf."""
    def __init__(self, store_url, access_token, api_version='2024-10'): # api_version parametresi burada ekli olmalı
        if not store_url: raise ValueError("Shopify Mağaza URL'si boş olamaz.")
        if not access_token: raise ValueError("Shopify Erişim Token'ı boş olamaz.")
        
        self.store_url = store_url if store_url.startswith('http') else f"https://{store_url.strip()}"
        self.access_token = access_token
        self.api_version = api_version # Gelen versiyonu kullan
        self.graphql_url = f"{self.store_url}/admin/api/{self.api_version}/graphql.json" # URL'yi dinamik hale getir
        self.rest_api_version = self.api_version
        self.headers = {
            'X-Shopify-Access-Token': access_token,
            'Content-Type': 'application/json',
            'User-Agent': 'Sentos-Sync-Python/Modular-v1.0'
        }
        self.product_cache = {}
        self.location_id = None
        
        # Geri kalan kodlar aynı
        self.last_request_time = 0
        self.min_request_interval = 0.4
        self.request_count = 0
        self.window_start = time.time()
        self.max_requests_per_minute = 40
        self.burst_tokens = 10
        self.current_tokens = 10

    def _rate_limit_wait(self):
        """10-worker için optimize edilmiş rate limiter"""
        current_time = time.time()
    
        # Token bucket sistemi
        elapsed = current_time - self.last_request_time
        tokens_to_add = elapsed * (self.max_requests_per_minute / 60.0)
        self.current_tokens = min(self.burst_tokens, self.current_tokens + tokens_to_add)
    
        if self.current_tokens >= 1:
            self.current_tokens -= 1
            self.last_request_time = current_time
            return
    
        # Token yetersiz, bekleme hesapla
        wait_time = (1 - self.current_tokens) / (self.max_requests_per_minute / 60.0)
        time.sleep(wait_time)
        self.last_request_time = time.time()
        self.current_tokens = 0

    def _make_request(self, method, endpoint, data=None, is_graphql=False, headers=None, files=None):
        self._rate_limit_wait()
        
        req_headers = headers if headers is not None else self.headers
        try:
            if not is_graphql and not endpoint.startswith('http'):
                # ✅ REST API endpoint'lerde de 2024-10 sürümünü kullan
                url = f"{self.store_url}/admin/api/{self.rest_api_version}/{endpoint}"
            else:
                url = endpoint if endpoint.startswith('http') else self.graphql_url
            
            response = requests.request(method, url, headers=req_headers, 
                                        json=data if isinstance(data, dict) else None, 
                                        data=data if isinstance(data, bytes) else None,
                                        files=files, timeout=90)
            response.raise_for_status()
            if response.content and 'application/json' in response.headers.get('Content-Type', ''):
                return response.json()
            return response
        except requests.exceptions.RequestException as e:
            error_content = e.response.text if e.response else "No response"
            logging.error(f"Shopify API Bağlantı Hatası ({url}): {e} - Response: {error_content}")
            raise e

    def execute_graphql(self, query, variables=None):
        """
        GraphQL sorgusunu çalıştırır ve hız limitine takıldığında
        otomatik olarak bekleyip tekrar dener (exponential backoff).
        """
        payload = {'query': query, 'variables': variables or {}}
        max_retries = 8  # Daha fazla deneme
        retry_delay = 2  # Başlangıç bekleme süresi

        for attempt in range(max_retries):
            try:
                response_data = self._make_request('POST', self.graphql_url, data=payload, is_graphql=True)
                
                if "errors" in response_data:
                    is_throttled = any(
                        err.get('extensions', {}).get('code') == 'THROTTLED' 
                        for err in response_data["errors"]
                    )
                    
                    if is_throttled and attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                        logging.warning(f"GraphQL Throttled! {wait_time} saniye beklenip tekrar denenecek... (Deneme {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    
                    error_messages = [err.get('message', 'Bilinmeyen GraphQL hatası') for err in response_data["errors"]]
                    logging.error(f"GraphQL sorgusu hata verdi: {json.dumps(response_data['errors'], indent=2)}")
                    raise Exception(f"GraphQL Error: {', '.join(error_messages)}")

                return response_data.get("data", {})

            except requests.exceptions.HTTPError as e:
                if e.response and e.response.status_code == 429 and attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    logging.warning(f"HTTP 429 Rate Limit! {wait_time} saniye beklenip tekrar denenecek...")
                    time.sleep(wait_time)
                    continue
                else:
                    logging.error(f"API bağlantı hatası: {e}")
                    raise e
            except requests.exceptions.RequestException as e:
                 logging.error(f"API bağlantı hatası: {e}. Bu hata için tekrar deneme yapılmıyor.")
                 raise e
        
        raise Exception(f"API isteği {max_retries} denemenin ardından başarısız oldu.")
    
    def get_orders_by_date_range(self, start_date_iso, end_date_iso):
        """
        DÜZELTİLDİ: İndirim bilgilerini de içerecek şekilde güncellendi.
        """
        all_orders = []
        # --- GraphQL Sorgusu İndirim Bilgileri Eklenerek Güncellendi ---
        query = """
        query getOrders($cursor: String, $filter_query: String!) {
          orders(first: 25, after: $cursor, query: $filter_query, sortKey: CREATED_AT, reverse: true) {
            pageInfo { hasNextPage, endCursor }
            edges {
              node {
                id, name, createdAt, displayFinancialStatus, displayFulfillmentStatus
                totalPriceSet { shopMoney { amount, currencyCode } }
                customer { firstName, lastName, email, phone }
                shippingAddress { firstName, lastName, address1, address2, city, provinceCode, zip, country, phone }
                lineItems(first: 50) {
                  nodes {
                    title, quantity
                    variant { sku, title }
                    originalUnitPriceSet { shopMoney { amount, currencyCode } }
                    discountedUnitPriceSet { shopMoney { amount, currencyCode } }
                    totalDiscountSet { shopMoney { amount, currencyCode } }
                    discountAllocations {
                      allocatedAmountSet { shopMoney { amount, currencyCode } }
                      discountApplication { title }
                    }
                  }
                }
              }
            }
          }
        }
        """
        variables = {"cursor": None, "filter_query": f"created_at:>='{start_date_iso}' AND created_at:<='{end_date_iso}'"}
        
        while True:
            # ... (Döngünün geri kalanı öncekiyle aynı)
            logging.info(f"Siparişler çekiliyor... Cursor: {variables['cursor']}")
            data = self.execute_graphql(query, variables)
            orders_data = data.get("orders", {})
            for edge in orders_data.get("edges", []):
                all_orders.append(edge["node"])
            
            page_info = orders_data.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            
            variables["cursor"] = page_info["endCursor"]
            time.sleep(0.5)

        logging.info(f"Tarih aralığı için toplam {len(all_orders)} sipariş çekildi.")
        return all_orders
        
    def get_locations(self):
        """
        YENİ FONKSİYON: Mağazadaki tüm aktif envanter konumlarını (locations) çeker.
        """
        query = """
        query {
          locations(first: 25, query:"status:active") {
            edges {
              node {
                id
                name
                address {
                  city
                  country
                }
              }
            }
          }
        }
        """
        try:
            result = self.execute_graphql(query)
            locations_edges = result.get("locations", {}).get("edges", [])
            locations = [edge['node'] for edge in locations_edges]
            logging.info(f"{len(locations)} adet aktif Shopify lokasyonu bulundu.")
            return locations
        except Exception as e:
            logging.error(f"Shopify lokasyonları çekilirken hata: {e}")
            return []

    def get_all_collections(self, progress_callback=None):
        all_collections = []
        query = """
        query getCollections($cursor: String) {
          collections(first: 50, after: $cursor) {
            pageInfo { hasNextPage endCursor }
            edges { node { id title } }
          }
        }
        """
        variables = {"cursor": None}
        while True:
            if progress_callback:
                progress_callback(f"Shopify'dan koleksiyonlar çekiliyor... {len(all_collections)} koleksiyon bulundu.")
            data = self.execute_graphql(query, variables)
            collections_data = data.get("collections", {})
            for edge in collections_data.get("edges", []):
                all_collections.append(edge["node"])
            if not collections_data.get("pageInfo", {}).get("hasNextPage"):
                break
            variables["cursor"] = collections_data["pageInfo"]["endCursor"]
        logging.info(f"{len(all_collections)} adet koleksiyon bulundu.")
        return all_collections

    def get_all_products_for_export(self, progress_callback=None):
        all_products = []
        query = """
        query getProductsForExport($cursor: String) {
          products(first: 25, after: $cursor) {
            pageInfo { hasNextPage endCursor }
            edges {
              node {
                title handle
                collections(first: 20) { edges { node { id title } } }
                featuredImage { url }
                variants(first: 100) {
                  edges {
                    node {
                      sku displayName inventoryQuantity
                      selectedOptions { name value }
                      inventoryItem { unitCost { amount } }
                    }
                  }
                }
              }
            }
          }
        }
        """
        variables = {"cursor": None}
        total_fetched = 0
        while True:
            if progress_callback:
                progress_callback(f"Shopify'dan ürün verisi çekiliyor... {total_fetched} ürün alındı.")
            data = self.execute_graphql(query, variables)
            products_data = data.get("products", {})
            for edge in products_data.get("edges", []):
                all_products.append(edge["node"])
            total_fetched = len(all_products)
            if not products_data.get("pageInfo", {}).get("hasNextPage"):
                break
            variables["cursor"] = products_data["pageInfo"]["endCursor"]
        logging.info(f"Export için toplam {len(all_products)} ürün çekildi.")
        return all_products

    def get_variant_ids_by_skus(self, skus: list, search_by_product_sku=False) -> dict:
        """
        RATE LIMIT KORUMASIZ GELIŞTIRILMIŞ VERSİYON
        """
        if not skus: return {}
        sanitized_skus = [str(sku).strip() for sku in skus if sku]
        if not sanitized_skus: return {}
        
        logging.info(f"{len(sanitized_skus)} adet SKU için varyant ID'leri aranıyor (Mod: {'Ürün Bazlı' if search_by_product_sku else 'Varyant Bazlı'})...")
        sku_map = {}
        
        # KRITIK: Batch boyutunu 2'ye düşür
        batch_size = 2
        
        for i in range(0, len(sanitized_skus), batch_size):
            sku_chunk = sanitized_skus[i:i + batch_size]
            query_filter = " OR ".join([f"sku:{json.dumps(sku)}" for sku in sku_chunk])
            
            query = """
            query getProductsBySku($query: String!) {
              products(first: 10, query: $query) {
                edges {
                  node {
                    id
                    variants(first: 50) {
                      edges {
                        node { 
                          id
                          sku 
                        }
                      }
                    }
                  }
                }
              }
            }
            """

            try:
                logging.info(f"SKU batch {i//batch_size+1}/{len(range(0, len(sanitized_skus), batch_size))} işleniyor: {sku_chunk}")
                result = self.execute_graphql(query, {"query": query_filter})
                product_edges = result.get("products", {}).get("edges", [])
                for p_edge in product_edges:
                    product_node = p_edge.get("node", {})
                    product_id = product_node.get("id")
                    variant_edges = product_node.get("variants", {}).get("edges", [])
                    for v_edge in variant_edges:
                        node = v_edge.get("node", {})
                        if node.get("sku") and node.get("id") and product_id:
                            sku_map[node["sku"]] = {
                                "variant_id": node["id"],
                                "product_id": product_id
                            }
                
                # KRITIK: Her batch sonrası uzun bekleme
                if i + batch_size < len(sanitized_skus):
                    logging.info(f"Batch {i//batch_size+1} tamamlandı, rate limit için 3 saniye bekleniyor...")
                    time.sleep(3)
            
            except Exception as e:
                logging.error(f"SKU grubu {i//batch_size+1} için varyant ID'leri alınırken hata: {e}")
                # Hata durumunda da biraz bekle
                time.sleep(5)
                raise e

        logging.info(f"Toplam {len(sku_map)} eşleşen varyant detayı bulundu.")
        return sku_map

    def get_product_media_details(self, product_gid):
        try:
            query = """
            query getProductMedia($id: ID!) {
                product(id: $id) {
                    media(first: 250) {
                        edges { node { id alt ... on MediaImage { image { originalSrc } } } }
                    }
                }
            }
            """
            result = self.execute_graphql(query, {"id": product_gid})
            media_edges = result.get("product", {}).get("media", {}).get("edges", [])
            media_details = [{'id': n['id'], 'alt': n.get('alt'), 'originalSrc': n.get('image', {}).get('originalSrc')} for n in [e.get('node') for e in media_edges] if n]
            logging.info(f"Ürün {product_gid} için {len(media_details)} mevcut medya bulundu.")
            return media_details
        except Exception as e:
            logging.error(f"Mevcut medya detayları alınırken hata: {e}")
            return []

    def get_default_location_id(self):
        if self.location_id: return self.location_id
        query = "query { locations(first: 1, query: \"status:active\") { edges { node { id } } } }"
        data = self.execute_graphql(query)
        locations = data.get("locations", {}).get("edges", [])
        if not locations: raise Exception("Shopify mağazasında aktif bir envanter lokasyonu bulunamadı.")
        self.location_id = locations[0]['node']['id']
        logging.info(f"Shopify Lokasyon ID'si bulundu: {self.location_id}")
        return self.location_id

    def load_all_products_for_cache(self, progress_callback=None):
        total_loaded = 0
        endpoint = f'{self.store_url}/admin/api/2024-10/products.json?limit=50&fields=id,title,variants'  # Limit düşürüldü
        
        while endpoint:
            if progress_callback: progress_callback({'message': f"Shopify ürünleri önbelleğe alınıyor... {total_loaded} ürün bulundu."})
            
            response = requests.get(endpoint, headers=self.headers)
            response.raise_for_status()
            products = response.json().get('products', [])
            
            for product in products:
                product_data = {'id': product['id'], 'gid': f"gid://shopify/Product/{product['id']}"}
                if title := product.get('title'): self.product_cache[f"title:{title.strip()}"] = product_data
                for variant in product.get('variants', []):
                    if sku := variant.get('sku'): self.product_cache[f"sku:{sku.strip()}"] = product_data
            
            total_loaded += len(products)
            link_header = response.headers.get('Link', '')
            endpoint = next((link['url'] for link in requests.utils.parse_header_links(link_header) if link.get('rel') == 'next'), None)
            
            # REST API için de rate limit koruması
            time.sleep(1)
        
        logging.info(f"Shopify'dan toplam {total_loaded} ürün önbelleğe alındı.")
        return total_loaded
    
    def delete_product_media(self, product_id, media_ids):
        """Ürün medyalarını siler"""
        if not media_ids: 
            return
            
        logging.info(f"Ürün GID: {product_id} için {len(media_ids)} medya siliniyor...")
        
        query = """
        mutation productDeleteMedia($productId: ID!, $mediaIds: [ID!]!) {
            productDeleteMedia(productId: $productId, mediaIds: $mediaIds) {
                deletedMediaIds
                userErrors { field message }
            }
        }
        """
        try:
            result = self.execute_graphql(query, {'productId': product_id, 'mediaIds': media_ids})
            deleted_ids = result.get('productDeleteMedia', {}).get('deletedMediaIds', [])
            errors = result.get('productDeleteMedia', {}).get('userErrors', [])
            
            if errors: 
                logging.warning(f"Medya silme hataları: {errors}")
            
            logging.info(f"{len(deleted_ids)} medya başarıyla silindi.")
            
        except Exception as e:
            logging.error(f"Medya silinirken kritik hata oluştu: {e}")

    def reorder_product_media(self, product_id, media_ids):
        """Ürün medyalarını yeniden sıralar"""
        if not media_ids or len(media_ids) < 2:
            logging.info("Yeniden sıralama için yeterli medya bulunmuyor (1 veya daha az).")
            return

        moves = [{"id": media_id, "newPosition": str(i)} for i, media_id in enumerate(media_ids)]
        
        logging.info(f"Ürün {product_id} için {len(moves)} medya yeniden sıralama işlemi gönderiliyor...")
        
        query = """
        mutation productReorderMedia($id: ID!, $moves: [MoveInput!]!) {
          productReorderMedia(id: $id, moves: $moves) {
            userErrors {
              field
              message
            }
          }
        }
        """
        try:
            result = self.execute_graphql(query, {'id': product_id, 'moves': moves})
            
            errors = result.get('productReorderMedia', {}).get('userErrors', [])
            if errors:
                logging.warning(f"Medya yeniden sıralama hataları: {errors}")
            else:
                logging.info("✅ Medya yeniden sıralama işlemi başarıyla gönderildi.")
                
        except Exception as e:
            logging.error(f"Medya yeniden sıralanırken kritik hata: {e}")

    def test_connection(self):
        """Shopify bağlantısını test eder"""
        try:
            query = """
            query {
                shop {
                    name
                    currencyCode
                    plan {
                        displayName
                    }
                }
                products(first: 1) {
                    edges {
                        node {
                            id
                        }
                    }
                }
            }
            """
            result = self.execute_graphql(query)
            shop_data = result.get('shop', {})
            products_data = result.get('products', {}).get('edges', [])
            
            return {
                'success': True,
                'name': shop_data.get('name'),
                'currency': shop_data.get('currencyCode'),
                'plan': shop_data.get('plan', {}).get('displayName'),
                'products_count': len(products_data),
                'message': 'GraphQL API OK'
            }
        except Exception as e:
            return {'success': False, 'message': f'GraphQL API failed: {e}'}

    def get_products_in_collection_with_inventory(self, collection_id):
        """
        Belirli bir koleksiyondaki tüm ürünleri, toplam stok bilgileriyle birlikte çeker.
        Sayfalama yaparak tüm ürünlerin alınmasını sağlar.
        """
        all_products = []
        query = """
        query getCollectionProducts($id: ID!, $cursor: String) {
          collection(id: $id) {
            title
            products(first: 50, after: $cursor) {
              pageInfo {
                hasNextPage
                endCursor
              }
              edges {
                node {
                  id
                  title
                  handle
                  totalInventory
                  featuredImage {
                    url(transform: {maxWidth: 100, maxHeight: 100})
                  }
                }
              }
            }
          }
        }
        """
        variables = {"id": collection_id, "cursor": None}
        
        while True:
            logging.info(f"Koleksiyon ürünleri çekiliyor... Cursor: {variables['cursor']}")
            data = self.execute_graphql(query, variables)
            
            collection_data = data.get("collection")
            if not collection_data:
                logging.error(f"Koleksiyon {collection_id} bulunamadı veya veri alınamadı.")
                break

            products_data = collection_data.get("products", {})
            for edge in products_data.get("edges", []):
                all_products.append(edge["node"])
            
            page_info = products_data.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            
            variables["cursor"] = page_info["endCursor"]
            time.sleep(0.5) # Rate limit için küçük bir bekleme

        logging.info(f"Koleksiyon için toplam {len(all_products)} ürün ve stok bilgisi çekildi.")
        return all_products        
        
    def update_product_metafield(self, product_gid, namespace, key, value):
        """
        Bir ürünün belirli bir tamsayı (integer) metafield'ını günceller.
        """
        logging.info(f"Metafield güncelleniyor: Ürün GID: {product_gid}, {namespace}.{key} = {value}")
        
        # Hatanın olduğu sorgu bu kısımdadır.
        mutation = """
        # Değişkenler burada da tanımlanmalı: $namespace: String!, $key: String!
        mutation productUpdate($input: ProductInput!, $namespace: String!, $key: String!) {
          productUpdate(input: $input) {
            product {
              id
              metafield(namespace: $namespace, key: $key) {
                value
              }
            }
            userErrors {
              field
              message
            }
          }
        }
        """
        
        variables = {
          "input": {
            "id": product_gid,
            "metafields": [
              {
                "namespace": namespace,
                "key": key,
                "value": str(value),
                "type": "number_integer"
              }
            ]
          },
          "namespace": namespace,
          "key": key
        }

        try:
            result = self.execute_graphql(mutation, variables)
            if errors := result.get('productUpdate', {}).get('userErrors', []):
                error_message = f"Metafield güncelleme hatası: {errors}"
                logging.error(error_message)
                return {'success': False, 'reason': error_message}
            
            updated_value = result.get('productUpdate', {}).get('product', {}).get('metafield', {}).get('value')
            logging.info(f"✅ Metafield başarıyla güncellendi. Yeni değer: {updated_value}")
            return {'success': True, 'new_value': updated_value}
        
        except Exception as e:
            error_message = f"Metafield güncellenirken kritik hata: {e}"
            logging.error(error_message)
            return {'success': False, 'reason': str(e)}
        
    def create_product_sortable_metafield_definition(self, method='modern'):
        """
        Metafield tanımını, seçilen metoda (modern, legacy, hybrid) göre oluşturur.
        """
        logging.info(f"API üzerinden metafield tanımı oluşturuluyor (Metot: {method}, API Versiyon: {self.api_version})...")

        mutation = """
        mutation metafieldDefinitionCreate($definition: MetafieldDefinitionInput!) {
          metafieldDefinitionCreate(definition: $definition) {
            createdDefinition {
              id
              name
            }
            userErrors {
              field
              message
              code
            }
          }
        }
        """

        # Temel tanım
        base_definition = {
            "name": "Toplam Stok Siralamasi",
            "namespace": "custom_sort",
            "key": "total_stock",
            "type": "number_integer",
            "ownerType": "PRODUCT",
        }

        # Seçilen metoda göre tanımı dinamik olarak oluştur
        if method == 'modern':
            base_definition["capabilities"] = {"sortable": True}
        elif method == 'legacy':
            base_definition["sortable"] = True
        elif method == 'hybrid':
            base_definition["capabilities"] = {"sortable": True}
            base_definition["sortable"] = True
        
        variables = {"definition": base_definition}

        try:
            result = self.execute_graphql(mutation, variables)
            errors = result.get('metafieldDefinitionCreate', {}).get('userErrors', [])
            if errors:
                if any(error.get('code') == 'TAKEN' for error in errors):
                    return {'success': True, 'message': 'Metafield tanımı zaten mevcut.'}
                return {'success': False, 'message': f"Metafield tanımı hatası: {errors}"}

            created_definition = result.get('metafieldDefinitionCreate', {}).get('createdDefinition')
            if created_definition:
                return {'success': True, 'message': f"✅ Tanım başarıyla oluşturuldu: {created_definition.get('name')}"}
            return {'success': False, 'message': 'Tanım oluşturuldu ancak sonuç alınamadı.'}

        except Exception as e:
            return {'success': False, 'message': f"Kritik API hatası: {e}"}
        
    def get_collection_available_sort_keys(self, collection_gid):
        """
        Belirli bir koleksiyon için mevcut olan sıralama anahtarlarını
        doğrudan API'den sorgular.
        """
        query = """
        query collectionSortKeys($id: ID!) {
          collection(id: $id) {
            id
            title
            availableSortKeys {
              key
              title
              urlParam
            }
          }
        }
        """
        try:
            result = self.execute_graphql(query, {"id": collection_gid})
            collection_data = result.get('collection', {})
            if not collection_data:
                return {'success': False, 'message': 'Koleksiyon bulunamadı.'}
            
            sort_keys = collection_data.get('availableSortKeys', [])
            return {'success': True, 'data': sort_keys}
        except Exception as e:
            return {'success': False, 'message': str(e)}    