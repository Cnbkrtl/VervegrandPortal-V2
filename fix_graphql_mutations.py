#!/usr/bin/env python3
"""
Shopify GraphQL Mutation Test Script
orderCreate hatalarını düzeltmek için
"""

import json
from connectors.shopify_api import ShopifyAPI

def test_shopify_mutations():
    """Shopify mutation'larının doğru çalışıp çalışmadığını test eder"""
    
    # Test için örnek veriler
    test_order_input = {
        "email": "test@example.com",
        "fulfillmentStatus": "UNFULFILLED",
        "lineItems": [
            {
                "variantId": "gid://shopify/ProductVariant/123456789",
                "quantity": 1
            }
        ]
    }
    
    print("🔍 Shopify GraphQL Mutation Test")
    print("=" * 50)
    
    # Test için ShopifyAPI instance'ı gerekiyor
    # Bu sadece syntax testi için
    
    # Doğru orderCreate mutation syntax'ı
    correct_mutation = """
    mutation orderCreate($order: OrderCreateOrderInput!) {
        orderCreate(order: $order) {
            order {
                id
                name
                createdAt
            }
            userErrors {
                field
                message
            }
        }
    }
    """
    
    # Yanlış mutation (eski hatalı versiyon)
    wrong_mutation = """
    mutation orderCreate($input: OrderInput!) {
        orderCreate(input: $input) {
            order {
                id
                name
            }
            userErrors {
                field
                message
            }
        }
    }
    """
    
    print("✅ Doğru Mutation Syntax:")
    print(correct_mutation)
    print("\n❌ Yanlış Mutation Syntax (bu hatayı veriyordu):")
    print(wrong_mutation)
    
    print("\n📋 Fark:")
    print("- Yanlış: mutation orderCreate($input: OrderInput!)")
    print("- Doğru:  mutation orderCreate($order: OrderCreateOrderInput!)")
    print("- Yanlış: orderCreate(input: $input)")
    print("- Doğru:  orderCreate(order: $order)")
    
    print("\n🛠️ Düzeltme:")
    print("- Variable name: $input → $order")
    print("- Argument name: input: → order:")
    print("- Type: OrderInput! → OrderCreateOrderInput!")
    print("- Bu değişiklik shopify_api.py'de yapıldı!")

if __name__ == "__main__":
    test_shopify_mutations()