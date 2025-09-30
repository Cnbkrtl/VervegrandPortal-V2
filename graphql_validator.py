#!/usr/bin/env python3
"""
GraphQL Mutation Validator
Shopify API mutation'larını doğrular ve yaygın hataları yakalar
"""

import re
import json

class GraphQLMutationValidator:
    """Shopify GraphQL mutation'larını doğrular"""
    
    # Shopify'da doğru argument patterns
    SHOPIFY_MUTATION_PATTERNS = {
        'orderCreate': r'orderCreate\s*\(\s*order\s*:\s*\$\w+\s*\)',
        'productCreate': r'productCreate\s*\(\s*input\s*:\s*\$\w+\s*\)',
        'productUpdate': r'productUpdate\s*\(\s*input\s*:\s*\$\w+\s*\)',
        'customerCreate': r'customerCreate\s*\(\s*input\s*:\s*\$\w+\s*\)',
        'customerUpdate': r'customerUpdate\s*\(\s*input\s*:\s*\$\w+\s*\)',
        'metafieldDefinitionCreate': r'metafieldDefinitionCreate\s*\(\s*definition\s*:\s*\$\w+\s*\)',
        'inventorySetOnHandQuantities': r'inventorySetOnHandQuantities\s*\(\s*input\s*:\s*\$\w+\s*\)'
    }
    
    # Shopify'da doğru type patterns
    SHOPIFY_TYPE_PATTERNS = {
        'orderCreate': r'\$\w+\s*:\s*OrderCreateOrderInput!',
        'productCreate': r'\$\w+\s*:\s*ProductInput!',
        'productUpdate': r'\$\w+\s*:\s*ProductUpdateInput!',
        'customerCreate': r'\$\w+\s*:\s*CustomerInput!',
        'customerUpdate': r'\$\w+\s*:\s*CustomerUpdateInput!',
        'metafieldDefinitionCreate': r'\$\w+\s*:\s*MetafieldDefinitionInput!',
        'inventorySetOnHandQuantities': r'\$\w+\s*:\s*InventorySetOnHandQuantitiesInput!'
    }
    
    # Yaygın hatalar
    COMMON_ERRORS = [
        (r'orderCreate\s*\(\s*input\s*:', 'orderCreate(input: -> orderCreate(order:'),
        (r'\$input\s*:\s*OrderInput', '$input: OrderInput -> $order: OrderCreateOrderInput'),
        (r'\$order\s*:\s*OrderInput!', '$order: OrderInput! -> $order: OrderCreateOrderInput!'),
    ]
    
    def validate_mutation(self, mutation_string):
        """Bir mutation string'ini doğrular"""
        errors = []
        warnings = []
        suggestions = []
        
        # Mutation type'ını bul
        mutation_match = re.search(r'mutation\s+(\w+)', mutation_string)
        if not mutation_match:
            errors.append("Mutation tanımı bulunamadı")
            return {'valid': False, 'errors': errors, 'warnings': warnings, 'suggestions': suggestions}
            
        # Mutation içeriğindeki field'ları bul
        field_matches = re.findall(r'(\w+)\s*\([^)]*\)', mutation_string)
        
        for field in field_matches:
            if field in self.SHOPIFY_MUTATION_PATTERNS:
                pattern = self.SHOPIFY_MUTATION_PATTERNS[field]
                if not re.search(pattern, mutation_string):
                    errors.append(f"'{field}' mutation'ı yanlış syntax'a sahip")
                    
                    # Önerileri ekle
                    if field == 'orderCreate':
                        if 'input:' in mutation_string:
                            suggestions.append("orderCreate için 'input:' yerine 'order:' kullanın")
                        if '$input' in mutation_string:
                            suggestions.append("orderCreate için '$input' yerine '$order' kullanın")
                
                # Type kontrolü
                if field in self.SHOPIFY_TYPE_PATTERNS:
                    type_pattern = self.SHOPIFY_TYPE_PATTERNS[field]
                    if not re.search(type_pattern, mutation_string):
                        errors.append(f"'{field}' mutation'ı yanlış type kullanıyor")
                        
                        if field == 'orderCreate':
                            if 'OrderInput!' in mutation_string:
                                suggestions.append("orderCreate için 'OrderInput!' yerine 'OrderCreateOrderInput!' kullanın")
        
        # Yaygın hataları kontrol et
        for error_pattern, suggestion in self.COMMON_ERRORS:
            if re.search(error_pattern, mutation_string):
                warnings.append(f"Yaygın hata tespit edildi: {suggestion}")
        
        # Variable declarations kontrol et
        var_declarations = re.findall(r'\$(\w+)\s*:\s*(\w+!?)', mutation_string)
        mutation_calls = re.findall(r'\w+\s*\([^)]*\$(\w+)[^)]*\)', mutation_string)
        
        declared_vars = {var[0] for var in var_declarations}
        used_vars = set(mutation_calls)
        
        unused_vars = declared_vars - used_vars
        if unused_vars:
            errors.append(f"Kullanılmayan değişkenler: {', '.join(unused_vars)}")
            
        undeclared_vars = used_vars - declared_vars
        if undeclared_vars:
            errors.append(f"Tanımlanmamış değişkenler: {', '.join(undeclared_vars)}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'suggestions': suggestions,
            'mutation_fields': field_matches,
            'variables': dict(var_declarations)
        }
    
    def fix_common_issues(self, mutation_string):
        """Yaygın hataları otomatik olarak düzeltir"""
        fixed = mutation_string
        
        # orderCreate hatalarını düzelt
        if 'orderCreate' in fixed:
            # input: -> order:
            fixed = re.sub(r'orderCreate\s*\(\s*input\s*:', 'orderCreate(order:', fixed)
            # $input: OrderInput -> $order: OrderCreateOrderInput
            fixed = re.sub(r'\$input\s*:\s*OrderInput', '$order: OrderCreateOrderInput', fixed)
            # $order: OrderInput! -> $order: OrderCreateOrderInput!
            fixed = re.sub(r'\$order\s*:\s*OrderInput!', '$order: OrderCreateOrderInput!', fixed)
        
        return fixed
    
    def get_mutation_examples(self):
        """Doğru mutation örnekleri döndürür"""
        return {
            'orderCreate': '''
mutation orderCreate($order: OrderCreateOrderInput!) {
    orderCreate(order: $order) {
        order {
            id
            name
            createdAt
            totalPrice
        }
        userErrors {
            field
            message
        }
    }
}''',
            'productCreate': '''
mutation productCreate($input: ProductInput!) {
    productCreate(input: $input) {
        product {
            id
            title
        }
        userErrors {
            field
            message
        }
    }
}''',
            'customerCreate': '''
mutation customerCreate($input: CustomerInput!) {
    customerCreate(input: $input) {
        customer {
            id
            email
        }
        userErrors {
            field
            message
        }
    }
}'''
        }

def main():
    """Test ve örnek kullanım"""
    validator = GraphQLMutationValidator()
    
    print("🔍 GraphQL Mutation Validator Test")
    print("=" * 50)
    
    # Hatalı mutation testi
    wrong_mutation = '''
    mutation orderCreate($input: OrderInput!) {
        orderCreate(input: $input) {
            order { id name }
            userErrors { field message }
        }
    }
    '''
    
    print("❌ Hatalı Mutation Test:")
    result = validator.validate_mutation(wrong_mutation)
    print(f"Valid: {result['valid']}")
    if result['errors']:
        print("Errors:")
        for error in result['errors']:
            print(f"  - {error}")
    if result['suggestions']:
        print("Suggestions:")
        for suggestion in result['suggestions']:
            print(f"  - {suggestion}")
    
    print("\n🔧 Otomatik Düzeltme:")
    fixed = validator.fix_common_issues(wrong_mutation)
    print(fixed)
    
    print("\n✅ Düzeltilmiş Mutation Test:")
    result2 = validator.validate_mutation(fixed)
    print(f"Valid: {result2['valid']}")
    
    print("\n📚 Doğru Örnekler:")
    examples = validator.get_mutation_examples()
    for name, example in examples.items():
        print(f"\n{name}:")
        print(example)

if __name__ == "__main__":
    main()