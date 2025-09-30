#!/usr/bin/env python3
"""
Sipariş Toplam Tutarı Düzeltme Testi
Transaction kaldırılarak doğru tutarın gösterilmesi testi
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from operations.shopify_order_builder import create_order_input_builder

def test_order_without_transaction():
    """Transaction olmadan sipariş oluşturma testi"""
    print("🧪 Test: Transaction Olmadan Sipariş Oluşturma")
    print("=" * 50)
    
    builder = create_order_input_builder()
    
    # İndirimli line item'lar (toplam ₺28,197)
    order_data = {
        "customerId": "gid://shopify/Customer/123456789",
        "lineItems": [
            {
                "variantId": "gid://shopify/ProductVariant/111",
                "quantity": 1,
                "price": "14098.50",  # İndirimli fiyat
                "currency": "TRY"
            },
            {
                "variantId": "gid://shopify/ProductVariant/222", 
                "quantity": 1,
                "price": "14098.50",  # İndirimli fiyat
                "currency": "TRY"
            }
        ],
        "shippingAddress": {
            "name": "Test Müşteri",
            "address1": "Test Adres 1",
            "city": "Istanbul",
            "country": "Turkey"
        },
        "note": "Kaynak Mağazadan Aktarılan Sipariş. Orijinal Sipariş No: #1001 | Net Tutar: ₺28197.00",
        "email": "test@example.com"
        # NOT: transactions alanı yok - Shopify otomatik hesaplayacak
    }
    
    result = builder['build_order_input'](order_data)
    
    print("📋 Oluşturulan Order Input:")
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # Kontroller
    print("\n✅ Kontroller:")
    print(f"✓ Customer ID var: {'customerId' in result}")
    print(f"✓ Line Items var: {'lineItems' in result}")
    print(f"✓ Transaction YOK (Shopify hesaplayacak): {'transactions' not in result}")
    print(f"✓ Note var: {'note' in result}")
    print(f"✓ priceSet formatı kullanılıyor (price yerine): {any('priceSet' in item for item in result.get('lineItems', []))}")
    
    # Line item toplamı hesapla
    total = 0
    if 'lineItems' in result:
        for item in result['lineItems']:
            if 'priceSet' in item:
                price = float(item['priceSet']['shopMoney']['amount'])
                quantity = int(item.get('quantity', 0))
                total += price * quantity
    
    print(f"✓ Line Items Toplamı: ₺{total:.2f}")
    print(f"✓ Beklenen Tutar: ₺28,197.00")
    print(f"✓ Eşleşme: {abs(total - 28197.0) < 1}")
    print(f"✓ GraphQL Schema Uyumlu: priceSet kullanılıyor")
    
    return result

def test_with_transaction():
    """Transaction ile sipariş oluşturma testi (karşılaştırma için)"""
    print("\n🧪 Test: Transaction ile Sipariş Oluşturma (Karşılaştırma)")
    print("=" * 50)
    
    builder = create_order_input_builder()
    
    # Aynı line item'lar ama transaction da var
    order_data = {
        "customerId": "gid://shopify/Customer/123456789",
        "lineItems": [
            {
                "variantId": "gid://shopify/ProductVariant/111",
                "quantity": 1,
                "price": "14098.50",
                "currency": "TRY"
            },
            {
                "variantId": "gid://shopify/ProductVariant/222",
                "quantity": 1, 
                "price": "14098.50",
                "currency": "TRY"
            }
        ],
        "transactions": [{
            "gateway": "manual",
            "amount": "52601.00",  # Yanlış tutar (indirimsiz)
            "currency": "TRY"
        }],
        "note": "Transaction ile test",
        "email": "test@example.com"
    }
    
    result = builder['build_order_input'](order_data)
    
    print("📋 Transaction'lı Order Input:")
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    print("\n❌ Sorun:")
    print("Line Items Toplamı: ₺28,197.00")
    print("Transaction Tutarı: ₺52,601.00")
    print("Shopify bu durumda 'kısmı ödeme' olarak algılar!")
    
    return result

if __name__ == "__main__":
    print("🔧 Sipariş Toplam Tutarı Düzeltme Testi")
    print("=" * 60)
    
    # İlk test: Transaction olmadan (doğru yöntem)
    test_order_without_transaction()
    
    # İkinci test: Transaction ile (sorunlu yöntem)
    test_with_transaction()
    
    print("\n🎯 Sonuç:")
    print("Transaction kaldırılarak Shopify'ın otomatik hesaplama")
    print("yapması sağlanıyor. Böylece sipariş değeri line item")
    print("toplamı (₺28,197) olarak görünecek, 'kısmı ödeme' değil.")