#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API gợi ý giá cho hệ thống Mine
Sử dụng web scraping để thu thập dữ liệu từ các trang bán đồ cũ
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
import time
import json
import urllib.parse
from urllib.parse import quote
from typing import List, Dict, Optional
import statistics
import unicodedata
import logging
from urllib.parse import quote
import random
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PriceSuggestionEngine:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.cache = {}  # Cache kết quả trong 1 giờ
        self.cache_duration = 3600  # 1 giờ
        
        # Mapping tình trạng sản phẩm với % giá
        self.condition_multipliers = {
            'moi': 0.95,  # Mới: 95% giá thị trường (đồ cũ)
            'nhu-moi': 0.85,  # Như mới: 85%
            '99%': 0.80,  # 99%: 80%
            'con-bao-hanh': 0.75,  # Còn bảo hành: 75%
            'het-bao-hanh': 0.65   # Hết bảo hành: 65%
        }
        
        # Cấu hình nguồn dữ liệu theo danh mục
        self.data_sources = {
            'electronics': {
                'name': 'Đồ điện tử',
                'sources': [
                    {
                        'name': 'Phong Vũ',
                        'base_url': 'https://phongvu.vn',
                        'search_url': 'https://phongvu.vn/tim-kiem?q={query}',
                        'price_selector': '.price-current',
                        'title_selector': '.product-name',
                        'active': True
                    },
                    {
                        'name': 'CellphoneS',
                        'base_url': 'https://cellphones.com.vn',
                        'search_url': 'https://cellphones.com.vn/tim-kiem?q={query}',
                        'price_selector': '.product-price',
                        'title_selector': '.product-name',
                        'active': True
                    },
                    {
                        'name': 'Thế Giới Di Động',
                        'base_url': 'https://thegioididong.com',
                        'search_url': 'https://thegioididong.com/tim-kiem?q={query}',
                        'price_selector': '.price',
                        'title_selector': '.name',
                        'active': True
                    }
                ]
            },
            'home_appliances': {
                'name': 'Đồ gia dụng & Nội thất',
                'sources': [
                    {
                        'name': 'Điện Máy Xanh',
                        'base_url': 'https://dienmayxanh.com',
                        'search_url': 'https://dienmayxanh.com/tim-kiem?q={query}',
                        'price_selector': '.price',
                        'title_selector': '.name',
                        'active': True
                    },
                    {
                        'name': 'Nguyễn Kim',
                        'base_url': 'https://nguyenkim.com',
                        'search_url': 'https://nguyenkim.com/tim-kiem?q={query}',
                        'price_selector': '.product-price',
                        'title_selector': '.product-name',
                        'active': True
                    },
                    {
                        'name': 'Tiki Gia Dụng',
                        'base_url': 'https://tiki.vn',
                        'search_url': 'https://tiki.vn/tim-kiem?q={query}&category=1882',
                        'price_selector': '.product-price',
                        'title_selector': '.product-name',
                        'active': True
                    }
                ]
            },
            'fashion': {
                'name': 'Thời trang & Phụ kiện',
                'sources': [
                    {
                        'name': 'ZALORA',
                        'base_url': 'https://zalora.vn',
                        'search_url': 'https://zalora.vn/tim-kiem/?q={query}',
                        'price_selector': '.price-current',
                        'title_selector': '.product-name',
                        'active': True
                    },
                    {
                        'name': 'Lazada Fashion',
                        'base_url': 'https://lazada.vn',
                        'search_url': 'https://lazada.vn/tim-kiem/?q={query}&from=input&spm=a2o4n.searchlist.search.go.2b2a52e6wHjsE7',
                        'price_selector': '.pdp-price',
                        'title_selector': '.pdp-product-name',
                        'active': True
                    },
                    {
                        'name': 'Shopee Fashion',
                        'base_url': 'https://shopee.vn',
                        'search_url': 'https://shopee.vn/search?keyword={query}&category=17',
                        'price_selector': '.shopee-price',
                        'title_selector': '.shopee-item-name',
                        'active': True
                    }
                ]
            },
            'vehicles': {
                'name': 'Xe cộ & Phương tiện',
                'sources': [
                    {
                        'name': 'Oto.com.vn',
                        'base_url': 'https://oto.com.vn',
                        'search_url': 'https://oto.com.vn/tim-kiem?q={query}',
                        'price_selector': '.price',
                        'title_selector': '.car-name',
                        'active': True
                    },
                    {
                        'name': 'Chợ Tốt Xe',
                        'base_url': 'https://xe.chotot.com',
                        'search_url': 'https://xe.chotot.com/tim-kiem?q={query}',
                        'price_selector': '.ad-price',
                        'title_selector': '.ad-title',
                        'active': True
                    }
                ]
            },
            'real_estate': {
                'name': 'Bất động sản',
                'sources': [
                    {
                        'name': 'Batdongsan.com.vn',
                        'base_url': 'https://batdongsan.com.vn',
                        'search_url': 'https://batdongsan.com.vn/tim-kiem?q={query}',
                        'price_selector': '.price',
                        'title_selector': '.product-title',
                        'active': True
                    }
                ]
            },
            'beauty_health': {
                'name': 'Sức khỏe & Làm đẹp',
                'sources': [
                    {
                        'name': 'Watsons Vietnam',
                        'base_url': 'https://watsons.vn',
                        'search_url': 'https://watsons.vn/tim-kiem?q={query}',
                        'price_selector': '.price',
                        'title_selector': '.product-name',
                        'active': True
                    }
                ]
            }
        }
        
        # Keywords để tự động phân loại sản phẩm
        self.category_keywords = {
            'electronics': [
                'iphone', 'samsung', 'laptop', 'macbook', 'ipad', 'airpods', 
                'watch', 'camera', 'ps5', 'xbox', 'nintendo', 'smartphone',
                'tablet', 'computer', 'mouse', 'keyboard', 'headphone', 'speaker'
            ],
            'home_appliances': [
                'tủ lạnh', 'máy giặt', 'điều hòa', 'ti vi', 'tv', 'lò vi sóng',
                'nồi cơm điện', 'máy lọc nước', 'quạt', 'bàn ghế', 'giường',
                'tủ quần áo', 'sofa', 'bàn ăn'
            ],
            'fashion': [
                'áo', 'quần', 'váy', 'giày', 'túi xách', 'đồng hồ', 'kính',
                'trang sức', 'thắt lưng', 'mũ', 'áo khoác', 'dress', 'shirt'
            ],
            'vehicles': [
                'xe máy', 'ô tô', 'xe hơi', 'xe đạp', 'honda', 'yamaha',
                'toyota', 'hyundai', 'mazda', 'ford', 'vinfast'
            ],
            'real_estate': [
                'nhà', 'căn hộ', 'chung cư', 'đất', 'villa', 'biệt thự',
                'mặt bằng', 'văn phòng'
            ],
            'beauty_health': [
                'mỹ phẩm', 'kem dưỡng', 'sữa rửa mặt', 'son', 'phấn',
                'nước hoa', 'thuốc', 'vitamin', 'thực phẩm chức năng'
            ]
        }
    
    def normalize_text(self, text: str) -> str:
        """Chuẩn hóa text để so sánh"""
        if not text:
            return ""
        
        # Loại bỏ dấu tiếng Việt
        text = unicodedata.normalize('NFD', text)
        text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')
        
        # Chuyển về lowercase và loại bỏ ký tự đặc biệt
        text = re.sub(r'[^\w\s]', '', text.lower())
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def detect_product_category(self, product_name: str) -> str:
        """Tự động phát hiện danh mục sản phẩm dựa trên tên"""
        normalized_name = self.normalize_text(product_name)
        
        # Đếm số keywords khớp cho mỗi category
        category_scores = {}
        for category, keywords in self.category_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword in normalized_name:
                    score += 1
            category_scores[category] = score
        
        # Trả về category có điểm cao nhất
        if category_scores:
            best_category = max(category_scores, key=category_scores.get)
            if category_scores[best_category] > 0:
                logger.info(f"Detected category: {best_category} for product: {product_name}")
                return best_category
        
        # Mặc định là electronics nếu không xác định được
        logger.info(f"Default category: electronics for product: {product_name}")
        return 'electronics'
    
    def scrape_official_store(self, source_config: dict, product_name: str, limit: int = 5) -> List[Dict]:
        """Thu thập dữ liệu từ cửa hàng chính hãng"""
        results = []
        source_name = source_config['name']
        
        try:
            search_url = source_config['search_url'].format(query=quote(product_name))
            logger.info(f"Scraping {source_name}: {search_url}")
            
            response = requests.get(search_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            normalized_query = self.normalize_text(product_name)
            
            # Tìm sản phẩm với selectors cơ bản
            product_containers = self.find_product_containers(soup, source_name)
            
            for container in product_containers[:limit * 2]:  # Lấy nhiều hơn để lọc
                try:
                    title = self.extract_product_title(container, source_config, source_name)
                    price = self.extract_product_price(container, source_config, source_name)
                    
                    if title and price and self.is_similar_product(normalized_query, self.normalize_text(title)):
                        results.append({
                            'title': title,
                            'price': price,
                            'source': source_name,
                            'url': search_url,
                            'type': 'official_store'
                        })
                        
                        if len(results) >= limit:
                            break
                            
                except Exception as e:
                    logger.warning(f"Error parsing item from {source_name}: {e}")
                    continue
            
            logger.info(f"Found {len(results)} items from {source_name}")
            
        except requests.RequestException as e:
            logger.warning(f"Request failed for {source_name}: {e}")
        except Exception as e:
            logger.error(f"Error scraping {source_name}: {e}")
        
        return results
    
    def find_product_containers(self, soup: BeautifulSoup, source_name: str) -> list:
        """Tìm containers chứa sản phẩm cho từng trang web"""
        containers = []
        
        # Common selectors cho các trang web phổ biến
        common_selectors = [
            # Generic product containers
            'div[class*="product"]',
            'div[class*="item"]',
            'div[class*="card"]',
            'article',
            'li[class*="product"]',
            'li[class*="item"]',
            
            # Specific for popular sites
            '.product-item',
            '.item-product',
            '.product-card',
            '.search-result-item',
            '.listing-item'
        ]
        
        for selector in common_selectors:
            try:
                found = soup.select(selector)
                if found and len(found) > 2:  # Phải có ít nhất 3 items để đảm bảo là product list
                    containers = found
                    break
            except Exception:
                continue
        
        return containers[:20]  # Giới hạn 20 items để xử lý
    
    def extract_product_title(self, container, source_config: dict, source_name: str) -> Optional[str]:
        """Trích xuất tên sản phẩm từ container"""
        title_selectors = [
            source_config.get('title_selector', '.product-name'),
            'a[title]',
            'h3', 'h4', 'h5',
            '.title', '.name', '.product-title',
            'a', 'span[title]'
        ]
        
        for selector in title_selectors:
            try:
                elem = container.select_one(selector)
                if elem:
                    title = elem.get_text(strip=True) or elem.get('title', '').strip()
                    if title and len(title) > 5:  # Tên phải có ít nhất 5 ký tự
                        return title
            except Exception:
                continue
        
        return None
    
    def extract_product_price(self, container, source_config: dict, source_name: str) -> Optional[int]:
        """Trích xuất giá sản phẩm từ container"""
        price_selectors = [
            source_config.get('price_selector', '.price'),
            '.price-current', '.current-price',
            '.price-new', '.new-price',
            '.sale-price', '.final-price',
            '[class*="price"]',
            '.cost', '.amount'
        ]
        
        for selector in price_selectors:
            try:
                elem = container.select_one(selector)
                if elem:
                    price_text = elem.get_text(strip=True)
                    price = self.extract_price_from_text(price_text)
                    if price and price > 1000:  # Giá phải > 1000 để hợp lý
                        return price
            except Exception:
                continue
        
        return None
    
    def extract_price_from_text(self, text: str) -> Optional[int]:
        """Trích xuất giá từ text với cải tiến"""
        if not text:
            return None
            
        # Làm sạch text
        text = re.sub(r'[^\d\.,\sktr\s]', ' ', text.lower())
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Tìm các pattern giá phổ biến (cải tiến)
        patterns = [
            # Giá có đơn vị rõ ràng
            r'(\d{1,3}(?:[,\.]\d{3})*)\s*(?:triệu|tr|million)',  # X triệu
            r'(\d{1,3}(?:[,\.]\d{3})*)\s*(?:nghìn|k|thousand)',  # X nghìn
            r'(\d{1,3}(?:[,\.]\d{3})*)\s*(?:tỷ|billion)',       # X tỷ
            
            # Giá với ký hiệu
            r'(\d{1,3}(?:[,\.]\d{3})*)\s*tr(?:\s|$)',           # 15 tr
            r'(\d{1,3}(?:[,\.]\d{3})*)\s*k(?:\s|$)',            # 500 k
            r'(\d{1,3}(?:[,\.]\d{3})*)\s*m(?:\s|$)',            # 15 m (million)
            
            # Giá với đơn vị tiền tệ
            r'(\d{1,3}(?:[,\.]\d{3})*)\s*(?:vnd|vnđ|đồng|dong|d)(?:\s|$)',
            
            # Giá thuần (số lớn)
            r'(\d{1,3}(?:[,\.]\d{3}){2,})',                     # Ít nhất 6 chữ số
            r'(\d{7,})',                                        # Ít nhất 7 chữ số
            
            # Giá nhỏ hơn
            r'(\d{1,3}(?:[,\.]\d{3})*)',                        # Bất kỳ số nào
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                try:
                    price_str = matches[0].replace(',', '').replace('.', '')
                    price = int(price_str)
                    
                    # Xử lý đơn vị
                    if any(unit in text for unit in ['triệu', 'tr', 'million', 'm']):
                        if price < 1000:  # Tránh nhầm lẫn với số lớn
                            price *= 1000000
                    elif any(unit in text for unit in ['tỷ', 'billion']):
                        if price < 100:
                            price *= 1000000000
                    elif any(unit in text for unit in ['nghìn', 'k', 'thousand']):
                        if price < 10000:
                            price *= 1000
                    
                    # Lọc giá hợp lý (từ 1k đến 10 tỷ)
                    if 1000 <= price <= 10000000000:
                        return price
                        
                except (ValueError, OverflowError):
                    continue
        
        return None
    
    def is_similar_product(self, query: str, title: str, min_similarity: float = 0.3) -> bool:
        """Kiểm tra độ tương đồng giữa tên sản phẩm"""
        if not query or not title:
            return False
        
        query_words = set(query.split())
        title_words = set(title.split())
        
        if not query_words or not title_words:
            return False
        
        # Tính toán Jaccard similarity
        intersection = len(query_words.intersection(title_words))
        union = len(query_words.union(title_words))
        
        similarity = intersection / union if union > 0 else 0
        
        return similarity >= min_similarity
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Tìm các pattern giá phổ biến (cải tiến)
        patterns = [
            # Giá có đơn vị rõ ràng
            r'(\d{1,3}(?:[,\.]\d{3})*)\s*(?:triệu|tr|million)',  # X triệu
            r'(\d{1,3}(?:[,\.]\d{3})*)\s*(?:nghìn|k|thousand)',  # X nghìn
            r'(\d{1,3}(?:[,\.]\d{3})*)\s*(?:tỷ|billion)',       # X tỷ
            
            # Giá với ký hiệu
            r'(\d{1,3}(?:[,\.]\d{3})*)\s*tr(?:\s|$)',           # 15 tr
            r'(\d{1,3}(?:[,\.]\d{3})*)\s*k(?:\s|$)',            # 500 k
            r'(\d{1,3}(?:[,\.]\d{3})*)\s*m(?:\s|$)',            # 15 m (million)
            
            # Giá với đơn vị tiền tệ
            r'(\d{1,3}(?:[,\.]\d{3})*)\s*(?:vnd|vnđ|đồng|dong|d)(?:\s|$)',
            
            # Giá thuần (số lớn)
            r'(\d{1,3}(?:[,\.]\d{3}){2,})',                     # Ít nhất 6 chữ số
            r'(\d{7,})',                                        # Ít nhất 7 chữ số
            
            # Giá nhỏ hơn
            r'(\d{1,3}(?:[,\.]\d{3})*)',                        # Bất kỳ số nào
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                try:
                    price_str = matches[0].replace(',', '').replace('.', '')
                    price = int(price_str)
                    
                    # Xử lý đơn vị
                    if any(unit in text for unit in ['triệu', 'tr', 'million', 'm']):
                        if price < 1000:  # Tránh nhầm lẫn với số lớn
                            price *= 1000000
                    elif any(unit in text for unit in ['tỷ', 'billion']):
                        if price < 100:
                            price *= 1000000000
                    elif any(unit in text for unit in ['nghìn', 'k', 'thousand']):
                        if price < 10000:
                            price *= 1000
                    
                    # Lọc giá hợp lý (từ 1k đến 10 tỷ)
                    if 1000 <= price <= 10000000000:
                        return price
                        
                except (ValueError, OverflowError):
                    continue
        
        return None
    
    def scrape_official_store(self, store_config: Dict, query: str, limit: int = 10) -> List[Dict]:
        """Thu thập dữ liệu từ cửa hàng chính hãng"""
        results = []
        try:
            # Chuẩn hóa query cho URL
            encoded_query = urllib.parse.quote_plus(query)
            search_url = store_config['search_url'].format(query=encoded_query)
            
            logger.info(f"Searching {store_config['name']} with URL: {search_url}")
            
            # Gửi request với headers giả lập browser
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'vi-VN,vi;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            response = requests.get(search_url, headers=headers, timeout=10)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Parse dữ liệu theo cấu hình của từng store
            if store_config['name'] == 'Phong Vũ':
                results = self.parse_phongvu(soup, query, limit)
            elif store_config['name'] == 'CellphoneS':
                results = self.parse_cellphones(soup, query, limit)
            elif store_config['name'] == 'Thế Giới Di Động':
                results = self.parse_tgdd(soup, query, limit)
            elif store_config['name'] == 'Điện Máy Xanh':
                results = self.parse_dmx(soup, query, limit)
            elif store_config['name'] == 'Nguyễn Kim':
                results = self.parse_nguyenkim(soup, query, limit)
            elif store_config['name'] == 'Tiki':
                results = self.parse_tiki(soup, query, limit)
            elif store_config['name'] == 'ZALORA':
                results = self.parse_zalora(soup, query, limit)
            elif store_config['name'] == 'Lazada':
                results = self.parse_lazada(soup, query, limit)
            elif store_config['name'] == 'Shopee':
                results = self.parse_shopee(soup, query, limit)
            elif store_config['name'] == 'Oto.com.vn':
                results = self.parse_oto(soup, query, limit)
            elif store_config['name'] == 'Carmudi':
                results = self.parse_carmudi(soup, query, limit)
            elif store_config['name'] == 'Batdongsan.com.vn':
                results = self.parse_batdongsan(soup, query, limit)
            elif store_config['name'] == 'Alonhadat.com.vn':
                results = self.parse_alonhadat(soup, query, limit)
            elif store_config['name'] == 'Guardian':
                results = self.parse_guardian(soup, query, limit)
            elif store_config['name'] == 'Hasaki':
                results = self.parse_hasaki(soup, query, limit)
            else:
                # Generic parser cho các store khác
                results = self.parse_generic_store(soup, query, limit)
            
            logger.info(f"Successfully scraped {len(results)} items from {store_config['name']}")
            
        except requests.RequestException as e:
            logger.warning(f"Request error for {store_config['name']}: {e}")
        except Exception as e:
            logger.error(f"Error scraping {store_config['name']}: {e}")
        
        return results[:limit]
    
    def parse_phongvu(self, soup: BeautifulSoup, query: str, limit: int) -> List[Dict]:
        """Parse dữ liệu từ Phong Vũ"""
        results = []
        try:
            # Tìm các sản phẩm (cấu trúc có thể thay đổi)
            product_items = soup.find_all(['div', 'li'], class_=re.compile(r'product|item'), limit=limit*2)
            
            for item in product_items[:limit]:
                try:
                    # Tìm tên sản phẩm
                    title_element = item.find(['a', 'h3', 'span'], class_=re.compile(r'title|name|product-name'))
                    if not title_element:
                        title_element = item.find('a')
                    
                    title = title_element.get_text(strip=True) if title_element else "Unknown Product"
                    
                    # Tìm giá
                    price_element = item.find(['span', 'div'], class_=re.compile(r'price|cost|money'))
                    if not price_element:
                        price_element = item.find(text=re.compile(r'[\d,]+\s*[₫đ]'))
                    
                    if price_element:
                        price_text = price_element.get_text(strip=True) if hasattr(price_element, 'get_text') else str(price_element)
                        price = self.extract_price(price_text)
                        
                        if price > 0 and self.is_relevant_product(title, query):
                            # Tìm URL
                            link_element = item.find('a', href=True)
                            url = link_element['href'] if link_element else "#"
                            if url.startswith('/'):
                                url = f"https://phongvu.vn{url}"
                            
                            results.append({
                                'title': title,
                                'price': price,
                                'source': 'Phong Vũ',
                                'url': url
                            })
                except Exception as e:
                    continue
                    
        except Exception as e:
            logger.warning(f"Error parsing Phong Vũ data: {e}")
        
        return results
    
    def parse_cellphones(self, soup: BeautifulSoup, query: str, limit: int) -> List[Dict]:
        """Parse dữ liệu từ CellphoneS"""
        results = []
        try:
            product_items = soup.find_all(['div', 'li'], class_=re.compile(r'product|item'), limit=limit*2)
            
            for item in product_items[:limit]:
                try:
                    title_element = item.find(['a', 'h3'], class_=re.compile(r'title|name'))
                    if not title_element:
                        title_element = item.find('a')
                    
                    title = title_element.get_text(strip=True) if title_element else "Unknown Product"
                    
                    price_element = item.find(['span', 'div'], class_=re.compile(r'price|cost'))
                    if price_element:
                        price_text = price_element.get_text(strip=True)
                        price = self.extract_price(price_text)
                        
                        if price > 0 and self.is_relevant_product(title, query):
                            link_element = item.find('a', href=True)
                            url = link_element['href'] if link_element else "#"
                            if url.startswith('/'):
                                url = f"https://cellphones.com.vn{url}"
                            
                            results.append({
                                'title': title,
                                'price': price,
                                'source': 'CellphoneS',
                                'url': url
                            })
                except Exception:
                    continue
                    
        except Exception as e:
            logger.warning(f"Error parsing CellphoneS data: {e}")
        
        return results
    
    def parse_tgdd(self, soup: BeautifulSoup, query: str, limit: int) -> List[Dict]:
        """Parse dữ liệu từ Thế Giới Di Động"""
        results = []
        try:
            product_items = soup.find_all(['li', 'div'], class_=re.compile(r'item|product'), limit=limit*2)
            
            for item in product_items[:limit]:
                try:
                    title_element = item.find(['a', 'h3'])
                    title = title_element.get_text(strip=True) if title_element else "Unknown Product"
                    
                    price_element = item.find(['strong', 'span'], class_=re.compile(r'price'))
                    if price_element:
                        price_text = price_element.get_text(strip=True)
                        price = self.extract_price(price_text)
                        
                        if price > 0 and self.is_relevant_product(title, query):
                            link_element = item.find('a', href=True)
                            url = link_element['href'] if link_element else "#"
                            if url.startswith('/'):
                                url = f"https://thegioididong.com{url}"
                            
                            results.append({
                                'title': title,
                                'price': price,
                                'source': 'Thế Giới Di Động',
                                'url': url
                            })
                except Exception:
                    continue
                    
        except Exception as e:
            logger.warning(f"Error parsing TGDĐ data: {e}")
        
        return results
    
    def parse_generic_store(self, soup: BeautifulSoup, query: str, limit: int) -> List[Dict]:
        """Generic parser cho các store chưa có parser riêng"""
        results = []
        try:
            # Tìm các element có thể chứa sản phẩm
            product_selectors = [
                'div[class*="product"]',
                'li[class*="item"]', 
                'div[class*="item"]',
                '.product-item',
                '.search-result'
            ]
            
            for selector in product_selectors:
                items = soup.select(selector, limit=limit*2)
                if items:
                    for item in items[:limit]:
                        try:
                            # Tìm title
                            title_element = item.find(['a', 'h1', 'h2', 'h3', 'h4'])
                            title = title_element.get_text(strip=True) if title_element else "Unknown Product"
                            
                            # Tìm giá
                            price_patterns = [
                                re.compile(r'[\d,]+\s*[₫đ]'),
                                re.compile(r'[\d,]+\s*VND'),
                                re.compile(r'[\d,]+\s*vnđ')
                            ]
                            
                            price = 0
                            for pattern in price_patterns:
                                price_text = item.find(text=pattern)
                                if price_text:
                                    price = self.extract_price(str(price_text))
                                    break
                            
                            if price > 0 and self.is_relevant_product(title, query):
                                link_element = item.find('a', href=True)
                                url = link_element['href'] if link_element else "#"
                                
                                results.append({
                                    'title': title,
                                    'price': price,
                                    'source': 'Generic Store',
                                    'url': url
                                })
                        except Exception:
                            continue
                    break  # Dừng khi tìm thấy dữ liệu
                    
        except Exception as e:
            logger.warning(f"Error in generic parser: {e}")
        
        return results
    
    def parse_dmx(self, soup: BeautifulSoup, query: str, limit: int) -> List[Dict]:
        """Parse dữ liệu từ Điện Máy Xanh"""
        return self.parse_generic_store(soup, query, limit)
    
    def parse_nguyenkim(self, soup: BeautifulSoup, query: str, limit: int) -> List[Dict]:
        """Parse dữ liệu từ Nguyễn Kim"""
        return self.parse_generic_store(soup, query, limit)
    
    def parse_tiki(self, soup: BeautifulSoup, query: str, limit: int) -> List[Dict]:
        """Parse dữ liệu từ Tiki"""
        return self.parse_generic_store(soup, query, limit)
    
    def parse_zalora(self, soup: BeautifulSoup, query: str, limit: int) -> List[Dict]:
        """Parse dữ liệu từ ZALORA"""
        return self.parse_generic_store(soup, query, limit)
    
    def parse_lazada(self, soup: BeautifulSoup, query: str, limit: int) -> List[Dict]:
        """Parse dữ liệu từ Lazada"""
        return self.parse_generic_store(soup, query, limit)
    
    def parse_shopee(self, soup: BeautifulSoup, query: str, limit: int) -> List[Dict]:
        """Parse dữ liệu từ Shopee"""
        return self.parse_generic_store(soup, query, limit)
    
    def parse_oto(self, soup: BeautifulSoup, query: str, limit: int) -> List[Dict]:
        """Parse dữ liệu từ Oto.com.vn"""
        return self.parse_generic_store(soup, query, limit)
    
    def parse_carmudi(self, soup: BeautifulSoup, query: str, limit: int) -> List[Dict]:
        """Parse dữ liệu từ Carmudi"""
        return self.parse_generic_store(soup, query, limit)
    
    def parse_batdongsan(self, soup: BeautifulSoup, query: str, limit: int) -> List[Dict]:
        """Parse dữ liệu từ Batdongsan.com.vn"""
        return self.parse_generic_store(soup, query, limit)
    
    def parse_alonhadat(self, soup: BeautifulSoup, query: str, limit: int) -> List[Dict]:
        """Parse dữ liệu từ Alonhadat.com.vn"""
        return self.parse_generic_store(soup, query, limit)
    
    def parse_guardian(self, soup: BeautifulSoup, query: str, limit: int) -> List[Dict]:
        """Parse dữ liệu từ Guardian"""
        return self.parse_generic_store(soup, query, limit)
    
    def parse_hasaki(self, soup: BeautifulSoup, query: str, limit: int) -> List[Dict]:
        """Parse dữ liệu từ Hasaki"""
        return self.parse_generic_store(soup, query, limit)
    
    def scrape_chotot_web(self, product_name: str, limit: int = 10) -> List[Dict]:
        """Fallback scraping từ website Chợ Tốt"""
        results = []
        try:
            search_url = f"https://www.chotot.com/tp-ho-chi-minh/mua-ban-dien-tu?q={quote(product_name)}"
            
            logger.info(f"Fallback scraping Chotot web: {search_url}")
            
            response = requests.get(search_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Tìm các sản phẩm với selectors mới
            product_items = soup.find_all(['div', 'a'], attrs={
                'class': lambda x: x and any(term in x.lower() for term in ['aditem', 'item', 'listing', 'product'])
            })
            
            normalized_query = self.normalize_text(product_name)
            
            for item in product_items[:limit * 2]:  # Lấy nhiều hơn để lọc
                try:
                    # Tìm tiêu đề
                    title_elem = item.find(['h3', 'h4', 'a', 'span'], attrs={
                        'class': lambda x: x and any(term in x.lower() for term in ['title', 'subject', 'name'])
                    })
                    
                    if not title_elem:
                        title_elem = item.find('a')
                    
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        normalized_title = self.normalize_text(title)
                        
                        if self.is_similar_product(normalized_query, normalized_title):
                            # Tìm giá
                            price_elem = item.find(['span', 'div'], attrs={
                                'class': lambda x: x and 'price' in x.lower()
                            })
                            
                            if price_elem:
                                price_text = price_elem.get_text(strip=True)
                                price = self.extract_price_from_text(price_text)
                                
                                if price and len(results) < limit:
                                    results.append({
                                        'title': title,
                                        'price': price,
                                        'source': 'chotot.com',
                                        'url': search_url
                                    })
                
                except Exception as e:
                    logger.warning(f"Error parsing Chotot web item: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error scraping Chotot web: {e}")
        
        return results
    
    def scrape_muaban(self, product_name: str, limit: int = 10) -> List[Dict]:
        """Thu thập dữ liệu từ MuaBan.net với selectors cập nhật"""
        results = []
        try:
            normalized_query = self.normalize_text(product_name)
            
            # Thử nhiều URL patterns
            urls_to_try = [
                f"https://muaban.net/tim-kiem?q={quote(product_name)}",
                f"https://muaban.net/search?keyword={quote(product_name)}",
                f"https://www.muaban.net/tim-kiem/{quote(product_name)}"
            ]
            
            for search_url in urls_to_try:
                try:
                    logger.info(f"Trying MuaBan URL: {search_url}")
                    
                    response = requests.get(search_url, headers=self.headers, timeout=15)
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Thử nhiều selectors khác nhau
                    selectors = [
                        {'tag': ['div', 'li'], 'class': lambda x: x and any(term in x.lower() for term in ['product', 'item', 'listing', 'ad'])},
                        {'tag': ['article'], 'class': lambda x: x and 'item' in x.lower()},
                        {'tag': ['div'], 'attrs': {'data-test': lambda x: x and 'item' in x}},
                    ]
                    
                    product_items = []
                    for selector in selectors:
                        items = soup.find_all(selector['tag'], attrs=selector.get('attrs', {'class': selector['class']}))
                        if items:
                            product_items = items
                            break
                    
                    found_items = 0
                    for item in product_items:
                        if found_items >= limit:
                            break
                            
                        try:
                            # Tìm tiêu đề với nhiều cách khác nhau
                            title_elem = None
                            title_selectors = [
                                {'tag': ['h1', 'h2', 'h3', 'h4'], 'class': lambda x: x and any(term in x.lower() for term in ['title', 'name', 'subject'])},
                                {'tag': ['a'], 'class': lambda x: x and 'title' in x.lower()},
                                {'tag': ['span'], 'class': lambda x: x and 'title' in x.lower()},
                                {'tag': ['a'], 'attrs': {'title': True}},
                                {'tag': ['a'], 'attrs': {}}  # Any link
                            ]
                            
                            for title_sel in title_selectors:
                                title_elem = item.find(title_sel['tag'], attrs=title_sel.get('attrs', {'class': title_sel['class']}))
                                if title_elem:
                                    break
                            
                            if title_elem:
                                title = title_elem.get_text(strip=True) or title_elem.get('title', '').strip()
                                normalized_title = self.normalize_text(title)
                                
                                # Kiểm tra độ tương đồng
                                if title and self.is_similar_product(normalized_query, normalized_title):
                                    # Tìm giá với nhiều cách
                                    price_elem = None
                                    price_selectors = [
                                        {'tag': ['span', 'div'], 'class': lambda x: x and 'price' in x.lower()},
                                        {'tag': ['span', 'div'], 'class': lambda x: x and 'gia' in x.lower()},
                                        {'tag': ['span'], 'attrs': {'data-price': True}},
                                        {'tag': ['div'], 'class': lambda x: x and 'money' in x.lower()}
                                    ]
                                    
                                    for price_sel in price_selectors:
                                        price_elem = item.find(price_sel['tag'], attrs=price_sel.get('attrs', {'class': price_sel['class']}))
                                        if price_elem:
                                            break
                                    
                                    if price_elem:
                                        price_text = price_elem.get_text(strip=True)
                                        price = self.extract_price_from_text(price_text)
                                        
                                        if price:
                                            results.append({
                                                'title': title,
                                                'price': price,
                                                'source': 'muaban.net',
                                                'url': search_url
                                            })
                                            found_items += 1
                        
                        except Exception as e:
                            logger.warning(f"Error parsing MuaBan item: {e}")
                            continue
                    
                    if results:
                        break  # Nếu tìm thấy kết quả, dừng thử URL khác
                        
                except requests.RequestException as e:
                    logger.warning(f"Request failed for {search_url}: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"Error with {search_url}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error scraping MuaBan: {e}")
        
        return results
    
    def scrape_facebook_marketplace(self, product_name: str, limit: int = 5) -> List[Dict]:
        """Thu thập dữ liệu từ Facebook Marketplace (limited)"""
        results = []
        try:
            # Facebook Marketplace thường khó scrape, tạo dữ liệu mẫu dựa trên tên sản phẩm
            normalized_query = self.normalize_text(product_name)
            
            # Tạo giá mẫu dựa trên từ khóa phổ biến
            price_ranges = {
                'iphone': {'min': 5000000, 'max': 30000000},
                'samsung': {'min': 3000000, 'max': 25000000},
                'laptop': {'min': 5000000, 'max': 50000000},
                'macbook': {'min': 15000000, 'max': 80000000},
                'ipad': {'min': 5000000, 'max': 30000000},
                'airpods': {'min': 1000000, 'max': 8000000},
                'watch': {'min': 1000000, 'max': 15000000},
                'camera': {'min': 3000000, 'max': 50000000},
                'ps5': {'min': 10000000, 'max': 20000000},
                'xbox': {'min': 8000000, 'max': 18000000},
                'switch': {'min': 5000000, 'max': 12000000}
            }
            
            # Tìm từ khóa phù hợp
            found_range = None
            for keyword, price_range in price_ranges.items():
                if keyword in normalized_query:
                    found_range = price_range
                    break
            
            if found_range:
                import random
                # Tạo một vài giá mẫu trong khoảng
                for i in range(min(3, limit)):
                    price = random.randint(found_range['min'], found_range['max'])
                    results.append({
                        'title': f"{product_name} - Sample from market research",
                        'price': price,
                        'source': 'facebook.com/marketplace',
                        'url': 'https://facebook.com/marketplace'
                    })
            
        except Exception as e:
            logger.warning(f"Error in Facebook Marketplace simulation: {e}")
        
        return results
    
    def is_similar_product(self, query: str, title: str, min_similarity: float = 0.3) -> bool:
        """Kiểm tra độ tương đồng giữa tên sản phẩm"""
        if not query or not title:
            return False
        
        query_words = set(query.split())
        title_words = set(title.split())
        
        if not query_words or not title_words:
            return False
        
        # Tính toán Jaccard similarity
        intersection = len(query_words.intersection(title_words))
        union = len(query_words.union(title_words))
        
        similarity = intersection / union if union > 0 else 0
        
        return similarity >= min_similarity
    
    def calculate_price_range(self, prices: List[int], condition: str) -> Dict:
        """Tính toán khoảng giá hợp lý"""
        if not prices:
            return {
                'min_price': 0,
                'max_price': 0,
                'recommended_price': 0,
                'market_average': 0,
                'condition_multiplier': 1.0
            }
        
        # Loại bỏ outliers (giá quá cao hoặc quá thấp)
        sorted_prices = sorted(prices)
        q1 = sorted_prices[len(sorted_prices)//4]
        q3 = sorted_prices[3*len(sorted_prices)//4]
        iqr = q3 - q1
        
        filtered_prices = [p for p in prices if q1 - 1.5*iqr <= p <= q3 + 1.5*iqr]
        
        if not filtered_prices:
            filtered_prices = prices
        
        market_average = statistics.mean(filtered_prices)
        condition_multiplier = self.condition_multipliers.get(condition, 0.75)
        
        # Tính giá đề xuất dựa trên tình trạng
        recommended_price = market_average * condition_multiplier
        
        # Khoảng giá hợp lý (±15% từ giá đề xuất)
        min_price = recommended_price * 0.85
        max_price = recommended_price * 1.15
        
        return {
            'min_price': int(min_price),
            'max_price': int(max_price),
            'recommended_price': int(recommended_price),
            'market_average': int(market_average),
            'condition_multiplier': condition_multiplier,
            'sample_size': len(filtered_prices)
        }
    
    def get_price_suggestion(self, product_name: str, condition: str) -> Dict:
        """Lấy gợi ý giá cho sản phẩm từ các cửa hàng chính hãng theo danh mục"""
        cache_key = f"{product_name}_{condition}"
        
        # Kiểm tra cache
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            if datetime.now() - cached_data['timestamp'] < timedelta(seconds=self.cache_duration):
                logger.info(f"Returning cached result for {cache_key}")
                return cached_data['data']
        
        logger.info(f"Getting price suggestion for: {product_name} - {condition}")
        
        # 1. Tự động phát hiện danh mục sản phẩm
        category = self.detect_product_category(product_name)
        category_info = self.data_sources.get(category, self.data_sources['electronics'])
        
        all_prices = []
        sources = []
        data_sources_used = []
        
        logger.info(f"Product category detected: {category} ({category_info['name']})")
        
        # 2. Thu thập dữ liệu từ các cửa hàng chính hãng theo danh mục
        for source_config in category_info['sources']:
            if not source_config.get('active', False):
                continue
                
            try:
                logger.info(f"Scraping {source_config['name']}...")
                source_data = self.scrape_official_store(source_config, product_name, limit=5)
                
                if source_data:
                    # Lọc giá hợp lý (loại bỏ giá quá cao hoặc quá thấp)
                    filtered_data = self.filter_reasonable_prices(source_data, category)
                    
                    all_prices.extend([item['price'] for item in filtered_data])
                    sources.extend(filtered_data)
                    data_sources_used.append(source_config['name'])
                    
                    logger.info(f"Found {len(filtered_data)} valid items from {source_config['name']}")
                
                time.sleep(1)  # Delay để tránh bị block
                
            except Exception as e:
                logger.warning(f"Error scraping {source_config['name']}: {e}")
                continue
        
        # 3. Nếu không có dữ liệu thực, tạo dữ liệu ước tính dựa trên danh mục
        if not all_prices:
            logger.info("No real data found, generating estimated prices based on category...")
            estimated_data = self.generate_category_based_estimates(product_name, category, condition)
            all_prices.extend([item['price'] for item in estimated_data])
            sources.extend(estimated_data)
            data_sources_used.append('Estimated Data')
        
        # 4. Tính toán khoảng giá
        price_range = self.calculate_price_range(all_prices, condition)
        
        result = {
            'product_name': product_name,
            'condition': condition,
            'category': category,
            'category_name': category_info['name'],
            'price_range': price_range,
            'sources': sources[:15],  # Lấy tối đa 15 nguồn
            'timestamp': datetime.now().isoformat(),
            'success': len(all_prices) > 0,
            'data_sources_used': data_sources_used
        }
        
        # Lưu cache
        self.cache[cache_key] = {
            'data': result,
            'timestamp': datetime.now()
        }
        
        logger.info(f"Generated price suggestion with {len(all_prices)} price points from {len(data_sources_used)} sources")
        
        return result
    
    def filter_reasonable_prices(self, data: List[Dict], category: str) -> List[Dict]:
        """Lọc giá hợp lý theo danh mục"""
        if not data:
            return []
        
        # Định nghĩa khoảng giá hợp lý cho từng danh mục
        price_ranges = {
            'electronics': {'min': 100000, 'max': 100000000},      # 100k - 100M
            'home_appliances': {'min': 500000, 'max': 200000000},  # 500k - 200M  
            'fashion': {'min': 50000, 'max': 20000000},            # 50k - 20M
            'vehicles': {'min': 5000000, 'max': 5000000000},       # 5M - 5B
            'real_estate': {'min': 100000000, 'max': 50000000000}, # 100M - 50B
            'beauty_health': {'min': 20000, 'max': 5000000}       # 20k - 5M
        }
        
        range_config = price_ranges.get(category, price_ranges['electronics'])
        
        filtered_data = []
        for item in data:
            price = item.get('price', 0)
            if range_config['min'] <= price <= range_config['max']:
                filtered_data.append(item)
        
        logger.info(f"Filtered {len(filtered_data)}/{len(data)} items within reasonable price range for {category}")
        return filtered_data
    
    def generate_category_based_estimates(self, product_name: str, category: str, condition: str) -> List[Dict]:
        """Tạo giá ước tính dựa trên danh mục và tên sản phẩm"""
        results = []
        normalized_query = self.normalize_text(product_name)
        
        # Database giá ước tính theo danh mục
        category_estimates = {
            'electronics': {
                'iphone 16': [25000000, 35000000, 45000000],
                'iphone 15': [20000000, 28000000, 35000000],
                'iphone 14': [15000000, 22000000, 28000000],
                'iphone 13': [12000000, 18000000, 22000000],
                'samsung galaxy s24': [15000000, 22000000, 28000000],
                'samsung galaxy s23': [12000000, 18000000, 24000000],
                'macbook air': [20000000, 30000000, 45000000],
                'macbook pro': [35000000, 50000000, 80000000],
                'laptop dell': [10000000, 20000000, 35000000],
                'laptop hp': [8000000, 15000000, 25000000],
                'airpods': [3000000, 5000000, 8000000],
                'default': [1000000, 8000000, 20000000]
            },
            'home_appliances': {
                'tu lanh': [8000000, 15000000, 30000000],
                'may giat': [6000000, 12000000, 25000000],
                'dieu hoa': [5000000, 10000000, 20000000],
                'ti vi': [4000000, 8000000, 15000000],
                'default': [2000000, 8000000, 20000000]
            },
            'fashion': {
                'giay nike': [1500000, 3000000, 6000000],
                'giay adidas': [1200000, 2500000, 5000000],
                'tui xach': [500000, 2000000, 10000000],
                'dong ho': [1000000, 5000000, 20000000],
                'default': [200000, 1000000, 5000000]
            },
            'vehicles': {
                'honda': [25000000, 50000000, 100000000],
                'yamaha': [20000000, 40000000, 80000000],
                'toyota': [400000000, 800000000, 1500000000],
                'default': [30000000, 100000000, 500000000]
            },
            'real_estate': {
                'can ho': [2000000000, 4000000000, 8000000000],
                'nha': [1500000000, 3000000000, 6000000000],
                'dat': [500000000, 2000000000, 5000000000],
                'default': [1000000000, 3000000000, 8000000000]
            },
            'beauty_health': {
                'my pham': [200000, 1000000, 3000000],
                'nuoc hoa': [500000, 2000000, 8000000],
                'default': [100000, 500000, 2000000]
            }
        }
        
        # Tìm giá ước tính phù hợp trong danh mục
        estimates = category_estimates.get(category, category_estimates['electronics'])
        found_prices = None
        
        for keyword, prices in estimates.items():
            if keyword == 'default':
                continue
            if any(word in normalized_query for word in keyword.split()):
                found_prices = prices
                break
        
        # Sử dụng giá mặc định nếu không tìm thấy
        if not found_prices:
            found_prices = estimates.get('default', [1000000, 5000000, 15000000])
        
        # Tạo kết quả ước tính
        for i, price in enumerate(found_prices):
            results.append({
                'title': f"{product_name} - Estimated price {i+1} ({category})",
                'price': price,
                'source': f'Estimated Data ({category})',
                'url': 'internal_estimation',
                'type': 'estimated'
            })
        
        return results

# Khởi tạo engine
price_engine = PriceSuggestionEngine()

@app.route('/', methods=['GET'])
def root():
    """Root endpoint để kiểm tra API"""
    return jsonify({
        'message': 'Price Suggestion API Server is running!',
        'version': '1.0.0',
        'endpoints': {
            '/health': 'Health check',
            '/api/price-suggestion': 'Get price suggestions (GET for info, POST for data)',
            '/api/validate-price': 'Validate user price (GET for info, POST for validation)'
        },
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/price-suggestion', methods=['GET', 'POST'])
def get_price_suggestion():
    """API endpoint để lấy gợi ý giá"""
    try:
        if request.method == 'GET':
            # Test endpoint với GET method
            return jsonify({
                'message': 'Price Suggestion API is running',
                'methods': ['POST'],
                'example_request': {
                    'product_name': 'iPhone 13',
                    'condition': 'nhu-moi'
                },
                'conditions': list(price_engine.condition_multipliers.keys())
            })
        
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        product_name = data.get('product_name', '').strip()
        condition = data.get('condition', '').strip()
        
        if not product_name:
            return jsonify({'error': 'Product name is required'}), 400
        
        if not condition:
            return jsonify({'error': 'Condition is required'}), 400
        
        result = price_engine.get_price_suggestion(product_name, condition)
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"API Error: {e}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/validate-price', methods=['GET', 'POST'])
def validate_price():
    """API endpoint để kiểm tra giá người dùng nhập"""
    try:
        if request.method == 'GET':
            return jsonify({
                'message': 'Price Validation API is running',
                'methods': ['POST'],
                'example_request': {
                    'product_name': 'iPhone 13',
                    'condition': 'nhu-moi',
                    'price': 15000000
                }
            })
            
        data = request.get_json()
        
        product_name = data.get('product_name', '').strip()
        condition = data.get('condition', '').strip()
        user_price = data.get('price', 0)
        
        if not product_name or not condition:
            return jsonify({'error': 'Missing product_name or condition'}), 400
            
        if user_price <= 0:
            return jsonify({
                'status': 'invalid_price',
                'message': 'Vui lòng nhập giá hợp lệ (lớn hơn 0)',
                'icon': '⚠️'
            }), 400
        
        # Lấy gợi ý giá
        suggestion = price_engine.get_price_suggestion(product_name, condition)
        
        if not suggestion['success']:
            return jsonify({
                'status': 'no_data',
                'message': 'Không tìm thấy dữ liệu tham khảo cho sản phẩm này',
                'icon': '⚠️'
            })
        
        price_range = suggestion['price_range']
        min_price = price_range['min_price']
        max_price = price_range['max_price']
        recommended_price = price_range['recommended_price']
        
        # Phân loại giá
        if user_price > max_price * 1.3:  # Cao hơn 130% giá tối đa
            return jsonify({
                'status': 'too_high',
                'message': f'Giá quá cao so với thị trường! Giá đề xuất: {recommended_price:,}₫',
                'icon': '🚫',
                'recommended_price': recommended_price,
                'max_safe_price': max_price
            })
        elif user_price > max_price:  # Cao hơn giá tối đa nhưng < 130%
            return jsonify({
                'status': 'high',
                'message': f'Giá hơi cao. Giá đề xuất: {recommended_price:,}₫',
                'icon': '⚠️',
                'recommended_price': recommended_price,
                'max_safe_price': max_price
            })
        elif user_price < min_price * 0.7:  # Thấp hơn 70% giá tối thiểu
            return jsonify({
                'status': 'too_low',
                'message': f'Giá quá thấp! Bạn có thể bán với giá cao hơn: {recommended_price:,}₫',
                'icon': '💡',
                'recommended_price': recommended_price,
                'min_safe_price': min_price
            })
        elif min_price <= user_price <= max_price:  # Trong khoảng hợp lý
            return jsonify({
                'status': 'good',
                'message': 'Giá hợp lý! Sản phẩm có thể bán nhanh',
                'icon': '✅',
                'recommended_price': recommended_price
            })
        else:  # Các trường hợp khác
            return jsonify({
                'status': 'acceptable',
                'message': f'Giá chấp nhận được. Giá đề xuất: {recommended_price:,}₫',
                'icon': '👍',
                'recommended_price': recommended_price
            })
    
    except Exception as e:
        logger.error(f"Validation Error: {e}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
