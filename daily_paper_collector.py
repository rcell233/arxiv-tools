#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import arxiv
import yaml
import logging
import argparse
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional

logging.basicConfig(format='[%(asctime)s %(levelname)s] %(message)s',
                    datefmt='%m/%d/%Y %H:%M:%S',
                    level=logging.INFO)

class DailyPaperCollector:
    def __init__(self, config_path: str = 'config.yaml', data_dir: str = 'data'):
        self.config_path = config_path
        self.data_dir = data_dir
        self.papers_dir = os.path.join(data_dir, 'papers')
        self.index_file = os.path.join(data_dir, 'index.json')
        self.config = self.load_config()
        self.ensure_data_directories()
        
    def load_config(self) -> Dict:
        """加载配置文件"""
        with open(self.config_path, 'r') as f:
            config = yaml.load(f, Loader=yaml.FullLoader)
            # 处理关键词过滤器和分类信息
            keywords = {}
            topic_categories = {}
            for k, v in config['keywords'].items():
                filters = v['filters']
                query_parts = []
                for filter_term in filters:
                    if len(filter_term.split()) > 1:
                        query_parts.append(f'"{filter_term}"')
                    else:
                        query_parts.append(filter_term)
                keywords[k] = ' OR '.join(query_parts)
                # 保存主题对应的大类
                topic_categories[k] = v.get('category', 'Other')
            config['processed_keywords'] = keywords
            config['topic_categories'] = topic_categories
            logging.info(f'Loaded config with {len(keywords)} topics')
        return config
    
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
    
    def get_authors_string(self, authors) -> str:
        """将作者列表转换为字符串"""
        return ", ".join(str(author) for author in authors)
    
    def get_arxiv_search_date(self, target_date: date) -> date:
        """获取arXiv搜索日期，处理周末逻辑"""
        # 如果是周一（weekday=0），需要回溯到上周五
        if target_date.weekday() == 0:  # 周一
            # 回溯到上周五（3天前）
            arxiv_search_date = target_date - timedelta(days=3)
        else:
            # 其他日期，查找前一天
            arxiv_search_date = target_date - timedelta(days=1)
        
        logging.info(f"Target date: {target_date} (weekday: {target_date.weekday()}), searching arXiv papers from: {arxiv_search_date}")
        return arxiv_search_date
    
    def is_target_date(self, paper_date: date, target_date: date) -> bool:
        """检查论文日期是否为目标日期（arXiv论文通常是前一天发表的）"""
        # 获取应该搜索的arXiv日期
        arxiv_search_date = self.get_arxiv_search_date(target_date)
        return paper_date == arxiv_search_date
    
    def search_papers_by_keywords(self, target_date: date, max_results: int = 100) -> Dict[str, List[Dict]]:
        """方式1: 使用关键词搜索论文"""
        logging.info("=== Method 1: Searching by keywords ===")
        results_by_topic = {}
        
        for topic, query in self.config['processed_keywords'].items():
            logging.info(f"Searching for topic: {topic}")
            
            try:
                search_engine = arxiv.Search(
                    query=query,
                    max_results=max_results,
                    sort_by=arxiv.SortCriterion.SubmittedDate
                )
                
                papers = []
                for result in search_engine.results():
                    paper_date = result.updated.date()
                    
                    if self.is_target_date(paper_date, target_date):
                        paper_info = {
                            'paper_title': result.title,
                            'paper_title_zh': '',  # 中文标题，留空
                            'paper_id': result.get_short_id(),
                            'paper_abstract': result.summary.replace('\n', ' '),
                            'paper_abstract_zh': '',  # 中文摘要，留空
                            'primary_category': result.primary_category,
                            'update_time': result.updated.strftime('%Y-%m-%d'),
                            'paper_authors': self.get_authors_string(result.authors),
                            'topic': [topic],  # 初始化为单个topic的列表
                            'category': [self.config['topic_categories'][topic]]  # 添加大类标签
                        }
                        papers.append(paper_info)
                
                results_by_topic[topic] = papers
                logging.info(f"Found {len(papers)} papers for topic '{topic}' on {target_date}")
                
            except Exception as e:
                logging.error(f"Error searching for topic '{topic}': {e}")
                results_by_topic[topic] = []
        
        return results_by_topic
    
    def search_papers_by_categories(self, target_date: date, max_results: int = 100) -> List[Dict]:
        """方式2: 按分类搜索论文"""
        logging.info("=== Method 2: Searching by categories ===")
        categories = ['eess.AS', 'cs.SD']
        all_papers = []
        
        for category in categories:
            logging.info(f"Searching category: {category}")
            
            try:
                query = f"cat:{category}"
                search_engine = arxiv.Search(
                    query=query,
                    max_results=max_results,
                    sort_by=arxiv.SortCriterion.SubmittedDate
                )
                
                category_papers = []
                for result in search_engine.results():
                    paper_date = result.updated.date()
                    
                    if self.is_target_date(paper_date, target_date):
                        paper_info = {
                            'paper_title': result.title,
                            'paper_title_zh': '',  # 中文标题，留空
                            'paper_id': result.get_short_id(),
                            'paper_abstract': result.summary.replace('\n', ' '),
                            'paper_abstract_zh': '',  # 中文摘要，留空
                            'primary_category': result.primary_category,
                            'update_time': result.updated.strftime('%Y-%m-%d'),
                            'paper_authors': self.get_authors_string(result.authors),
                            'topic': [],  # 分类搜索的论文topic为空
                            'category': ['Other']  # 分类搜索的论文默认为Other大类
                        }
                        category_papers.append(paper_info)
                
                all_papers.extend(category_papers)
                logging.info(f"Found {len(category_papers)} papers in category '{category}' on {target_date}")
                
            except Exception as e:
                logging.error(f"Error searching category '{category}': {e}")
        
        return all_papers
    
    def merge_papers_by_topic(self, results_by_topic: Dict[str, List[Dict]]) -> Dict[str, Dict]:
        """合并不同topic的重复论文"""
        merged_papers = {}
        
        for topic, papers in results_by_topic.items():
            for paper in papers:
                paper_id = paper['paper_id']
                
                if paper_id in merged_papers:
                    # 合并topic
                    if topic not in merged_papers[paper_id]['topic']:
                        merged_papers[paper_id]['topic'].append(topic)
                    # 合并大类标签
                    category = self.config['topic_categories'][topic]
                    if category not in merged_papers[paper_id]['category']:
                        merged_papers[paper_id]['category'].append(category)
                else:
                    merged_papers[paper_id] = paper.copy()
        
        logging.info(f"Merged {sum(len(papers) for papers in results_by_topic.values())} papers into {len(merged_papers)} unique papers")
        return merged_papers
    
    def add_incremental_papers(self, existing_papers: Dict[str, Dict], category_papers: List[Dict]) -> Dict[str, Dict]:
        """添加分类搜索的增量论文"""
        initial_count = len(existing_papers)
        
        for paper in category_papers:
            paper_id = paper['paper_id']
            if paper_id not in existing_papers:
                existing_papers[paper_id] = paper
        
        added_count = len(existing_papers) - initial_count
        logging.info(f"Added {added_count} incremental papers from category search")
        return existing_papers
    
    def collect_daily_papers(self, target_date: date):
        """收集指定日期的论文（增量模式）"""
        date_str = target_date.strftime('%Y-%m-%d')
        arxiv_date = self.get_arxiv_search_date(target_date)
        logging.info(f"Collecting papers for date: {date_str} (searching arXiv papers from {arxiv_date})")
        
        # 加载已存在的论文数据
        existing_papers_list = self.load_papers_for_date(date_str)
        existing_papers_dict = {paper['paper_id']: paper for paper in existing_papers_list}
        existing_count = len(existing_papers_dict)
        logging.info(f"Found {existing_count} existing papers for date {date_str}")
        
        # 方式1: 关键词搜索
        results_by_topic = self.search_papers_by_keywords(target_date)
        merged_papers = self.merge_papers_by_topic(results_by_topic)
        method1_count = len(merged_papers)
        logging.info(f"Method 1 (Keywords) found: {method1_count} unique papers")
        
        # 方式2: 分类搜索（增量）
        category_papers = self.search_papers_by_categories(target_date)
        final_papers = self.add_incremental_papers(merged_papers, category_papers)
        method2_increment = len(final_papers) - method1_count
        logging.info(f"Method 2 (Categories) added: {method2_increment} additional papers")
        
        # 增量合并：只添加新论文，保留已有论文
        new_papers_count = 0
        for paper_id, paper in final_papers.items():
            if paper_id not in existing_papers_dict:
                existing_papers_dict[paper_id] = paper
                new_papers_count += 1
            else:
                # 对于已存在的论文，可以选择更新topic和category信息
                existing_paper = existing_papers_dict[paper_id]
                # 合并topic
                for topic in paper['topic']:
                    if topic not in existing_paper['topic']:
                        existing_paper['topic'].append(topic)
                # 合并category
                for category in paper['category']:
                    if category not in existing_paper['category']:
                        existing_paper['category'].append(category)
        
        logging.info(f"Added {new_papers_count} new papers to existing {existing_count} papers")
        
        # 转换为列表格式
        papers_list = list(existing_papers_dict.values())
        
        # 保存到新的文件结构中
        self.save_papers_for_date(date_str, papers_list)
        
        total_count = len(papers_list)
        logging.info(f"Total papers for {date_str}: {total_count} (existing: {existing_count}, new: {new_papers_count})")
        
        # 显示topic统计
        topic_stats = {}
        category_stats = {}
        for paper in papers_list:
            topics = paper['topic']
            categories = paper['category']
            
            if not topics:
                topic_stats['No Topic'] = topic_stats.get('No Topic', 0) + 1
            else:
                for topic in topics:
                    topic_stats[topic] = topic_stats.get(topic, 0) + 1
                    
            for category in categories:
                category_stats[category] = category_stats.get(category, 0) + 1
        
        logging.info("Topic distribution:")
        for topic, count in sorted(topic_stats.items()):
            logging.info(f"  {topic}: {count} papers")
            
        logging.info("Category distribution:")
        for category, count in sorted(category_stats.items()):
            logging.info(f"  {category}: {count} papers")
        
        return papers_list

def main():
    parser = argparse.ArgumentParser(description='Daily Paper Collector')
    parser.add_argument('--date', type=str, default=None,
                        help='Target date in YYYY-MM-DD format (default: today)')
    parser.add_argument('--config', type=str, default='config.yaml',
                        help='Config file path')
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
    collector = DailyPaperCollector(args.config, args.data_dir)
    papers = collector.collect_daily_papers(target_date)
    
    logging.info(f"Collection completed! Found {len(papers)} papers for {target_date}")

if __name__ == "__main__":
    main()
