#!/usr/bin/env python3
"""
Shopify OrderCreateOrderInput Schema Helper
Doğru field formatlarını sağlar
"""

def create_order_input_builder():
    """
    OrderCreateOrderInput için safe builder
    Shopify GraphQL schema'sına uygun format
    """
    
    def build_mailing_address(address_data):
        """MailingAddressInput formatında adres oluşturur"""
        if not address_data:
            return None
            
        # name field'ını firstName/lastName'e ayır
        full_name = address_data.get('name', '')
        first_name = address_data.get('firstName', '')
        last_name = address_data.get('lastName', '')
        
        if full_name and not first_name:
            name_parts = full_name.strip().split(' ', 1)
            first_name = name_parts[0] if name_parts else ''
            last_name = name_parts[1] if len(name_parts) > 1 else ''
        
        # Null değerleri temizle
        address = {}
        if first_name:
            address["firstName"] = first_name
        if last_name:
            address["lastName"] = last_name
        if address_data.get('address1'):
            address["address1"] = address_data.get('address1')
        if address_data.get('address2'):
            address["address2"] = address_data.get('address2')
        if address_data.get('city'):
            address["city"] = address_data.get('city')
        if address_data.get('province'):
            address["province"] = address_data.get('province')
        if address_data.get('zip'):
            address["zip"] = address_data.get('zip')
        if address_data.get('country'):
            address["country"] = address_data.get('country')
        if address_data.get('phone'):
            address["phone"] = address_data.get('phone')
            
        return address if address else None
    
    def build_transaction(transaction_data):
        """OrderCreateOrderTransactionInput formatında transaction oluşturur"""
        if not transaction_data:
            return None
            
        amount = transaction_data.get('amount', '0')
        currency = transaction_data.get('currency', 'TRY')
        
        transaction = {
            "gateway": transaction_data.get('gateway', 'manual'),
            "kind": transaction_data.get('kind', 'SALE'),
            "status": transaction_data.get('status', 'SUCCESS')
        }
        
        # amountSet formatı - amount yerine
        if amount:
            transaction["amountSet"] = {
                "shopMoney": {
                    "amount": str(amount),
                    "currencyCode": currency
                }
            }
        
        return transaction
    
    def build_line_item(line_item_data):
        """OrderCreateOrderLineItemInput formatında line item oluşturur"""
        if not line_item_data:
            return None
            
        line_item = {}
        
        if line_item_data.get('variantId'):
            line_item["variantId"] = line_item_data.get('variantId')
        
        # Quantity - güvenli dönüşüm
        if line_item_data.get('quantity'):
            try:
                quantity = int(line_item_data.get('quantity'))
                if quantity > 0:
                    line_item["quantity"] = quantity
            except (ValueError, TypeError):
                # Geçersiz quantity, line item'ı oluşturma
                return None
        
        # Price - priceSet formatında
        if line_item_data.get('price'):
            try:
                price = float(line_item_data.get('price'))
                if price > 0:
                    line_item["priceSet"] = {
                        "shopMoney": {
                            "amount": str(price),
                            "currencyCode": line_item_data.get('currency', 'TRY')
                        }
                    }
            except (ValueError, TypeError):
                # Geçersiz price, devam et ama priceSet ekleme
                pass
            
        return line_item if line_item else None
    
    def build_order_input(order_data):
        """Tam OrderCreateOrderInput oluşturur"""
        order_input = {}
        
        # Customer ID
        if order_data.get('customerId'):
            order_input["customerId"] = order_data.get('customerId')
        
        # Line Items
        line_items_data = order_data.get('lineItems', [])
        if line_items_data:
            line_items = []
            for item_data in line_items_data:
                item = build_line_item(item_data)
                if item:
                    line_items.append(item)
            if line_items:
                order_input["lineItems"] = line_items
        
        # Shipping Address
        shipping_address = build_mailing_address(order_data.get('shippingAddress'))
        if shipping_address:
            order_input["shippingAddress"] = shipping_address
        
        # Billing Address (opsiyonel)
        billing_address = build_mailing_address(order_data.get('billingAddress'))
        if billing_address:
            order_input["billingAddress"] = billing_address
        
        # Note
        if order_data.get('note'):
            order_input["note"] = order_data.get('note')
        
        # Transactions (opsiyonel - belirtilmezse Shopify otomatik hesaplar)
        transactions_data = order_data.get('transactions', [])
        if transactions_data:
            transactions = []
            for trans_data in transactions_data:
                trans = build_transaction(trans_data)
                if trans:
                    transactions.append(trans)
            if transactions:
                order_input["transactions"] = transactions
        # NOT: Transaction verilmezse Shopify line item'lardan toplam hesaplar
        
        # Email
        if order_data.get('email'):
            order_input["email"] = order_data.get('email')
        
        return order_input
    
    return {
        'build_order_input': build_order_input,
        'build_mailing_address': build_mailing_address,
        'build_transaction': build_transaction,
        'build_line_item': build_line_item
    }

def test_builder():
    """Builder'ı test eder"""
    builder = create_order_input_builder()
    
    # Test data
    test_data = {
        "customerId": "gid://shopify/Customer/123456789",
        "lineItems": [
            {
                "variantId": "gid://shopify/ProductVariant/987654321",
                "quantity": 2,
                "price": "29.99"
            }
        ],
        "shippingAddress": {
            "name": "John Doe",
            "address1": "123 Test St",
            "city": "Istanbul",
            "country": "Turkey",
            "phone": "+905551234567"
        },
        "note": "Test order",
        "transactions": [
            {
                "gateway": "manual",
                "amount": "59.98",
                "currency": "TRY"
            }
        ],
        "email": "test@example.com"
    }
    
    result = builder['build_order_input'](test_data)
    
    print("🧪 Test Result:")
    import json
    print(json.dumps(result, indent=2))
    
    return result

if __name__ == "__main__":
    print("🔧 Shopify OrderCreateOrderInput Builder Test")
    print("=" * 50)
    test_builder()