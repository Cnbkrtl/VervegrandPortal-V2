# operations/shopify_to_shopify.py

import logging
from .shopify_order_builder import create_order_input_builder

def find_or_create_customer(destination_api, source_customer):
    """Hedef mağazada müşteriyi e-postaya göre arar, bulamazsa yenisini oluşturur."""
    if not source_customer or not source_customer.get('email'):
        raise Exception("Kaynak siparişte müşteri e-postası bulunamadı.")
    
    email = source_customer['email']
    customer_id = destination_api.find_customer_by_email(email)
    
    if customer_id:
        logging.info(f"Mevcut müşteri bulundu: {email}")
        return customer_id
    else:
        new_customer_id = destination_api.create_customer(source_customer)
        logging.info(f"Yeni müşteri oluşturuldu: {email}")
        return new_customer_id

def map_line_items(destination_api, source_line_items):
    """Kaynak mağazadaki ürünleri SKU'larına göre hedef mağazadaki varyant ID'leri ile eşleştirir."""
    line_items_for_creation = []
    logs = []
    
    for item in source_line_items:
        sku = (item.get('variant') or {}).get('sku')
        if not sku:
            logs.append(f"UYARI: '{item.get('title')}' ürününde SKU bulunamadı, siparişe eklenemiyor.")
            continue
        
        variant_id = destination_api.find_variant_id_by_sku(sku)
        if variant_id:
            # İndirimli fiyatı hesapla
            # discountedTotal = originalUnitPrice - discountAllocations
            original_price = float(item.get('originalUnitPriceSet', {}).get('shopMoney', {}).get('amount', '0'))
            discounted_price = float(item.get('discountedUnitPriceSet', {}).get('shopMoney', {}).get('amount', '0'))
            
            # Eğer indirimli fiyat yoksa, orijinal fiyatı kullan
            final_price = discounted_price if discounted_price > 0 else original_price
            
            line_item = {
                "variantId": variant_id,
                "quantity": item.get('quantity')
            }
            
            # Eğer indirimli fiyat varsa, onu da ekle (para birimi ile birlikte)
            if final_price > 0:
                line_item["price"] = str(final_price)
                # Para birimi bilgisini de ekle (priceSet için gerekli)
                currency = item.get('originalUnitPriceSet', {}).get('shopMoney', {}).get('currencyCode', 'TRY')
                line_item["currency"] = currency
            
            line_items_for_creation.append(line_item)
            logs.append(f"Ürün eşleştirildi: SKU {sku}, Miktar: {item.get('quantity')}, Fiyat: ₺{final_price:.2f}")
        else:
            logs.append(f"HATA: SKU '{sku}' hedef mağazada bulunamadı.")
            
    return line_items_for_creation, logs

def transfer_order(source_api, destination_api, order_data):
    """
    Bir siparişi kaynak mağazadan alır ve hedef mağazada oluşturur.
    """
    log_messages = []
    
    try:
        # 1. Müşteriyi Hedef Mağazada Bul veya Oluştur
        customer_id = find_or_create_customer(destination_api, order_data.get('customer'))
        log_messages.append(f"Müşteri ID'si '{customer_id}' olarak belirlendi.")
        
        # 2. Ürün Satırlarını Eşleştir
        line_items, mapping_logs = map_line_items(destination_api, order_data.get('lineItems', {}).get('nodes', []))
        log_messages.extend(mapping_logs)

        if not line_items:
            raise Exception("Siparişteki hiçbir ürün hedef mağazada eşleştirilemedi.")

        # 3. Sipariş Verisini Hazırla ve Oluştur
        # Safe order input builder kullan
        builder = create_order_input_builder()
        
        # DÜZELTME: Doğru toplam tutarı hesapla (indirimli)
        # Shopify'da farklı toplam türleri:
        # - totalPriceSet: Orijinal toplam (indirimsiz)
        # - currentTotalPriceSet: Güncel toplam (indirimli)
        # - Manuel hesaplama: currentSubtotalPriceSet - totalDiscountsSet + shipping + tax
        
        # 1. Shopify'ın güncel toplamı (currentTotalPriceSet)
        current_total = float(order_data.get('currentTotalPriceSet', {}).get('shopMoney', {}).get('amount', '0'))
        
        # 2. Shopify'ın orijinal toplamı (totalPriceSet)
        original_total = float(order_data.get('totalPriceSet', {}).get('shopMoney', {}).get('amount', '0'))
        
        # 3. Manuel hesaplama
        subtotal = float(order_data.get('currentSubtotalPriceSet', {}).get('shopMoney', {}).get('amount', '0'))
        discounts = float(order_data.get('totalDiscountsSet', {}).get('shopMoney', {}).get('amount', '0'))
        shipping = float(order_data.get('totalShippingPriceSet', {}).get('shopMoney', {}).get('amount', '0'))
        tax = float(order_data.get('totalTaxSet', {}).get('shopMoney', {}).get('amount', '0'))
        calculated_total = subtotal - discounts + shipping + tax
        
        # 4. Hangi tutarı kullanacağımıza karar ver
        # Eğer currentTotalPriceSet varsa onu kullan (en güvenilir)
        if current_total > 0:
            total_amount = str(current_total)
            source = "currentTotalPriceSet"
        elif calculated_total > 0:
            total_amount = str(calculated_total)
            source = "manuel hesaplama"
        else:
            total_amount = str(original_total)
            source = "totalPriceSet (fallback)"
        
        # Debug bilgileri
        log_messages.append(f"💰 Tutar Analizi:")
        log_messages.append(f"  📊 Orijinal (totalPriceSet): ₺{original_total:.2f}")
        log_messages.append(f"  � Güncel (currentTotalPriceSet): ₺{current_total:.2f}")
        log_messages.append(f"  📊 Manuel (subtotal-indirim+kargo+vergi): ₺{calculated_total:.2f}")
        log_messages.append(f"  � Detay: Subtotal ₺{subtotal:.2f} - İndirim ₺{discounts:.2f} + Kargo ₺{shipping:.2f} + Vergi ₺{tax:.2f}")
        log_messages.append(f"  ✅ Seçilen: ₺{total_amount} ({source})")
        
        # Kaynak veriyi düzenle
        # NOT: Transaction kaldırıldı - Shopify line item'lardan otomatik hesaplasın
        order_data_for_creation = {
            "customerId": customer_id,
            "lineItems": line_items,
            "shippingAddress": order_data.get('shippingAddress', {}),
            "note": f"Kaynak Mağazadan Aktarılan Sipariş. Orijinal Sipariş No: {order_data.get('name')} | Net Tutar: ₺{total_amount}",
            "email": order_data.get('customer', {}).get('email')
        }
        
        # Safe builder ile OrderCreateOrderInput oluştur
        order_input = builder['build_order_input'](order_data_for_creation)
        
        new_order = destination_api.create_order(order_input)
        log_messages.append(f"✅ BAŞARILI: Sipariş, hedef mağazada '{new_order.get('name')}' numarasıyla oluşturuldu.")
        
        return {"success": True, "logs": log_messages, "new_order_name": new_order.get('name')}

    except Exception as e:
        logging.error(f"Sipariş aktarımında kritik hata: {e}", exc_info=True)
        log_messages.append(f"❌ KRİTİK HATA: {str(e)}")
        return {"success": False, "logs": log_messages}