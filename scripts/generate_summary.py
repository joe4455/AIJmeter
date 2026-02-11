#!/usr/bin/env python3
"""
JMeter测试结果汇总报告生成脚本
"""

import os
import json
import pandas as pd
from pathlib import Path
import datetime
import sys

# 添加utils模块路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils import setup_logging, get_logger

def collect_test_results():
    """收集所有测试结果"""
    logger = get_logger()
    results_dir = Path(__file__).parent.parent / "results"
    
    all_results = []
    
    for batch_dir in results_dir.iterdir():
        if batch_dir.is_dir():
            batch_name = batch_dir.name
            for result_file in batch_dir.glob("*.jtl"):
                # 这里可以添加解析JTL文件的逻辑
                # 目前先收集基本信息
                all_results.append({
                    'batch': batch_name,
                    'file': result_file.name,
                    'path': str(result_file),
                    'size': result_file.stat().st_size,
                    'timestamp': datetime.datetime.fromtimestamp(result_file.stat().st_mtime)
                })
    
    return all_results

def generate_summary_report(results):
    """生成汇总报告"""
    logger = get_logger()
    
    # 创建DataFrame用于分析
    df = pd.DataFrame(results)
    
    # 生成基本统计信息
    summary = {
        'total_batches': df['batch'].nunique(),
        'total_results': len(df),
        'total_size_mb': df['size'].sum() / (1024 * 1024),
        'latest_test': df['timestamp'].max().strftime("%Y-%m-%d %H:%M:%S"),
        'batches': df['batch'].value_counts().to_dict()
    }
    
    return summary

def main():
    """主函数"""
    setup_logging()
    logger = get_logger()
    
    try:
        logger.info("开始生成测试结果汇总报告")
        
        # 收集结果
        results = collect_test_results()
        
        if not results:
            logger.warning("未找到任何测试结果文件")
            return
        
        # 生成报告
        summary = generate_summary_report(results)
        
        # 保存报告
        report_file = Path(__file__).parent.parent / "reports" / "summary_report.json"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        logger.info(f"汇总报告已生成: {report_file}")
        logger.info(f"统计信息: {summary}")
        
    except Exception as e:
        logger.error(f"生成报告过程中发生错误: {e}")

if __name__ == "__main__":
    main()
