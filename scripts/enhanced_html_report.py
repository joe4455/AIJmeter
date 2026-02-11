#!/usr/bin/env python3
"""
增强版HTML报告生成模块
独立于主脚本，提供generate_enhanced_html_report功能
"""

import datetime
import os
import sys
from pathlib import Path

def parse_timestamp(timestamp_str):
    """解析时间戳，支持数值和字符串格式"""
    formats = ['%Y/%m/%d %H:%M:%S', '%Y-%m-%d %H:%M:%S']
    
    try:
        return float(timestamp_str)
    except ValueError:
        for fmt in formats:
            try:
                dt = datetime.datetime.strptime(timestamp_str, fmt)
                return dt.timestamp() * 1000  # 转换为毫秒级时间戳
            except ValueError:
                continue
        return datetime.datetime.now().timestamp() * 1000

def generate_enhanced_html_report(jtl_file, report_dir, test_name, logger):
    """生成增强版HTML报告（备用方案）"""
    logger.info(f"为 {test_name} 生成增强版HTML报告")
    
    try:
        # 解析JTL文件，提取关键统计信息
        stats = {}
        line_count = 0
        all_timestamps = []  # 存储所有样本的时间戳，用于计算整体TPS
        
        with open(jtl_file, 'r', encoding='utf-8') as f:
            headers = None
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                if line_count == 0 and 'timeStamp' in line:
                    # CSV格式带表头
                    headers = line.split(',')
                    line_count += 1
                    continue
                
                values = line.split(',')
                if not headers:
                    # 假设CSV格式不带表头，使用默认顺序
                    if len(values) < 10:
                        continue  # 跳过不完整的行
                    
                    sampler_name = values[2] if len(values) > 2 else "Unknown"
                    response_time = float(values[1]) if values[1] else 0
                    success = values[7] == "true" if len(values) > 7 else True
                    response_code = values[3] if len(values) > 3 else "200"
                    bytes = float(values[9]) if values[9] else 0
                    sent_bytes = float(values[10]) if len(values) > 10 else 0
                    timestamp = parse_timestamp(values[0]) if len(values) > 0 else 0
                else:
                    # 使用表头解析
                    if len(values) != len(headers):
                        continue  # 跳过不完整的行
                    
                    row = dict(zip(headers, values))
                    sampler_name = row.get('label', 'Unknown')
                    response_time = float(row.get('elapsed', 0))
                    success = row.get('success', 'true') == 'true'
                    response_code = row.get('responseCode', '200')
                    bytes = float(row.get('bytes', 0))
                    sent_bytes = float(row.get('sentBytes', 0))
                    timestamp = parse_timestamp(row.get('timeStamp', 0))
                
                # 记录时间戳用于整体TPS计算
                all_timestamps.append(timestamp)
                
                # 初始化统计信息
                if sampler_name not in stats:
                    stats[sampler_name] = {
                        'sampleCount': 0,
                        'errorCount': 0,
                        'totalTime': 0,
                        'times': [],
                        'bytes': 0,
                        'sentBytes': 0,
                        'successCodes': {},
                        'errorCodes': {},
                        'timestamps': []  # 记录每个接口的时间戳
                    }
                
                # 更新统计信息
                stat = stats[sampler_name]
                stat['sampleCount'] += 1
                stat['totalTime'] += response_time
                stat['times'].append(response_time)
                stat['bytes'] += bytes
                stat['sentBytes'] += sent_bytes
                stat['timestamps'].append(timestamp)  # 记录时间戳
                
                if success:
                    stat['successCodes'][response_code] = stat['successCodes'].get(response_code, 0) + 1
                else:
                    stat['errorCount'] += 1
                    stat['errorCodes'][response_code] = stat['errorCodes'].get(response_code, 0) + 1
                
                line_count += 1
        
        # 计算摘要统计信息
        for sampler, stat in stats.items():
            if stat['sampleCount'] > 0:
                stat['meanResTime'] = stat['totalTime'] / stat['sampleCount']
                stat['medianResTime'] = sorted(stat['times'])[len(stat['times']) // 2]
                stat['minResTime'] = min(stat['times'])
                stat['maxResTime'] = max(stat['times'])
                stat['errorPct'] = (stat['errorCount'] / stat['sampleCount']) * 100
                # 计算90%, 95%, 99%响应时间
                sorted_times = sorted(stat['times'])
                stat['pct90'] = sorted_times[int(len(sorted_times) * 0.9)]
                stat['pct95'] = sorted_times[int(len(sorted_times) * 0.95)]
                stat['pct99'] = sorted_times[int(len(sorted_times) * 0.99)]
                
                # 计算TPS（基于样本实际运行时间）
                if stat['timestamps']:
                    run_time_seconds = (max(stat['timestamps']) - min(stat['timestamps'])) / 1000
                    stat['tps'] = stat['sampleCount'] / run_time_seconds if run_time_seconds > 0 else 0
                    stat['actual_run_time'] = run_time_seconds
                else:
                    stat['tps'] = 0
                    stat['actual_run_time'] = 0
                
                # 计算总响应时间（秒）
                stat['total_response_time'] = stat['totalTime'] / 1000
        
        # 计算整体TPS
        total_tps = 0
        if all_timestamps:
            total_run_time_seconds = (max(all_timestamps) - min(all_timestamps)) / 1000
            total_tps = sum(s['sampleCount'] for s in stats.values()) / total_run_time_seconds if total_run_time_seconds > 0 else 0
        
        # 文件大小转换为MB
        file_size_bytes = jtl_file.stat().st_size
        file_size_mb = file_size_bytes / (1024 * 1024)
        
        # 生成HTML报告
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{test_name} - JMeter测试报告</title>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                h1 {{ color: #333; }}
                .info {{ background: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                .summary {{ margin: 20px 0; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                .success {{ color: green; }}
                .error {{ color: red; }}
            </style>
        </head>
        <body>
            <h1>{test_name} - JMeter测试报告</h1>
            <div class="info">
                <p><strong>测试名称:</strong> {test_name}</p>
                <p><strong>生成时间:</strong> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>JTL文件:</strong> {jtl_file.name}</p>
                <p><strong>文件大小:</strong> {file_size_bytes} 字节 ({file_size_mb:.2f} MB)</p>
                <p><strong>事务总数:</strong> {sum(s['sampleCount'] for s in stats.values())}</p>
                <p><strong>总TPS:</strong> {total_tps:.2f} 事务/秒</p>
            </div>
            
            <h2>响应时间摘要</h2>
            <table>
                <tr>
                    <th>接口名称</th>
                    <th>事务数</th>
                    <th>错误数</th>
                    <th>错误率</th>
                    <th>总响应时间(秒)</th>
                    <th>实际运行时间(秒)</th>
                    <th>平均响应时间</th>
                    <th>中位数</th>
                    <th>最小值</th>
                    <th>最大值</th>
                    <th>90%响应时间</th>
                    <th>95%响应时间</th>
                    <th>99%响应时间</th>
                    <th>吞吐量 (Throughput)</th>
                    <th>TPS</th>
                </tr>
        """
        
        # 添加每个接口的统计信息
        for sampler, stat in stats.items():
            throughput = stat['sampleCount'] / stat['actual_run_time'] if stat['actual_run_time'] > 0 else 0
            html_content += f"""
                <tr>
                    <td>{sampler}</td>
                    <td>{stat['sampleCount']}</td>
                    <td class="{'error' if stat['errorCount'] > 0 else 'success'}">{stat['errorCount']}</td>
                    <td class="{'error' if stat['errorPct'] > 0 else 'success'}">{stat['errorPct']:.2f}%</td>
                    <td>{stat['total_response_time']:.2f}s</td>
                    <td>{stat['actual_run_time']:.2f}s</td>
                    <td>{stat['meanResTime']:.2f}ms</td>
                    <td>{stat['medianResTime']}ms</td>
                    <td>{stat['minResTime']}ms</td>
                    <td>{stat['maxResTime']}ms</td>
                    <td>{stat['pct90']}ms</td>
                    <td>{stat['pct95']}ms</td>
                    <td>{stat['pct99']}ms</td>
                    <td>{throughput:.2f} 请求/秒</td>
                    <td>{stat['tps']:.2f} 事务/秒</td>
                </tr>
            """
        
        html_content += """
            </table>
            
            <h2>响应码统计</h2>
        """
        
        for sampler, stat in stats.items():
            html_content += f"""
                <h3>{sampler}</h3>
                <table>
                    <tr>
                        <th>响应码</th>
                        <th>成功次数</th>
                        <th>失败次数</th>
                    </tr>
            """
            
            # 合并成功和失败的响应码
            all_codes = set(stat['successCodes'].keys()) | set(stat['errorCodes'].keys())
            for code in sorted(all_codes):
                success_count = stat['successCodes'].get(code, 0)
                error_count = stat['errorCodes'].get(code, 0)
                html_content += f"""
                    <tr>
                        <td>{code}</td>
                        <td>{success_count}</td>
                        <td>{error_count}</td>
                    </tr>
                """
            html_content += """
                </table>
            """
        
        html_content += """
            <h2>系统信息</h2>
            <div class="info">
                <p><strong>JMeter版本:</strong> 5.6.3</p>
                <p><strong>报告生成模式:</strong> 增强版备用报告</p>
                <p><strong>注:</strong> 此报告为增强版备用报告，包含完整的性能统计信息</p>
                <p><strong>吞吐量定义:</strong> 实际事务吞吐率 (请求/秒 = 事务数/实际运行时间(秒))</p>
                <p><strong>TPS定义:</strong> 实际事务吞吐率 (事务/秒 = 事务数/实际运行时间(秒))</p>
                <p><strong>计算说明:</strong> 如果每个事务 = 1个请求，则TPS等于吞吐量；如果事务包含多个请求，则TPS = (总请求数 / 每个事务包含的请求数) / 实际运行时间(秒)</p>
            </div>
        </body>
        </html>
        """
        
        report_file = report_dir / "index.html"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"增强版HTML报告已生成: {report_file}")
        return True
        
    except Exception as e:
        logger.error(f"生成增强版HTML报告时出错: {e}")
        return False