#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import requests
import yaml
import logging
import argparse
import re
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup

logging.basicConfig(format='[%(asctime)s %(levelname)s] %(message)s',
                    datefmt='%m/%d/%Y %H:%M:%S',
                    level=logging.INFO)

class DailyPaperCollector:
    def __init__(self, config_path: str = 'config.yaml', data_dir: str = 'data'):
        self.data_dir = data_dir
        self.papers_dir = os.path.join(data_dir, 'papers')
        self.index_file = os.path.join(data_dir, 'index.json')
        
        # 新的爬取URL列表
        self.urls = [
            # "https://arxiv.org/list/cs.CV/new",
            "https://arxiv.org/list/eess.AS/new", 
            "https://arxiv.org/list/cs.SD/new"
        ]
        
        self.ensure_data_directories()
        
    def ensure_data_directories(self):
        """确保数据目录存在"""
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.papers_dir, exist_ok=True)
        logging.info(f'Data directories ensured: {self.data_dir}, {self.papers_dir}')
    
    def load_index(self) -> Dict:
        """加载索引文件"""
        if os.path.exists(self.index_file):
            with open(self.index_file, 'r', encoding='utf-8') as f:
                try:
                    index = json.load(f)
                    logging.info(f'Loaded index with {len(index.get("dates", []))} dates')
                    return index
                except json.JSONDecodeError:
                    logging.warning('Invalid index file, starting fresh')
                    return {'dates': [], 'total_papers': 0, 'last_updated': ''}
        else:
            logging.info('No existing index file, starting fresh')
            return {'dates': [], 'total_papers': 0, 'last_updated': ''}
    
    def save_index(self, index: Dict):
        """保存索引文件"""
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        logging.info(f'Saved index to {self.index_file}')
    
    def load_papers_for_date(self, date_str: str) -> List[Dict]:
        """加载指定日期的论文数据"""
        date_file = os.path.join(self.papers_dir, f'{date_str}.json')
        if os.path.exists(date_file):
            with open(date_file, 'r', encoding='utf-8') as f:
                try:
                    papers = json.load(f)
                    logging.info(f'Loaded {len(papers)} papers for date {date_str}')
                    return papers
                except json.JSONDecodeError:
                    logging.warning(f'Invalid JSON file for date {date_str}')
                    return []
        else:
            logging.info(f'No existing data for date {date_str}')
            return []
    
    def save_papers_for_date(self, date_str: str, papers: List[Dict]):
        """保存指定日期的论文数据"""
        date_file = os.path.join(self.papers_dir, f'{date_str}.json')
        with open(date_file, 'w', encoding='utf-8') as f:
            json.dump(papers, f, ensure_ascii=False, indent=2)
        logging.info(f'Saved {len(papers)} papers to {date_file}')
        
        # 更新索引
        index = self.load_index()
        if date_str not in index['dates']:
            index['dates'].append(date_str)
            index['dates'].sort()  # 保持日期排序
        
        # 计算总论文数
        total_papers = 0
        for date in index['dates']:
            date_papers = self.load_papers_for_date(date)
            total_papers += len(date_papers)
        
        index['total_papers'] = total_papers
        index['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        self.save_index(index)
    
    def fetch_page(self, url: str) -> Optional[str]:
        """获取网页内容"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logging.error(f"Error fetching {url}: {e}")
            return None
    
    def extract_global_date(self, html_content: str) -> Optional[str]:
        """从HTML中提取全局日期"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 查找包含 "Showing new listings for" 的 h3 标签
        h3_tag = soup.find('h3', string=re.compile(r'Showing new listings for'))
        
        if h3_tag:
            text = h3_tag.get_text()
            # 提取日期部分：Wednesday, 10 September 2025
            date_match = re.search(r'Showing new listings for\s+(\w+,\s+\d{1,2}\s+\w+\s+\d{4})', text)
            if date_match:
                date_str = date_match.group(1)
                try:
                    # 解析格式：Wednesday, 10 September 2025
                    parsed_date = datetime.strptime(date_str, '%A, %d %B %Y')
                    return parsed_date.strftime('%Y-%m-%d')
                except ValueError as e:
                    logging.warning(f"Failed to parse date '{date_str}': {e}")
        
        # 如果找不到日期，返回 None
        return None
    
    def parse_subjects(self, subjects_div) -> List[str]:
        """解析subjects div，提取所有学科分类"""
        subjects = []
        
        if not subjects_div:
            return subjects
        
        # 获取div的完整文本内容
        full_text = subjects_div.get_text()
        
        # 移除 "Subjects:" 标签
        text = re.sub(r'Subjects:\s*', '', full_text)
        
        # 按分号分割，然后提取每个分类
        parts = text.split(';')
        
        for part in parts:
            part = part.strip()
            if part and '(' in part and ')' in part:
                # 提取完整的分类名称和代码
                subjects.append(part)
        
        return subjects
    
    def extract_authors(self, authors_div) -> str:
        """从作者div中提取作者列表"""
        if not authors_div:
            return ""
        
        # 提取所有作者链接的文本
        author_links = authors_div.find_all('a')
        authors = []
        for link in author_links:
            author_name = link.get_text().strip()
            if author_name:
                authors.append(author_name)
        
        return ", ".join(authors)
    
    def parse_papers_from_html(self, html_content: str, global_date: str) -> List[Dict]:
        """从HTML中解析论文信息，跳过Replacement submissions部分，其他都解析"""
        soup = BeautifulSoup(html_content, 'html.parser')
        papers = []
        
        # 查找所有 h3 标签和对应的内容
        h3_tags = soup.find_all('h3')
        paper_items = []
        
        for h3 in h3_tags:
            section_text = h3.get_text().strip()
            
            # 跳过 "Replacement submissions" 部分
            if 'Replacement submissions' in section_text:
                logging.info(f"Skipping section: {section_text}")
                continue
            
            # 检查是否是论文列表的section（通常包含submissions字样）
            if 'submissions' in section_text.lower() or 'cross-lists' in section_text.lower():
                logging.info(f"Processing section: {section_text}")
                
                # 查找该 h3 标签后的所有 dt 元素，直到遇到下一个 h3 标签
                current_element = h3.next_sibling
                
                while current_element:
                    if current_element.name == 'h3':
                        # 遇到下一个 h3 标签，停止查找
                        break
                    elif current_element.name == 'dt':
                        # 找到 dt 元素，添加到列表中
                        paper_items.append(current_element)
                    current_element = current_element.next_sibling
        
        logging.info(f"Found {len(paper_items)} papers in total (excluding Replacement submissions)")
        
        for dt in paper_items:
            try:
                # 查找对应的dd元素（包含详细信息）
                dd = dt.find_next_sibling('dd')
                if not dd:
                    continue
                
                # 提取arXiv ID
                arxiv_link = dt.find('a', href=re.compile(r'/abs/'))
                if not arxiv_link:
                    continue
                
                arxiv_id_match = re.search(r'(\d{4}\.\d{5})', arxiv_link.get('href', ''))
                if not arxiv_id_match:
                    continue
                
                paper_id = arxiv_id_match.group(1)
                
                # 提取标题
                title_div = dd.find('div', class_='list-title')
                title = ""
                if title_div:
                    title_text = title_div.get_text()
                    title_match = re.search(r'Title:\s*(.+)', title_text)
                    if title_match:
                        title = title_match.group(1).strip()
                
                # 提取作者
                authors_div = dd.find('div', class_='list-authors')
                authors = self.extract_authors(authors_div)
                
                # 提取subjects
                subjects_div = dd.find('div', class_='list-subjects')
                subjects = self.parse_subjects(subjects_div)
                
                # 提取摘要
                abstract = ""
                abstract_p = dd.find('p', class_='mathjax')
                if abstract_p:
                    abstract = abstract_p.get_text().strip()
                
                # 构建论文信息
                paper_info = {
                    'paper_title': title,
                    'paper_title_zh': '',  # 中文标题，留空
                    'paper_id': paper_id,
                    'paper_abstract': abstract,
                    'paper_abstract_zh': '',  # 中文摘要，留空
                    'subjects': subjects,  # 新字段：subjects列表
                    'update_time': global_date,  # 使用全局日期
                    'paper_authors': authors,
                    'topic': [],  # 留空
                    'category': []  # 留空
                }
                
                papers.append(paper_info)
                
            except Exception as e:
                logging.warning(f"Error parsing paper: {e}")
                continue
        
        return papers
    
    def collect_papers_from_url(self, url: str, target_date: str) -> List[Dict]:
        """从单个URL收集论文"""
        logging.info(f"Fetching papers from: {url}")
        
        html_content = self.fetch_page(url)
        if not html_content:
            return []
        
        # 提取全局日期
        global_date = self.extract_global_date(html_content)
        if not global_date:
            logging.warning(f"Could not extract date from {url}, skipping")
            return []
        
        logging.info(f"Extracted global date: {global_date}, target date: {target_date}")
        
        # 检查日期是否匹配
        if global_date != target_date:
            logging.info(f"Date mismatch for {url}: extracted {global_date}, target {target_date}. Skipping this URL.")
            return []
        
        # 解析论文
        papers = self.parse_papers_from_html(html_content, global_date)
        logging.info(f"Found {len(papers)} papers from {url}")
        
        return papers
    
    def collect_daily_papers(self, target_date: date) -> List[Dict]:
        """收集指定日期的论文（从三个URL），跳过Replacement submissions"""
        date_str = target_date.strftime('%Y-%m-%d')
        logging.info(f"Collecting papers for date: {date_str}")
        
        all_papers = {}  # 使用dict去重，key为paper_id
        
        # 从三个URL收集论文
        for url in self.urls:
            papers = self.collect_papers_from_url(url, date_str)
            
            # 合并论文，避免重复
            for paper in papers:
                paper_id = paper['paper_id']
                if paper_id in all_papers:
                    # 如果论文已存在，合并subjects
                    existing_subjects = set(all_papers[paper_id]['subjects'])
                    new_subjects = set(paper['subjects'])
                    all_papers[paper_id]['subjects'] = list(existing_subjects | new_subjects)
                else:
                    all_papers[paper_id] = paper
        
        papers_list = list(all_papers.values())
        logging.info(f"Total unique papers collected: {len(papers_list)}")
        
        # 保存论文数据
        self.save_papers_for_date(date_str, papers_list)
        
        # 显示统计信息
        subjects_stats = {}
        for paper in papers_list:
            for subject in paper['subjects']:
                subjects_stats[subject] = subjects_stats.get(subject, 0) + 1
        
        logging.info("Subjects distribution:")
        for subject, count in sorted(subjects_stats.items()):
            logging.info(f"  {subject}: {count} papers")
        
        return papers_list

def main():
    parser = argparse.ArgumentParser(description='Daily Paper Collector - New Version')
    parser.add_argument('--date', type=str, default=None,
                        help='Target date in YYYY-MM-DD format (default: today)')
    parser.add_argument('--data-dir', type=str, default='data',
                        help='Data directory path')
    
    args = parser.parse_args()
    
    # 解析目标日期
    if args.date:
        try:
            target_date = datetime.strptime(args.date, '%Y-%m-%d').date()
        except ValueError:
            logging.error("Invalid date format. Use YYYY-MM-DD")
            return
    else:
        # 默认使用当天日期
        target_date = date.today()
        logging.info(f"Using today's date: {target_date}")
    
    # 创建收集器并运行
    collector = DailyPaperCollector(data_dir=args.data_dir)
    papers = collector.collect_daily_papers(target_date)
    
    logging.info(f"Collection completed! Found {len(papers)} papers for {target_date}")

if __name__ == "__main__":
    main()