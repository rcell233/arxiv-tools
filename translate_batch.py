import json
import requests
import time
import os
from typing import Dict, Any, List

# OpenRouter API配置
# API_KEY = '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'
API_KEY = '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'

BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "moonshotai/kimi-k2:free"

def translate_papers_batch(papers_batch: list) -> list:
    """
    批量翻译多篇论文的标题和摘要
    
    Args:
        papers_batch: 包含论文信息的列表，每个元素包含paper_title和paper_abstract
    
    Returns:
        包含中文翻译的列表
    """
    
    # 构建批量翻译的prompt
    papers_input = []
    for i, paper in enumerate(papers_batch):
        papers_input.append(f'"paper_{i+1}": {{"paper_title": "{paper["paper_title"]}", "paper_abstract": "{paper["paper_abstract"]}"}}')
    
    papers_input_str = "{\n" + ",\n".join(papers_input) + "\n}"
    
    prompt = f"""
请将以下多篇论文的标题和摘要翻译成中文，并以JSON格式返回。
返回格式应该是：
{{
  "paper_1": {{"paper_title_zh": "中文标题1", "paper_abstract_zh": "中文摘要1"}},
  "paper_2": {{"paper_title_zh": "中文标题2", "paper_abstract_zh": "中文摘要2"}},
  ...
}}

输入内容：
{papers_input_str}
"""

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/your-repo",  # 可选，用于在openrouter.ai上显示
        "X-Title": "ArXiv Paper Translator"  # 可选，用于在openrouter.ai上显示
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
        "max_tokens": 8000  # 增加token限制以支持批量翻译
    }
    
    # 添加重试机制
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(BASE_URL, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            
            result = response.json()
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
                
                translations = json.loads(json_content)
                
                # 解析批量翻译结果
                results = []
                for i in range(len(papers_batch)):
                    paper_key = f"paper_{i+1}"
                    if paper_key in translations:
                        results.append({
                            "paper_title_zh": translations[paper_key].get("paper_title_zh", ""),
                            "paper_abstract_zh": translations[paper_key].get("paper_abstract_zh", "")
                        })
                    else:
                        results.append({"paper_title_zh": "", "paper_abstract_zh": ""})
                
                return results
                
            except json.JSONDecodeError as e:
                print(f"JSON解析错误 (尝试 {attempt+1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    print(f"原始响应: {content}")
                    return [{"paper_title_zh": "", "paper_abstract_zh": ""} for _ in papers_batch]
                
        except requests.exceptions.RequestException as e:
            print(f"API请求错误 (尝试 {attempt+1}/{max_retries}): {e}")
            if "429" in str(e):  # 速率限制错误
                wait_time = (attempt + 1) * 10  # 递增等待时间
                print(f"遇到速率限制，等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
            elif attempt == max_retries - 1:
                return [{"paper_title_zh": "", "paper_abstract_zh": ""} for _ in papers_batch]
        except Exception as e:
            print(f"未知错误 (尝试 {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                return [{"paper_title_zh": "", "paper_abstract_zh": ""} for _ in papers_batch]
    
    return [{"paper_title_zh": "", "paper_abstract_zh": ""} for _ in papers_batch]

def load_index(data_dir: str) -> Dict[str, Any]:
    """加载索引文件"""
    index_file = os.path.join(data_dir, 'index.json')
    try:
        with open(index_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载索引文件错误: {e}")
        return {'dates': [], 'total_papers': 0, 'last_updated': ''}

def save_index(data_dir: str, index: Dict[str, Any]):
    """保存索引文件"""
    index_file = os.path.join(data_dir, 'index.json')
    try:
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        print(f"索引已保存到 {index_file}")
    except Exception as e:
        print(f"保存索引文件错误: {e}")

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

def load_papers_data(file_path: str) -> Dict[str, Any]:
    """加载论文数据（兼容旧格式）"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载文件错误: {e}")
        return {}

def save_papers_data(data: Dict[str, Any], file_path: str):
    """保存论文数据（兼容旧格式）"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"数据已保存到 {file_path}")
    except Exception as e:
        print(f"保存文件错误: {e}")

def translate_empty_papers_new_format(data_dir: str = "data", batch_size: int = 5):
    """
    批量翻译新格式下所有中文字段为空的论文条目
    
    Args:
        data_dir: 数据目录路径
        batch_size: 每批翻译的论文数量
    """
    # 确保数据目录存在
    if not os.path.exists(data_dir):
        print(f"数据目录 {data_dir} 不存在")
        return
    
    # 加载索引
    index = load_index(data_dir)
    dates = index.get('dates', [])
    
    if not dates:
        print("没有找到任何日期数据")
        return
    
    print(f"找到 {len(dates)} 个日期: {dates}")
    
    # 收集所有需要翻译的论文
    papers_to_translate = []
    paper_locations = []  # 记录每篇论文的位置 (date, paper_index)
    
    for date_str in dates:
        papers = load_papers_for_date(data_dir, date_str)
        for i, paper in enumerate(papers):
            needs_translation = (
                not paper.get("paper_title_zh") or 
                not paper.get("paper_abstract_zh") or
                paper.get("paper_title_zh") == "" or 
                paper.get("paper_abstract_zh") == ""
            )
            
            if needs_translation:
                papers_to_translate.append({
                    "paper_title": paper.get("paper_title", ""),
                    "paper_abstract": paper.get("paper_abstract", "")
                })
                paper_locations.append((date_str, i))
    
    total_to_translate = len(papers_to_translate)
    print(f"找到 {total_to_translate} 个需要翻译的论文条目")
    
    if total_to_translate == 0:
        print("没有需要翻译的论文条目")
        return
    
    total_translated = 0
    
    # 批量处理翻译
    for batch_start in range(0, total_to_translate, batch_size):
        batch_end = min(batch_start + batch_size, total_to_translate)
        current_batch = papers_to_translate[batch_start:batch_end]
        current_locations = paper_locations[batch_start:batch_end]
        
        print(f"\n翻译批次 {batch_start//batch_size + 1}: 论文 {batch_start+1}-{batch_end}")
        
        # 显示当前批次的论文标题
        for i, paper in enumerate(current_batch):
            print(f"  {batch_start + i + 1}. {paper['paper_title'][:60]}...")
        
        # 调用批量翻译API
        translations = translate_papers_batch(current_batch)
        
        # 按日期分组更新数据
        date_updates = {}
        for i, translation in enumerate(translations):
            if i < len(current_locations):
                date_str, paper_index = current_locations[i]
                if date_str not in date_updates:
                    date_updates[date_str] = load_papers_for_date(data_dir, date_str)
                
                paper = date_updates[date_str][paper_index]
                if translation["paper_title_zh"]:
                    paper["paper_title_zh"] = translation["paper_title_zh"]
                if translation["paper_abstract_zh"]:
                    paper["paper_abstract_zh"] = translation["paper_abstract_zh"]
                
                total_translated += 1
        
        # 保存更新的数据
        for date_str, papers in date_updates.items():
            save_papers_for_date(data_dir, date_str, papers)
        
        print(f"  批次翻译完成 ({total_translated}/{total_to_translate})")
    
    print(f"\n翻译完成！总共翻译了 {total_translated} 个论文条目")
    print(f"总共发送了 {(total_to_translate + batch_size - 1) // batch_size} 次API请求")

def translate_empty_papers(input_file: str = "daily_papers.json", output_file: str = None, batch_size: int = 5):
    """
    批量翻译所有中文字段为空的论文条目
    
    Args:
        input_file: 输入文件路径
        output_file: 输出文件路径，如果为None则覆盖输入文件
        batch_size: 每批翻译的论文数量
    """
    if output_file is None:
        output_file = input_file
    
    # 加载数据
    papers_data = load_papers_data(input_file)
    if not papers_data:
        return
    
    # 收集所有需要翻译的论文
    papers_to_translate = []
    paper_locations = []  # 记录每篇论文在原数据中的位置
    
    for date, papers in papers_data.items():
        for i, paper in enumerate(papers):
            needs_translation = (
                not paper.get("paper_title_zh") or 
                not paper.get("paper_abstract_zh") or
                paper.get("paper_title_zh") == "" or 
                paper.get("paper_abstract_zh") == ""
            )
            
            if needs_translation:
                papers_to_translate.append({
                    "paper_title": paper.get("paper_title", ""),
                    "paper_abstract": paper.get("paper_abstract", "")
                })
                paper_locations.append((date, i))
    
    total_to_translate = len(papers_to_translate)
    print(f"找到 {total_to_translate} 个需要翻译的论文条目")
    
    if total_to_translate == 0:
        print("没有需要翻译的论文条目")
        return
    
    total_translated = 0
    
    # 批量处理翻译
    for batch_start in range(0, total_to_translate, batch_size):
        batch_end = min(batch_start + batch_size, total_to_translate)
        current_batch = papers_to_translate[batch_start:batch_end]
        current_locations = paper_locations[batch_start:batch_end]
        
        print(f"\n翻译批次 {batch_start//batch_size + 1}: 论文 {batch_start+1}-{batch_end}")
        
        # 显示当前批次的论文标题
        for i, paper in enumerate(current_batch):
            print(f"  {batch_start + i + 1}. {paper['paper_title'][:60]}...")
        
        # 调用批量翻译API
        translations = translate_papers_batch(current_batch)
        
        # 更新原数据
        for i, translation in enumerate(translations):
            if i < len(current_locations):
                date, paper_index = current_locations[i]
                paper = papers_data[date][paper_index]
                
                if translation["paper_title_zh"]:
                    paper["paper_title_zh"] = translation["paper_title_zh"]
                if translation["paper_abstract_zh"]:
                    paper["paper_abstract_zh"] = translation["paper_abstract_zh"]
                
                total_translated += 1
        
        print(f"  批次翻译完成 ({total_translated}/{total_to_translate})")
        
        # 每个批次后保存一次
        save_papers_data(papers_data, output_file)
        print(f"  已保存进度: {total_translated}/{total_to_translate}")
        
    
    print(f"\n翻译完成！总共翻译了 {total_translated} 个论文条目")
    print(f"总共发送了 {(total_to_translate + batch_size - 1) // batch_size} 次API请求")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='批量翻译论文标题和摘要')
    parser.add_argument('--format', choices=['old', 'new'], default='new',
                        help='数据格式：old=单一JSON文件，new=分文件格式')
    parser.add_argument('--data-dir', type=str, default='data',
                        help='数据目录路径（新格式）')
    parser.add_argument('--input-file', type=str, default='daily_papers.json',
                        help='输入文件路径（旧格式）')
    parser.add_argument('--output-file', type=str, default=None,
                        help='输出文件路径（旧格式，默认覆盖输入文件）')
    parser.add_argument('--batch-size', type=int, default=5,
                        help='每批翻译的论文数量')
    
    args = parser.parse_args()
    
    if args.format == 'new':
        print("使用新的分文件格式进行翻译...")
        translate_empty_papers_new_format(args.data_dir, args.batch_size)
    else:
        print("使用旧的单一JSON文件格式进行翻译...")
        translate_empty_papers(args.input_file, args.output_file, args.batch_size)