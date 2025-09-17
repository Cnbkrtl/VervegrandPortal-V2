# operations/smart_rate_limiter.py - YENİ DOSYA

import time
import threading
import logging
from collections import deque

class SmartRateLimiter:
    """
    Token bucket algoritması ile akıllı rate limiting
    """
    def __init__(self, max_requests_per_second=2.0, burst_capacity=10):
        self.max_rate = max_requests_per_second  # Saniyede maksimum istek
        self.burst_capacity = burst_capacity     # Burst modunda max istek
        self.tokens = burst_capacity            # Mevcut token sayısı
        self.last_refill = time.time()
        self.lock = threading.Lock()
        
        # Shopify'a özel ayarlar
        self.request_history = deque(maxlen=100)
        self.throttle_detected = False
        self.backoff_until = 0
    
    def acquire(self, tokens_needed=1):
        """Token al, gerekirse bekle"""
        with self.lock:
            now = time.time()
            
            # Backoff durumu kontrolü
            if now < self.backoff_until:
                wait_time = self.backoff_until - now
                time.sleep(wait_time)
                now = time.time()
            
            # Token yenileme
            self._refill_tokens(now)
            
            # Token yeterli mi?
            if self.tokens >= tokens_needed:
                self.tokens -= tokens_needed
                self._record_request(now)
                return True
            
            # Token yetersiz, bekle
            wait_time = tokens_needed / self.max_rate
            time.sleep(wait_time)
            self.tokens = max(0, self.tokens - tokens_needed)
            self._record_request(now + wait_time)
            return True
    
    def _refill_tokens(self, now):
        """Token bucket'ını doldur"""
        elapsed = now - self.last_refill
        new_tokens = elapsed * self.max_rate
        self.tokens = min(self.burst_capacity, self.tokens + new_tokens)
        self.last_refill = now
    
    def _record_request(self, timestamp):
        """İsteği kaydet ve throttle tespiti yap"""
        self.request_history.append(timestamp)
        
        # Son 1 dakikada çok fazla 429 hatası alındı mı?
        recent_requests = [t for t in self.request_history if timestamp - t < 60]
        if len(recent_requests) > 40:  # Dakikada 40+ istek = risk
            self.throttle_detected = True
            self.max_rate = max(0.5, self.max_rate * 0.8)  # Hızı düşür
    
    def handle_throttle_error(self):
        """429 hatası geldiğinde çağrılır"""
        with self.lock:
            self.throttle_detected = True
            self.backoff_until = time.time() + 30  # 30 saniye backoff
            self.max_rate = max(0.3, self.max_rate * 0.5)  # Hızı yarıya düşür
            logging.warning(f"Rate limit detected! Reduced rate to {self.max_rate} req/sec")
    
    def handle_success(self):
        """Başarılı istek sonrası çağrılır"""
        if self.throttle_detected:
            # Yavaşça hızı artır
            self.max_rate = min(2.0, self.max_rate * 1.1)
            if self.max_rate > 1.5:
                self.throttle_detected = False