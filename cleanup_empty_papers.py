#!/usr/bin/env python3
"""
清理 data/papers 目录下空的日度 JSON 文件，并同步更新 data/index.json。

判定标准：
- 文件可解析为 JSON 且为列表类型，并且长度为 0，则视为空；
- 或者内容为仅包含空白/空数组的情况。

安全策略：
- 仅删除明确判定为空的文件；
- 仅从 index.json 的 dates 中移除对应日期；
- 打印日志汇总。
"""

import os
import json
import logging
from datetime import datetime


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
PAPERS_DIR = os.path.join(ROOT_DIR, 'data', 'papers')
INDEX_FILE = os.path.join(ROOT_DIR, 'data', 'index.json')


def is_empty_daily_json(file_path: str) -> bool:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw = f.read().strip()
            if raw == '' or raw == '[]':
                return True
            data = json.loads(raw)
            if isinstance(data, list) and len(data) == 0:
                return True
            return False
    except json.JSONDecodeError:
        # 无法解析当作JSON，不删除
        return False
    except Exception as e:
        logger.warning(f"读取文件失败，跳过: {file_path} - {e}")
        return False


def extract_date_from_filename(filename: str) -> str | None:
    # 期望文件名格式：YYYY-MM-DD.json
    name, ext = os.path.splitext(filename)
    if ext.lower() != '.json':
        return None
    try:
        datetime.strptime(name, '%Y-%m-%d')
        return name
    except ValueError:
        return None


def load_index() -> dict:
    if not os.path.exists(INDEX_FILE):
        return {}
    try:
        with open(INDEX_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"读取 index.json 失败，将以空对象处理: {e}")
        return {}


def save_index(index_obj: dict) -> None:
    try:
        with open(INDEX_FILE, 'w', encoding='utf-8') as f:
            json.dump(index_obj, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"写入 index.json 失败: {e}")


def main():
    if not os.path.isdir(PAPERS_DIR):
        logger.info("未找到 papers 目录，跳过清理。")
        return

    index_obj = load_index()
    dates = set(index_obj.get('dates', [])) if isinstance(index_obj.get('dates'), list) else set()

    removed_files: list[str] = []
    removed_dates: list[str] = []

    for filename in os.listdir(PAPERS_DIR):
        file_path = os.path.join(PAPERS_DIR, filename)
        if not os.path.isfile(file_path):
            continue
        day = extract_date_from_filename(filename)
        if not day:
            continue
        if is_empty_daily_json(file_path):
            try:
                os.remove(file_path)
                removed_files.append(filename)
                if day in dates:
                    dates.remove(day)
                    removed_dates.append(day)
                logger.info(f"删除空文件: {filename}")
            except Exception as e:
                logger.error(f"删除文件失败: {filename} - {e}")

    if removed_files:
        # 更新 index.json
        index_obj['dates'] = sorted(list(dates))
        # 如果 total_papers 存在，尝试重新估算：保持不变更为安全，或留空。
        # 这里选择安全不动 total_papers，由上游流程更新。
        save_index(index_obj)
        logger.info(f"已删除 {len(removed_files)} 个空JSON，更新 index.json 中 {len(removed_dates)} 个日期。")
    else:
        logger.info("未发现需要删除的空JSON。")


if __name__ == '__main__':
    main()


