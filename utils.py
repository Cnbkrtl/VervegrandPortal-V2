# utils.py

import re

def get_apparel_sort_key(size_str):
    """Giyim bedenlerini mantıksal olarak sıralamak için bir anahtar üretir."""
    if not isinstance(size_str, str): return (3, 9999, size_str)
    size_upper = size_str.strip().upper()
    size_order_map = {'XXS': 0, 'XS': 1, 'S': 2, 'M': 3, 'L': 4, 'XL': 5, 'XXL': 6, '2XL': 6, '3XL': 7, 'XXXL': 7, '4XL': 8, 'XXXXL': 8, '5XL': 9, 'XXXXXL': 9, 'TEK EBAT': 100, 'STANDART': 100}
    if size_upper in size_order_map: return (1, size_order_map[size_upper], size_str)
    numbers = re.findall(r'\d+', size_str)
    if numbers: return (2, int(numbers[0]), size_str)
    return (3, 9999, size_str)

def get_variant_size(variant_data):
    """Varyant verisinden beden bilgisini alır. Sadece 'model' nesnesini kontrol eder."""
    if not isinstance(variant_data, dict):
        return None
    
    model = variant_data.get('model')
    if isinstance(model, dict) and model.get('name', '').lower() == 'beden':
        value = model.get('value')
        return str(value).strip() if value is not None else None
        
    return None

def get_variant_color(variant_data):
    """Varyant verisinden renk bilgisini alır. Hem 'color' anahtarını hem de 'model' nesnesini kontrol eder."""
    if not isinstance(variant_data, dict):
        return None

    # 1. Öncelikli olarak doğrudan 'color' anahtarını kontrol et
    if color := variant_data.get('color'):
        return str(color).strip()

    # 2. 'color' anahtarı yoksa 'model' nesnesini kontrol et
    if model := variant_data.get('model'):
        if isinstance(model, dict) and model.get('name', '').lower() == 'renk':
            value = model.get('value')
            return str(value).strip() if value is not None else None
            
    return None