#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import requests
import time
import os
import yaml
import argparse
from typing import Dict, Any, List, Optional
from datetime import datetime

# OpenRouter API配置
API_KEY = value = os.environ["API_KEY"]
BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "z-ai/glm-4.5-air:free"

def load_config(config_path: str = "config.yaml") -> Dict[str, List[str]]:
    """加载配置文件中的topic、category候选列表和白名单subjects"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return {
            'all_topic': config.get('all_topic', []),
            'all_category': config.get('all_category', []),
            'whitelist_subjects': config.get('whitelist_subjects', [])
        }
    except Exception as e:
        print(f"加载配置文件错误: {e}")
        return {'all_topic': [], 'all_category': [], 'whitelist_subjects': []}

def is_paper_in_whitelist(paper: Dict[str, Any], whitelist_subjects: List[str]) -> bool:
    """
    检查论文是否在白名单subjects中
    
    Args:
        paper: 论文信息字典
        whitelist_subjects: 白名单subjects列表
    
    Returns:
        如果论文包含任何白名单subject则返回True
    """
    paper_subjects = paper.get('subjects', [])
    
    for subject in paper_subjects:
        for whitelist_subject in whitelist_subjects:
            if whitelist_subject in subject:
                return True
    
    return False

def process_paper_complete(paper: Dict[str, Any], config: Dict[str, List[str]]) -> Dict[str, Any]:
    """
    使用LLM API为单篇论文进行完整处理：翻译标题和摘要，分类topic和category
    
    Args:
        paper: 包含论文信息的字典
        config: 包含候选topic和category列表的配置
    
    Returns:
        包含翻译和分类结果的字典
    """
    
    # 构建完整处理的prompt
    prompt = f"""
请对以下论文进行完整处理，包括翻译和分类：

1. 将英文标题和摘要翻译成中文
2. 根据论文内容为其分配合适的topic和category

论文信息：
标题：{paper.get("paper_title", "")}
摘要：{paper.get("paper_abstract", "")}
学科分类：{paper.get("subjects", [])}

可选的topic列表：{config['all_topic']}
可选的category列表：{config['all_category']}

分类要求：
1. category是这个论文所属的大类（从Music, Speech, Image, Other中选择）
2. topic是这篇论文所属的细分任务（从给定的topic列表中选择）
3. 一篇论文可以有多个topic，但通常只有一个主要category
4. 如果论文不完全符合任何预定义的分类，可以选择最接近的或选择"Other"

请以JSON格式返回结果：
{{
  "paper_title_zh": "中文标题",
  "paper_abstract_zh": "中文摘要",
  "topic": ["选择的topic1", "选择的topic2"],
  "category": ["选择的category"]
}}
请勿返回特殊字符，保证JSON格式标准可解析
"""

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/your-repo",
        "X-Title": "ArXiv Paper Classifier"
    }
    
    data = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.3,
        "max_tokens": 1000,
        "reasoning": {"enabled": False}
    }
    
    # 添加重试机制
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(BASE_URL, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            print(result)
            content = result['choices'][0]['message']['content']
            
            # 尝试解析JSON响应
            try:
                # 提取JSON部分（可能包含在代码块中）
                if '```json' in content:
                    json_start = content.find('```json') + 7
                    json_end = content.find('```', json_start)
                    json_content = content[json_start:json_end].strip()
                elif '{' in content and '}' in content:
                    json_start = content.find('{')
                    json_end = content.rfind('}') + 1
                    json_content = content[json_start:json_end]
                else:
                    json_content = content
                
                result_data = json.loads(json_content)
                
                # 提取翻译结果
                paper_title_zh = result_data.get("paper_title_zh", "")
                paper_abstract_zh = result_data.get("paper_abstract_zh", "")
                
                # 验证分类结果
                topic = result_data.get("topic", [])
                category = result_data.get("category", [])
                
                # 确保topic和category是列表
                if not isinstance(topic, list):
                    topic = [topic] if topic else []
                if not isinstance(category, list):
                    category = [category] if category else []
                
                # 验证topic是否在候选列表中
                valid_topics = []
                for t in topic:
                    if t in config['all_topic']:
                        valid_topics.append(t)
                    else:
                        print(f"警告：topic '{t}' 不在候选列表中")
                
                # 验证category是否在候选列表中
                valid_categories = []
                for c in category:
                    if c in config['all_category']:
                        valid_categories.append(c)
                    else:
                        print(f"警告：category '{c}' 不在候选列表中")
                
                return {
                    "paper_title_zh": paper_title_zh,
                    "paper_abstract_zh": paper_abstract_zh,
                    "topic": valid_topics,
                    "category": valid_categories
                }
                
            except json.JSONDecodeError as e:
                print(f"JSON解析错误 (尝试 {attempt+1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    print(f"原始响应: {content}")
                    return {"paper_title_zh": "", "paper_abstract_zh": "", "topic": [], "category": []}
                
        # except requests.exceptions.RequestException as e:
        #     print(f"API请求错误 (尝试 {attempt+1}/{max_retries}): {e}")
        #     if "429" in str(e):  # 速率限制错误
        #         wait_time = (attempt + 1) * 10  # 递增等待时间
        #         print(f"遇到速率限制，等待 {wait_time} 秒后重试...")
        #         time.sleep(wait_time)
        #     elif attempt == max_retries - 1:
        #         return {"paper_title_zh": "", "paper_abstract_zh": "", "topic": [], "category": []}
        except Exception as e:
            print(f"未知错误 (尝试 {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                return {"paper_title_zh": "", "paper_abstract_zh": "", "topic": [], "category": []}
    
    return {"paper_title_zh": "", "paper_abstract_zh": "", "topic": [], "category": []}

def load_index(data_dir: str) -> Dict[str, Any]:
    """加载索引文件"""
    index_file = os.path.join(data_dir, 'index.json')
    try:
        with open(index_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载索引文件错误: {e}")
        return {'dates': [], 'total_papers': 0, 'last_updated': ''}

def load_papers_for_date(data_dir: str, date_str: str) -> List[Dict]:
    """加载指定日期的论文数据"""
    papers_dir = os.path.join(data_dir, 'papers')
    date_file = os.path.join(papers_dir, f'{date_str}.json')
    try:
        with open(date_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载日期 {date_str} 的论文数据错误: {e}")
        return []

def save_papers_for_date(data_dir: str, date_str: str, papers: List[Dict]):
    """保存指定日期的论文数据"""
    papers_dir = os.path.join(data_dir, 'papers')
    os.makedirs(papers_dir, exist_ok=True)
    date_file = os.path.join(papers_dir, f'{date_str}.json')
    try:
        with open(date_file, 'w', encoding='utf-8') as f:
            json.dump(papers, f, ensure_ascii=False, indent=2)
        print(f"日期 {date_str} 的论文数据已保存到 {date_file}")
    except Exception as e:
        print(f"保存日期 {date_str} 的论文数据错误: {e}")

def process_papers_classification(data_dir: str = "data", config_path: str = "config.yaml", target_date: str = None):
    """
    为论文进行完整处理：翻译标题和摘要，补全topic和category分类
    
    Args:
        data_dir: 数据目录路径
        config_path: 配置文件路径
        target_date: 目标日期，格式为YYYY-MM-DD，如果为None则处理所有日期
    """
    # 确保数据目录存在
    if not os.path.exists(data_dir):
        print(f"数据目录 {data_dir} 不存在")
        return
    
    # 加载配置
    config = load_config(config_path)
    if not config['all_topic'] or not config['all_category']:
        print("配置文件中缺少topic或category列表")
        return
    
    print(f"可用的topic: {config['all_topic']}")
    print(f"可用的category: {config['all_category']}")
    print(f"白名单subjects: {config['whitelist_subjects']}")
    
    # 加载索引
    index = load_index(data_dir)
    dates = index.get('dates', [])
    
    if not dates:
        print("没有找到任何日期数据")
        return
    
    # 如果指定了目标日期，只处理该日期
    if target_date:
        if target_date not in dates:
            print(f"指定的日期 {target_date} 不存在于数据中")
            return
        dates = [target_date]
    
    print(f"将处理以下日期: {dates}")
    
    # 逐个日期处理
    for date_str in dates:
        print(f"\n开始处理日期: {date_str}")
        papers = load_papers_for_date(data_dir, date_str)
        
        if not papers:
            print(f"日期 {date_str} 没有论文数据")
            continue
        
        # 统计需要处理的论文（翻译或分类）
        papers_to_process = []
        for i, paper in enumerate(papers):
            needs_translation = (
                not paper.get("paper_title_zh") or 
                not paper.get("paper_abstract_zh") or
                paper.get("paper_title_zh") == "" or 
                paper.get("paper_abstract_zh") == ""
            )
            
            needs_classification = (
                not paper.get("topic") or 
                not paper.get("category") or
                (isinstance(paper.get("topic"), list) and len(paper.get("topic")) == 0) or
                (isinstance(paper.get("category"), list) and len(paper.get("category")) == 0)
            )
            
            if needs_translation or needs_classification:
                papers_to_process.append(i)
        
        total_to_process = len(papers_to_process)
        print(f"找到 {total_to_process} 个需要处理的论文条目（共 {len(papers)} 个）")
        
        if total_to_process == 0:
            print(f"日期 {date_str} 的所有论文都已处理完成")
            continue
        
        processed_count = 0
        filtered_count = 0
        
        # 创建论文副本用于操作，原始papers用于遍历
        papers_copy = papers.copy()
        
        # 逐个处理论文
        for paper_idx in papers_to_process:
            paper = papers[paper_idx]  # 从原始列表获取论文
            
            print(f"\n处理论文 {processed_count + 1}/{total_to_process}")
            print(f"标题: {paper.get('paper_title', '')[:80]}...")
            
            # 调用完整处理API（翻译+分类）
            result = process_paper_complete(paper, config)
            
            # 在副本中找到对应的论文并更新
            for i, copy_paper in enumerate(papers_copy):
                if copy_paper.get('paper_id') == paper.get('paper_id'):
                    # 更新论文信息
                    if result["paper_title_zh"]:
                        papers_copy[i]["paper_title_zh"] = result["paper_title_zh"]
                    if result["paper_abstract_zh"]:
                        papers_copy[i]["paper_abstract_zh"] = result["paper_abstract_zh"]
                    if result["topic"]:
                        papers_copy[i]["topic"] = result["topic"]
                    if result["category"]:
                        papers_copy[i]["category"] = result["category"]
                    
                    processed_count += 1
                    
                    print(f"处理结果 - Topic: {papers_copy[i].get('topic', [])}, Category: {papers_copy[i].get('category', [])}")
                    if result["paper_title_zh"]:
                        print(f"中文标题: {result['paper_title_zh'][:50]}...")
                    
                    # 检查是否需要过滤
                    is_whitelisted = is_paper_in_whitelist(papers_copy[i], config['whitelist_subjects'])
                    
                    # 过滤条件：非白名单论文且满足以下任一条件
                    # 1. category仅有Other（即category列表只包含"Other"一个元素）
                    # 2. topic仅有Other（即topic列表只包含"Other"一个元素）
                    paper_topics = papers_copy[i].get('topic', [])
                    paper_categories = papers_copy[i].get('category', [])
                    
                    should_filter = (not is_whitelisted and 
                                   (paper_categories == ['Other'] or 
                                    paper_topics == ['Other']))
                    
                    if should_filter:
                        # 从副本中删除这篇论文
                        papers_copy.pop(i)
                        filtered_count += 1
                        if paper_categories == ['Other']:
                            print(f"⚠️ 论文被过滤并删除（非白名单且category仅为Other）")
                        elif paper_topics == ['Other']:
                            print(f"⚠️ 论文被过滤并删除（非白名单且topic仅为Other）")
                    
                    break
            
            # 每处理一篇论文就保存一次（避免数据丢失）
            save_papers_for_date(data_dir, date_str, papers_copy)
            
            # 添加延迟避免API速率限制
            time.sleep(2)
        
        # 更新原始papers为最终的副本
        papers = papers_copy
        
        print(f"\n日期 {date_str} 处理完成！")
        print(f"  - 处理了 {processed_count} 个论文条目")
        print(f"  - 过滤删除了 {filtered_count} 个论文条目")
        print(f"  - 最终保留了 {len(papers)} 个论文条目")
    
    print(f"\n所有论文翻译和分类处理完成！")

def main():
    parser = argparse.ArgumentParser(description='为论文进行完整处理：翻译和分类')
    parser.add_argument('--data-dir', type=str, default='data',
                        help='数据目录路径')
    parser.add_argument('--config-path', type=str, default='config.yaml',
                        help='配置文件路径')
    parser.add_argument('--target-date', type=str, default=None,
                        help='目标日期，格式为YYYY-MM-DD，如果不指定则处理所有日期')
    
    args = parser.parse_args()
    
    print("开始论文翻译和分类处理...")
    process_papers_classification(args.data_dir, args.config_path, args.target_date)

if __name__ == "__main__":
    main()
