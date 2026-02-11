#!/usr/bin/env python3
"""
工具函数模块
"""

import logging
import sys
from pathlib import Path
import json

def setup_logging():
    """设置日志配置"""
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / "jmeter_batch_test.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

def get_logger():
    """获取logger实例"""
    return logging.getLogger("jmeter_batch_test")

def load_json_config(file_path):
    """加载JSON配置文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        get_logger().error(f"加载配置文件失败 {file_path}: {e}")
        raise

def save_json_config(data, file_path):
    """保存JSON配置"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        get_logger().error(f"保存配置文件失败 {file_path}: {e}")
        raise

def format_duration(seconds):
    """格式化持续时间"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
