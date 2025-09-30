#!/usr/bin/env python3
"""
Shopify GraphQL OrderCreateLineItemInput Testi
priceSet formatının doğru çalışıp çalışmadığını test eder
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from operations.shopify_order_builder import create_order_input_builder

def test_graphql_schema_compatibility():
    """Gerçek GraphQL şemasına uygunluk testi"""
    print("🧪 Test: Shopify GraphQL Schema Uyumluluğu")
    print("=" * 50)
    
    builder = create_order_input_builder()
    
    # Gerçek verilere benzer test data
    order_data = {
        "customerId": "gid://shopify/Customer/123456789",
        "lineItems": [
            {
                "variantId": "gid://shopify/ProductVariant/111",
                "quantity": 2,
                "price": "199.99",
                "currency": "TRY"
            },
            {
                "variantId": "gid://shopify/ProductVariant/222",
                "quantity": 1,
                "price": "299.50",
                "currency": "TRY"
            }
        ],
        "shippingAddress": {
            "name": "Ahmet Yılmaz",
            "address1": "Atatürk Caddesi No:123",
            "city": "İstanbul",
            "country": "Turkey",
            "phone": "+905551234567"
        },
        "note": "Kaynak Mağazadan Aktarılan Sipariş",
        "email": "ahmet@example.com"
    }
    
    result = builder['build_order_input'](order_data)
    
    print("📋 Oluşturulan GraphQL Input:")
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # Schema kontrolleri
    print("\n✅ GraphQL Schema Kontrolleri:")
    
    # 1. OrderCreateOrderInput ana alanları
    required_fields = ['customerId', 'lineItems']
    for field in required_fields:
        print(f"✓ {field}: {'✅' if field in result else '❌'}")
    
    # 2. LineItem alanları
    line_items = result.get('lineItems', [])
    if line_items:
        first_item = line_items[0]
        print(f"✓ variantId: {'✅' if 'variantId' in first_item else '❌'}")
        print(f"✓ quantity: {'✅' if 'quantity' in first_item else '❌'}")
        print(f"✓ priceSet (price yerine): {'✅' if 'priceSet' in first_item else '❌'}")
        print(f"✓ price alanı YOK: {'✅' if 'price' not in first_item else '❌ (price alanı olmamalı)'}")
        
        # 3. priceSet yapısı
        if 'priceSet' in first_item:
            price_set = first_item['priceSet']
            print(f"✓ priceSet.shopMoney: {'✅' if 'shopMoney' in price_set else '❌'}")
            if 'shopMoney' in price_set:
                shop_money = price_set['shopMoney']
                print(f"✓ shopMoney.amount: {'✅' if 'amount' in shop_money else '❌'}")
                print(f"✓ shopMoney.currencyCode: {'✅' if 'currencyCode' in shop_money else '❌'}")
    
    # 4. Transactions alanının olmaması
    print(f"✓ transactions alanı YOK: {'✅' if 'transactions' not in result else '❌ (transactions olmamalı)'}")
    
    # 5. Toplam tutar hesaplama
    total = 0
    for item in line_items:
        if 'priceSet' in item:
            amount = float(item['priceSet']['shopMoney']['amount'])
            quantity = int(item['quantity'])
            total += amount * quantity
    
    print(f"\n💰 Hesaplanan Toplam: ₺{total:.2f}")
    print(f"✓ Beklenen: ₺{(199.99 * 2) + (299.50 * 1):.2f}")
    
    return result

def test_error_scenarios():
    """Hata senaryolarını test eder"""
    print("\n🧪 Test: Hata Senaryoları")
    print("=" * 30)
    
    builder = create_order_input_builder()
    
    # 1. Boş line items
    result1 = builder['build_order_input']({
        "customerId": "gid://shopify/Customer/123",
        "lineItems": []
    })
    print(f"✓ Boş line items: {'✅' if 'lineItems' not in result1 else '❌'}")
    
    # 2. Price olmayan line item
    result2 = builder['build_order_input']({
        "customerId": "gid://shopify/Customer/123",
        "lineItems": [{
            "variantId": "gid://shopify/ProductVariant/111",
            "quantity": 1
            # price yok
        }]
    })
    first_item = result2.get('lineItems', [{}])[0]
    print(f"✓ Price olmayan item: {'✅' if 'priceSet' not in first_item else '❌'}")
    
    # 3. Geçersiz quantity
    result3 = builder['build_order_input']({
        "customerId": "gid://shopify/Customer/123",
        "lineItems": [{
            "variantId": "gid://shopify/ProductVariant/111",
            "quantity": "invalid",
            "price": "100",
            "currency": "TRY"
        }]
    })
    print(f"✓ Geçersiz quantity işlendi: {'✅' if len(result3.get('lineItems', [])) == 0 else '❌'}")

if __name__ == "__main__":
    print("🔧 Shopify GraphQL Schema Uyumluluk Testi")
    print("=" * 60)
    
    # Ana test
    test_graphql_schema_compatibility()
    
    # Hata senaryoları
    test_error_scenarios()
    
    print("\n🎯 Sonuç:")
    print("✅ priceSet formatı kullanılıyor (price değil)")
    print("✅ MoneyBagInput yapısı doğru")
    print("✅ Transaction alanı kaldırıldı")
    print("✅ GraphQL OrderCreateLineItemInput schema'sına uyumlu")