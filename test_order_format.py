#!/usr/bin/env python3
"""
Shopify OrderCreateOrderInput Validation Test
Field format hatalarını kontrol eder
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from operations.shopify_order_builder import create_order_input_builder

def test_order_input_format():
    """OrderCreateOrderInput formatını test eder"""
    
    print("🧪 Shopify OrderCreateOrderInput Format Testi")
    print("=" * 60)
    
    builder = create_order_input_builder()
    
    # Hatalı veri örneği (önceki format)
    problematic_data = {
        "customerId": "gid://shopify/Customer/8536418189490",
        "lineItems": [
            {
                "variantId": "gid://shopify/ProductVariant/46153432727730",
                "quantity": 2
            }
        ],
        "shippingAddress": {
            "name": "Delfin Kablan",  # ❌ Bu field MailingAddressInput'ta yok
            "address1": "Birlik mahallesi 802. Sokak No:4/Z",
            "city": "Esenler / İstanbul",
            "country": "Turkey",
            "countryCodeV2": "TR",  # ❌ Bu field MailingAddressInput'ta yok
            "phone": "+905360591034"
        },
        "transactions": [
            {
                "gateway": "manual",
                "amount": "28197.0",  # ❌ amount field yok, amountSet gerekli
                "kind": "SALE",
                "status": "SUCCESS"
            }
        ]
    }
    
    print("❌ Problematic Input:")
    import json
    print(json.dumps(problematic_data, indent=2))
    
    print("\n🔧 Builder ile düzeltiliyor...")
    corrected_input = builder['build_order_input'](problematic_data)
    
    print("\n✅ Corrected Input:")
    print(json.dumps(corrected_input, indent=2))
    
    # Validation kontrolleri
    print("\n🔍 Validation Kontrolleri:")
    
    checks = [
        ("shippingAddress.name yokluğu", "name" not in corrected_input.get("shippingAddress", {})),
        ("shippingAddress.firstName varlığı", "firstName" in corrected_input.get("shippingAddress", {})),
        ("shippingAddress.lastName varlığı", "lastName" in corrected_input.get("shippingAddress", {})),
        ("countryCodeV2 yokluğu", "countryCodeV2" not in corrected_input.get("shippingAddress", {})),
        ("transactions.amountSet varlığı", any("amountSet" in t for t in corrected_input.get("transactions", []))),
        ("transactions.amount yokluğu", not any("amount" in t for t in corrected_input.get("transactions", []))),
    ]
    
    all_passed = True
    for check_name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {check_name}: {status}")
        if not result:
            all_passed = False
    
    print(f"\n🎯 Sonuç: {'✅ TÜM KONTROLLER BAŞARILI' if all_passed else '❌ BAZI KONTROLLER BAŞARISIZ'}")
    
    return all_passed

def test_name_parsing():
    """Name field parsing'ini test eder"""
    
    print("\n" + "=" * 60)
    print("🔤 Name Field Parsing Testi")
    print("=" * 60)
    
    builder = create_order_input_builder()
    
    test_cases = [
        {"name": "John Doe"},
        {"name": "Ahmet Can Bakırtel"},
        {"name": "Ayşe"},
        {"firstName": "John", "lastName": "Doe"},
        {"name": ""}
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\nTest {i}: {case}")
        result = builder['build_mailing_address'](case)
        print(f"Result: {result}")
    
    return True

if __name__ == "__main__":
    print("🚀 Shopify Field Format Validation")
    print("OrderCreateOrderInput hatalarını çözme testi\n")
    
    try:
        success1 = test_order_input_format()
        success2 = test_name_parsing()
        
        if success1 and success2:
            print("\n🎉 TÜM TESTLER BAŞARILI!")
            print("Field format hataları çözüldü!")
        else:
            print("\n❌ BAZI TESTLER BAŞARISIZ!")
            
    except Exception as e:
        print(f"\n💥 Test hatası: {e}")
        import traceback
        traceback.print_exc()