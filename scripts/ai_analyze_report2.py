#!/usr/bin/env python3
"""
JMeter 压测报告 AI 分析脚本
支持分析 JMeter 压测报告并生成 AI 分析结果
"""

import os
import json
import datetime
import re
import argparse
import time
from pathlib import Path
import requests


class AIAnalyzer:
    """AI 分析器类"""
    
    def __init__(self, config_file=None):
        """初始化分析器"""
        self.config = self.load_config(config_file)
        self.logger = self.get_logger()
    
    def load_config(self, config_file=None):
        """加载配置文件"""
        default_config = {
            "ai_service": "deepseek",
            "api_keys": {
                "deepseek": "",
                "qianwen": "",
                "moon": "",
                "yunwu": ""
            },
            "api_endpoints": {
                "deepseek": "https://api.deepseek.com/v1/chat/completions",
                "qianwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "moon": "https://api.moonshot.cn/v1/chat/completions",
                "yunwu": "https://api.yunwuai.com/v1/chat/completions"
            },
            "model_names": {
                "deepseek": "deepseek-chat",
                "qianwen": "ep-20240101000000-xxxx",
                "moon": "moonshot-v1-8k",
                "yunwu": "yunwu-7b"
            },
            "max_tokens": 2000,
            "temperature": 0.7
        }
        
        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                
                # 深度合并配置，确保嵌套字典正确更新
                for key, value in user_config.items():
                    if key in default_config and isinstance(default_config[key], dict) and isinstance(value, dict):
                        # 合并嵌套字典
                        default_config[key].update(value)
                    else:
                        # 直接替换非字典值
                        default_config[key] = value
            except Exception as e:
                print(f"加载配置文件失败: {e}")
        
        return default_config
    
    def get_logger(self):
        """获取日志记录器"""
        import logging
        logger = logging.getLogger("AI_Analyzer")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def analyze_report(self, report_file, config):
        """分析单个报告文件"""
        try:
            self.logger.info(f"开始分析报告: {report_file}")
            
            # 读取报告文件内容
            with open(report_file, 'r', encoding='utf-8') as f:
                report_content = f.read()
            
            # 提取报告中的关键信息
            report_info = self.extract_report_info(report_content, report_file)
            
            # 构建AI分析提示
            prompt = self.build_analysis_prompt(report_info)
            
            # 调用AI服务
            analysis_result = self.call_ai_service(prompt)
            
            # 生成AI分析报告
            ai_report_file = self.generate_ai_report(report_file, analysis_result, config)
            
            # 更新原始报告，添加AI分析链接
            self.update_original_report(report_file, ai_report_file)
            
            return ai_report_file
        except Exception as e:
            self.logger.error(f"分析报告失败: {e}")
            return None
    
    def extract_report_info(self, report_content, report_file):
        """提取报告中的关键信息"""
        info = {
            "report_file": report_file,
            "report_name": os.path.basename(report_file),
            "metrics": {},
            "report_list": []
        }
        
        # 提取吞吐量信息
        throughput_match = re.search(r'平均吞吐量\s*\(TPS\)\s*[:：]\s*([\d.]+)', report_content)
        if throughput_match:
            info["metrics"]["throughput"] = float(throughput_match.group(1))
        
        # 提取响应时间信息
        response_time_match = re.search(r'平均响应时间\s*[:：]\s*([\d.]+)\s*ms', report_content)
        if response_time_match:
            info["metrics"]["response_time"] = float(response_time_match.group(1))
        
        # 提取错误率信息
        error_rate_match = re.search(r'错误率\s*[:：]\s*([\d.]+)%', report_content)
        if error_rate_match:
            info["metrics"]["error_rate"] = float(error_rate_match.group(1))
        
        # 提取样本数信息
        sample_count_match = re.search(r'样本数\s*[:：]\s*([\d,]+)', report_content)
        if sample_count_match:
            info["metrics"]["sample_count"] = int(sample_count_match.group(1).replace(',', ''))
        
        # 提取报告目录
        info["report_dir"] = os.path.dirname(report_file)
        
        # 提取报告列表
        info["report_list"] = self.extract_report_list(report_content, report_file)
        
        # 分析报告列表中的所有报告，提取详细指标
        info["detailed_analysis"] = self.analyze_report_list(info["report_list"])
        
        return info
    
    def extract_report_list(self, report_content, report_file):
        """从summary html文件中提取报告列表"""
        report_list = []
        
        # 提取报告列表中的链接
        report_links = re.findall(r'<a\s+href="([^"]+)"[^>]*>查看详细报告<\/a>', report_content)
        
        for link in report_links:
            # 构建完整的报告路径
            report_dir = os.path.dirname(report_file)
            full_path = os.path.join(report_dir, link)
            
            # 确保路径存在
            if os.path.exists(full_path):
                report_info = {
                    "path": full_path,
                    "name": os.path.basename(os.path.dirname(full_path)),
                    "link": link
                }
                report_list.append(report_info)
        
        return report_list
    
    def parse_index_html(self, index_file):
        """解析index.html文件，提取Dashboard中的关键信息"""
        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            dashboard_info = {
                "test_info": {},
                "apdex": {},
                "statistics": [],
                "errors": [],
                "top_errors": []
            }
            
            # 提取Test and Report information
            test_info_match = re.search(r'<h2>Test and Report information<\/h2>(.*?)<\/div>', content, re.DOTALL)
            if test_info_match:
                test_info_html = test_info_match.group(1)
                test_info_items = re.findall(r'<tr>(.*?)<\/tr>', test_info_html, re.DOTALL)
                for item in test_info_items:
                    key_match = re.search(r'<td[^>]*>(.*?)<\/td>', item)
                    value_match = re.search(r'<td[^>]*>(.*?)<\/td>', item, re.DOTALL)
                    if key_match and value_match:
                        key = key_match.group(1).strip()
                        value = value_match.group(1).strip()
                        dashboard_info["test_info"][key] = value
            
            # 提取APDEX
            apdex_match = re.search(r'<h2>APDEX \(Application Performance Index\)<\/h2>(.*?)<\/div>', content, re.DOTALL)
            if apdex_match:
                apdex_html = apdex_match.group(1)
                # 提取APDEX分数
                apdex_score_match = re.search(r'(?:<td[^>]*>APDEX<\/td>|Score|0\.\d+).*?<td[^>]*>([\d.]+)<\/td>', apdex_html, re.DOTALL)
                if apdex_score_match:
                    dashboard_info["apdex"]["score"] = apdex_score_match.group(1).strip()
                # 提取APDEX等级
                apdex_level_match = re.search(r'<td[^>]*>Level<\/td>.*?<td[^>]*>(.*?)<\/td>', apdex_html, re.DOTALL)
                if apdex_level_match:
                    dashboard_info["apdex"]["level"] = apdex_level_match.group(1).strip()
            
            # 提取Statistics
            statistics_match = re.search(r'<h2>Statistics<\/h2>(.*?)<\/div>', content, re.DOTALL)
            if statistics_match:
                statistics_html = statistics_match.group(1)
                # 提取表头
                headers = re.findall(r'<th[^>]*>(.*?)<\/th>', statistics_html)
                # 提取数据行
                rows = re.findall(r'<tr[^>]*>(.*?)<\/tr>', statistics_html, re.DOTALL)
                for row in rows:
                    if '<td' in row:
                        values = re.findall(r'<td[^>]*>(.*?)<\/td>', row, re.DOTALL)
                        if len(values) == len(headers):
                            row_data = {}
                            for i, header in enumerate(headers):
                                row_data[header] = values[i].strip()
                            # 确保关键性能指标存在
                            if row_data.get('Label') or row_data.get('Sampler Name') or row_data.get('Requests'):
                                dashboard_info["statistics"].append(row_data)
            
            # 提取Errors
            errors_match = re.search(r'<h2>Errors<\/h2>(.*?)<\/div>', content, re.DOTALL)
            if errors_match:
                errors_html = errors_match.group(1)
                # 提取表头
                headers = re.findall(r'<th[^>]*>(.*?)<\/th>', errors_html)
                # 提取数据行
                rows = re.findall(r'<tr[^>]*>(.*?)<\/tr>', errors_html, re.DOTALL)
                for row in rows:
                    if '<td' in row:
                        values = re.findall(r'<td[^>]*>(.*?)<\/td>', row, re.DOTALL)
                        if len(values) == len(headers):
                            row_data = {}
                            for i, header in enumerate(headers):
                                row_data[header] = values[i].strip()
                            dashboard_info["errors"].append(row_data)
            
            # 提取Top 5 Errors by sampler
            top_errors_match = re.search(r'<h2>Top 5 Errors by sampler<\/h2>(.*?)<\/div>', content, re.DOTALL)
            if top_errors_match:
                top_errors_html = top_errors_match.group(1)
                # 提取表头
                headers = re.findall(r'<th[^>]*>(.*?)<\/th>', top_errors_html)
                # 提取数据行
                rows = re.findall(r'<tr[^>]*>(.*?)<\/tr>', top_errors_html, re.DOTALL)
                for row in rows:
                    if '<td' in row:
                        values = re.findall(r'<td[^>]*>(.*?)<\/td>', row, re.DOTALL)
                        if len(values) == len(headers):
                            row_data = {}
                            for i, header in enumerate(headers):
                                row_data[header] = values[i].strip()
                            dashboard_info["top_errors"].append(row_data)
            
            return dashboard_info
        except Exception as e:
            self.logger.error(f"解析index.html文件失败: {e}")
            return {}
    
    def analyze_report_list(self, report_list):
        """分析报告列表中的所有报告"""
        analysis_results = []
        
        for report_info in report_list:
            index_file = os.path.join(report_info["path"])
            if os.path.exists(index_file):
                dashboard_info = self.parse_index_html(index_file)
                if dashboard_info:
                    analysis_results.append({
                        "report_name": report_info["name"],
                        "dashboard": dashboard_info
                    })
        
        return analysis_results
    
    def build_analysis_prompt(self, report_info):
        """构建AI分析提示"""
        # 构建详细的分析提示，包含所有提取的性能指标
        prompt = f"""
你是一位专业的性能测试分析师，请对以下JMeter压测报告进行深入分析：

# 报告基本信息
- 报告文件: {report_info['report_name']}
- 报告路径: {report_info['report_file']}
- 分析时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 测试场景数量: {len(report_info['report_list'])}

"""
        
        # 使用报告信息中的详细分析数据
        detailed_analysis = report_info.get('detailed_analysis', [])
        
        for i, result in enumerate(detailed_analysis, 1):
            report_name = result['report_name']
            dashboard = result['dashboard']
            
            prompt += f"\n## 场景 {i}: {report_name}\n"
            
            # 添加测试信息
            if dashboard.get('test_info'):
                prompt += "### 测试信息\n"
                test_info = dashboard['test_info']
                for key, value in test_info.items():
                    prompt += f"- {key}: {value}\n"
            
            # 添加APDEX
            if dashboard.get('apdex') and dashboard.get('apdex').get('score'):
                prompt += f"\n### APDEX 性能指数\n"
                prompt += f"- APDEX 分数: {dashboard['apdex']['score']}\n"
                if dashboard['apdex'].get('level'):
                    prompt += f"- APDEX 等级: {dashboard['apdex']['level']}\n"
            
            # 添加Statistics表格数据
            if dashboard.get('statistics'):
                prompt += "\n### Statistics 表格数据\n"
                stats = dashboard['statistics']
                if stats:
                    # 添加表头
                    headers = list(stats[0].keys())
                    prompt += "| " + " | ".join(headers) + " |\n"
                    prompt += "| " + " | ".join(["---"] * len(headers)) + " |\n"
                    # 添加数据行
                    for stat in stats:
                        row_values = [stat.get(header, "-") for header in headers]
                        prompt += "| " + " | ".join(row_values) + " |\n"
            
            # 添加Errors
            if dashboard.get('errors'):
                prompt += "\n### 错误信息\n"
                errors = dashboard['errors']
                for error in errors:
                    prompt += f"- {error.get('Error', 'Unknown Error')}: {error.get('Count', 0)}\n"
        
        prompt += "\n# 分析要求\n"
        prompt += "请基于上述结构化数据，生成详细的性能测试分析报告。\n"
        prompt += "\n## 分析重点\n"
        prompt += "请特别关注以下几个方面：\n"
        prompt += "1. **响应时间分析**：对平均响应时间、最大响应时间、90/95/99百分位响应时间进行详细解读，\n"
        prompt += "   例如：如果平均响应时间超过1000ms，说明系统响应偏慢，需要分析原因。\n"
        prompt += "2. **吞吐量分析**：分析系统的处理能力，评估是否满足业务需求。\n"
        prompt += "3. **错误率分析**：如果存在错误，分析错误类型和原因。\n"
        prompt += "4. **APDEX指数分析**：根据APDEX分数评估用户满意度。\n"
        prompt += "\n## 分析要求\n"
        prompt += "1. 请基于提供的结构化数据进行分析，不要使用模板化内容。\n"
        prompt += "2. 分析要具体到每个接口和场景，识别具体的性能瓶颈。\n"
        prompt += "3. 提供可操作的优化建议，包括代码层面、数据库层面、架构层面等。\n"
        prompt += "4. 使用表格和列表使分析结果清晰易读。\n"
        prompt += "5. 请使用中文进行分析，确保分析结果准确反映测试数据的实际情况。\n"
        
        return prompt
    
    def call_ai_service(self, prompt):
        """调用AI服务"""
        ai_service = self.config["ai_service"]
        api_key = self.config["api_keys"][ai_service]
        api_endpoint = self.config["api_endpoints"][ai_service]
        model_name = self.config["model_names"][ai_service]
        
        if not api_key:
            self.logger.warning(f"未配置 {ai_service} 的API密钥，使用模拟分析结果")
            return self.get_mock_analysis()
        
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                }
                
                payload = {
                    "model": model_name,
                    "messages": [
                        {
                            "role": "system",
                            "content": "你是一位专业的性能测试分析师，擅长分析JMeter压测报告并提供专业的性能优化建议。"
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "max_tokens": self.config["max_tokens"],
                    "temperature": self.config["temperature"]
                }
                
                # 增加超时时间到60秒
                response = requests.post(api_endpoint, headers=headers, json=payload, timeout=60)
                response.raise_for_status()
                
                result = response.json()
                return result["choices"][0]["message"]["content"]
            except requests.exceptions.Timeout as e:
                self.logger.warning(f"第 {attempt + 1} 次调用AI服务超时: {e}")
                if attempt < max_retries - 1:
                    self.logger.info(f"等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避
                else:
                    self.logger.error(f"调用AI服务多次超时，使用模拟分析结果")
                    return self.get_mock_analysis()
            except requests.exceptions.RequestException as e:
                self.logger.error(f"调用AI服务失败: {e}")
                return self.get_mock_analysis()
            except Exception as e:
                self.logger.error(f"调用AI服务失败: {e}")
                return self.get_mock_analysis()
    
    def get_mock_analysis(self):
        """获取模拟分析结果"""
        return """
# AI 分析报告

## 性能总体评估
基于提取的性能指标数据，系统性能表现需要进一步分析。请参考以下详细分析：

## 详细分析
- **响应时间分析**：需要根据具体的平均响应时间、最大响应时间、90/95/99百分位响应时间数据进行评估
- **吞吐量分析**：需要根据具体的TPS数据评估系统处理能力
- **错误率分析**：需要根据具体的错误率数据评估系统稳定性
- **APDEX分析**：需要根据具体的APDEX分数评估用户满意度

## 分析说明
由于AI服务调用暂时不可用，本分析基于结构化数据模板。实际分析需要：
1. 提取Statistics表格中的具体数值
2. 分析响应时间分布情况
3. 评估吞吐量是否满足业务需求
4. 分析错误类型和原因
5. 根据APDEX分数评估用户体验

## 优化建议方向
- **响应时间优化**：如果平均响应时间超过1000ms，需要优化系统性能
- **吞吐量提升**：如果TPS无法满足业务峰值需求，需要增加系统容量
- **错误率降低**：如果存在错误，需要分析错误原因并修复
- **用户体验改善**：根据APDEX分数采取相应措施提升用户满意度

## 总结
请使用Python脚本解析HTML报告，提取关键性能指标，然后基于结构化数据生成详细的分析结论。
"""
    
    def generate_ai_report(self, report_file, analysis_result, config):
        """生成AI分析报告"""
        try:
            # 提取项目名称和时间戳
            report_name = os.path.basename(report_file)
            project_match = re.search(r'^(.*?)_summary_(\d{8}_\d{6})\.html$', report_name)
            if project_match:
                project_name = project_match.group(1)
                timestamp = project_match.group(2)
            else:
                # 尝试其他格式的文件名
                project_match = re.search(r'^(.*?)_(\d{8}_\d{6})\.html$', report_name)
                if project_match:
                    project_name = project_match.group(1)
                    timestamp = project_match.group(2)
                else:
                    project_name = "default"
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 生成AI报告文件名
            ai_report_name = f"{project_name}_AIreport_{timestamp}.html"
            report_dir = os.path.dirname(report_file)
            ai_report_file = os.path.join(report_dir, ai_report_name)
            
            self.logger.info(f"生成AI分析报告文件名: {ai_report_name}")
            
            # 提取报告信息，包括报告列表
            with open(report_file, 'r', encoding='utf-8') as f:
                report_content = f.read()
            report_info = self.extract_report_info(report_content, report_file)
            
            # 生成HTML内容
            html_content = self.generate_ai_report_html(analysis_result, report_file, report_info)
            
            # 写入文件
            with open(ai_report_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            self.logger.info(f"AI分析报告生成完成: {ai_report_file}")
            return ai_report_file
        except Exception as e:
            self.logger.error(f"生成AI分析报告失败: {e}")
            return None
    
    def generate_ai_report_html(self, analysis_result, original_report, report_info=None):
        """生成AI分析报告HTML内容"""
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        original_report_name = os.path.basename(original_report)
        
        # 提取项目名称
        project_name = "性能测试"
        if original_report_name:
            # 尝试从原始报告文件名中提取项目名称
            project_match = re.search(r'^(.*?)_summary_\d{8}_\d{6}\.html$', original_report_name)
            if not project_match:
                project_match = re.search(r'^(.*?)_\d{8}_\d{6}\.html$', original_report_name)
            if project_match:
                project_name = project_match.group(1)
        
        # 生成报告标题
        report_title = f"{project_name} AI性能分析报告"
        
        # 处理AI分析结果，确保格式正确
        processed_analysis = analysis_result.strip()
        # 替换Markdown格式为HTML格式
        processed_analysis = processed_analysis.replace('# ', '<h3>').replace('</h3>', '</h3>')
        processed_analysis = processed_analysis.replace('## ', '<h4>').replace('</h4>', '</h4>')
        processed_analysis = processed_analysis.replace('### ', '<h5>').replace('</h5>', '</h5>')
        # 替换列表
        processed_analysis = processed_analysis.replace('\n- ', '\n<li>').replace('\n  - ', '\n<li>')
        # 替换换行符为HTML换行
        processed_analysis = processed_analysis.replace('\n', '<br>')
        # 修复列表标签
        processed_analysis = processed_analysis.replace('<br><li>', '<br><ul><li>').replace('<li><br>', '</li></ul><br>')
        
        # 使用三引号和字符串拼接，避免f-string中的花括号转义问题
        html = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 分析报告</title>
    <style>
        body {
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }
        .header {
            background-color: #333;
            color: white;
            padding: 40px;
            text-align: center;
        }
        .header h1 {
            margin: 0;
            font-size: 36px;
            font-weight: bold;
        }
        .header-info {
            background-color: #f8f9fa;
            padding: 20px;
            border-bottom: 1px solid #e9ecef;
        }
        .header-info .info-row {
            display: flex;
            flex-wrap: wrap;
            gap: 30px;
            margin-bottom: 10px;
        }
        .header-info .info-item {
            flex: 1;
            min-width: 200px;
        }
        .header-info .info-label {
            font-weight: bold;
            color: #495057;
        }
        .content {
            padding: 40px;
        }
        .section {
            margin-bottom: 50px;
        }
        .section h2 {
            color: #333;
            font-size: 24px;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #007bff;
        }
        .section h3 {
            color: #555;
            font-size: 20px;
            margin: 25px 0 15px 0;
        }
        .section h4 {
            color: #666;
            font-size: 18px;
            margin: 20px 0 10px 0;
        }
        .section h5 {
            color: #777;
            font-size: 16px;
            margin: 15px 0 10px 0;
        }
        .analysis-content {
            line-height: 1.8;
            color: #333;
            font-size: 16px;
        }
        .analysis-content p {
            margin-bottom: 15px;
        }
        .analysis-content ul {
            margin-bottom: 15px;
            padding-left: 20px;
        }
        .analysis-content li {
            margin-bottom: 8px;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }
        .metric-card {
            background-color: #f8f9fa;
            padding: 25px;
            border-radius: 8px;
            text-align: center;
            border: 1px solid #e9ecef;
            transition: transform 0.3s, box-shadow 0.3s;
        }
        .metric-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        .metric-value {
            font-size: 32px;
            font-weight: bold;
            color: #007bff;
            margin-bottom: 10px;
        }
        .metric-label {
            font-size: 14px;
            color: #6c757d;
        }
        .table-container {
            overflow-x: auto;
            margin: 30px 0;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }
        th {
            background-color: #007bff;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: bold;
        }
        td {
            padding: 12px;
            border-bottom: 1px solid #e9ecef;
        }
        tr:hover {
            background-color: #f8f9fa;
        }
        .report-card {
            background-color: #f8f9fa;
            padding: 30px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid #007bff;
        }
        .report-card h4 {
            margin-top: 0;
            color: #333;
            font-size: 16px;
        }
        .footer {
            background-color: #333;
            color: white;
            padding: 30px;
            text-align: center;
        }
        .back-link {
            display: inline-block;
            margin-top: 30px;
            padding: 12px 24px;
            background-color: #007bff;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            transition: background-color 0.3s;
            font-weight: bold;
        }
        .back-link:hover {
            background-color: #0069d9;
        }
        .summary-box {
            background-color: #e7f3ff;
            border: 1px solid #b3d7ff;
            border-radius: 8px;
            padding: 25px;
            margin: 30px 0;
        }
        .summary-box h3 {
            color: #0066cc;
            margin-top: 0;
        }
        .error-box {
            background-color: #f8d7da;
            border: 1px solid #f5c6cb;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
        }
        .error-box h4 {
            color: #721c24;
            margin-top: 0;
        }
        .highlight {
            background-color: #fff3cd;
            padding: 2px 4px;
            border-radius: 3px;
        }
        .warning {
            color: #dc3545;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>''' + report_title + '''</h1>
        </div>
        
        <div class="header-info">
            <div class="info-row">
                <div class="info-item">
                    <span class="info-label">分析时间:</span> ''' + current_time + '''
                </div>
                <div class="info-item">
                    <span class="info-label">原始报告:</span> ''' + original_report_name + '''
                </div>
                ''' + (f'''<div class="info-item">
                    <span class="info-label">报告数量:</span> {len(report_info['report_list'])}
                </div>''' if report_info and report_info.get('report_list') else '') + '''
            </div>
        </div>
        
        <div class="content">
            <div class="section">
                <h2>分析摘要</h2>
                <div class="summary-box">
                    <div class="analysis-content">
                        ''' + processed_analysis + '''
                    </div>
                </div>
            </div>
            
            ''' + (self.generate_detailed_metrics(report_info) if report_info else '') + '''
        </div>
        
        <div class="footer">
            <a href="''' + original_report_name + '''" class="back-link">返回原始报告</a>
            <p style="margin-top: 20px; font-size: 14px; color: #ccc;">报告生成时间: ''' + current_time + '''</p>
        </div>
    </div>
</body>
</html>
'''
        
        return html
    
    def generate_detailed_metrics(self, report_info):
        """生成详细的性能指标表格"""
        if not report_info or not report_info.get('report_list'):
            return ''
        
        detailed_metrics = '''
        <div class="section">
            <h2>详细性能指标</h2>
        '''
        
        # 分析报告列表中的所有报告
        analysis_results = self.analyze_report_list(report_info['report_list'])
        
        for result in analysis_results:
            report_name = result['report_name']
            dashboard = result['dashboard']
            
            detailed_metrics += f'''
            <div class="report-card">
                <h3>{report_name}</h3>
            '''
            
            # 添加Test and Report information
            if dashboard.get('test_info'):
                detailed_metrics += '''
                <h4>测试信息</h4>
                <div class="table-container">
                    <table>
                        <tr>
                            <th>项目</th>
                            <th>值</th>
                        </tr>
                '''
                
                for key, value in dashboard['test_info'].items():
                    detailed_metrics += f'''
                        <tr>
                            <td>{key}</td>
                            <td>{value}</td>
                        </tr>
                    '''
                
                detailed_metrics += '''
                    </table>
                </div>
                '''
            
            # 添加APDEX
            if dashboard.get('apdex') and dashboard['apdex'].get('score'):
                detailed_metrics += f'''
                <h4>APDEX 性能指数</h4>
                <div class="metrics-grid">
                    <div class="metric-card">
                        <div class="metric-value">{dashboard['apdex']['score']}</div>
                        <div class="metric-label">APDEX 分数</div>
                    </div>
                </div>
                '''
            
            # 添加Statistics
            if dashboard.get('statistics'):
                detailed_metrics += '''
                <h4>性能统计</h4>
                <div class="table-container">
                    <table>
                        <tr>
                '''
                
                # 添加表头
                if dashboard['statistics']:
                    headers = list(dashboard['statistics'][0].keys())
                    for header in headers:
                        detailed_metrics += f'''
                            <th>{header}</th>
                        '''
                
                detailed_metrics += '''
                        </tr>
                '''
                
                # 添加数据行
                for row in dashboard['statistics']:
                    detailed_metrics += '''
                        <tr>
                    '''
                    for header in headers:
                        detailed_metrics += f'''
                            <td>{row.get(header, '-')}</td>
                        '''
                    detailed_metrics += '''
                        </tr>
                    '''
                
                detailed_metrics += '''
                    </table>
                </div>
                '''
            
            # 添加Errors
            if dashboard.get('errors'):
                detailed_metrics += '''
                <h4>错误信息</h4>
                <div class="error-box">
                    <div class="table-container">
                        <table>
                            <tr>
                '''
                
                # 添加表头
                if dashboard['errors']:
                    headers = list(dashboard['errors'][0].keys())
                    for header in headers:
                        detailed_metrics += f'''
                                <th>{header}</th>
                            '''
                
                detailed_metrics += '''
                            </tr>
                '''
                
                # 添加数据行
                for row in dashboard['errors']:
                    detailed_metrics += '''
                            <tr>
                        '''
                    for header in headers:
                        detailed_metrics += f'''
                                <td>{row.get(header, '-')}</td>
                            '''
                    detailed_metrics += '''
                            </tr>
                        '''
                
                detailed_metrics += '''
                        </table>
                    </div>
                </div>
                '''
            
            # 添加Top 5 Errors by sampler
            if dashboard.get('top_errors'):
                detailed_metrics += '''
                <h4>Top 5 错误</h4>
                <div class="table-container">
                    <table>
                        <tr>
                '''
                
                # 添加表头
                if dashboard['top_errors']:
                    headers = list(dashboard['top_errors'][0].keys())
                    for header in headers:
                        detailed_metrics += f'''
                            <th>{header}</th>
                        '''
                
                detailed_metrics += '''
                        </tr>
                '''
                
                # 添加数据行
                for row in dashboard['top_errors']:
                    detailed_metrics += '''
                        <tr>
                    '''
                    for header in headers:
                        detailed_metrics += f'''
                            <td>{row.get(header, '-')}</td>
                        '''
                    detailed_metrics += '''
                        </tr>
                    '''
                
                detailed_metrics += '''
                    </table>
                </div>
                '''
            
            detailed_metrics += '''
            </div>
            '''
        
        detailed_metrics += '''
        </div>
        '''
        
        return detailed_metrics
    
    def update_original_report(self, report_file, ai_report_file):
        """更新原始报告，添加AI分析链接"""
        try:
            # 读取原始报告内容
            with open(report_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 提取AI报告文件名
            ai_report_name = os.path.basename(ai_report_file)
            self.logger.info(f"AI报告文件名: {ai_report_name}")
            
            # 检查是否包含AI分析部分
            import re
            
            # 定义原始AI分析部分的模式（包含"无"文本）
            # 使用更精确的正则表达式，确保只匹配AI分析部分
            original_ai_pattern = r'<div\s+class="stat-card"\s+style="background-color:\s*#fff3cd;">\s*<div\s+class="stat-value"\s+style="color:\s*#666;">\s*AI分析\s*<\/div>\s*<div\s+style="font-size:\s*12px;\s*color:\s*#dc3545;\s*margin-top:\s*5px;">\s*无\s*<\/div>\s*<\/div>'
            
            # 定义更新后AI分析部分的模式（包含链接）
            # 使用更精确的正则表达式，确保只匹配AI分析部分
            updated_ai_pattern = r'<div\s+class="stat-card"\s+style="background-color:\s*#fff3cd;">\s*<div\s+class="stat-value"\s+style="color:\s*#666;">\s*<a\s+href=".*?"\s+style="color:\s*#28a745;\s*text-decoration:\s*none;"\s+target="_blank">AI分析<\/a>\s*<\/div>\s*<div\s+style="font-size:\s*12px;\s*color:\s*#666;\s*margin-top:\s*5px;">\s*点击查看\s*<\/div>\s*<\/div>'
            
            # 检查是否是原始AI分析部分（需要更新）
            if re.search(original_ai_pattern, content, flags=re.DOTALL):
                self.logger.info("找到原始AI分析部分，需要更新")
                
                # 创建新的AI分析部分，包含链接
                new_ai_section = f'''<div class="stat-card" style="background-color: #fff3cd;">
                    <div class="stat-value" style="color: #666;">
                        <a href="{ai_report_name}" style="color: #28a745; text-decoration: none;" target="_blank">AI分析</a>
                    </div>
                    <div style="font-size: 12px; color: #666; margin-top: 5px;">
                        点击查看
                    </div>
                </div>'''
                
                # 替换原始的AI分析部分
                # 使用更灵活的正则表达式进行替换
                new_content = re.sub(original_ai_pattern, new_ai_section, content, flags=re.DOTALL)
            # 检查是否已经是更新后的AI分析部分
            elif re.search(updated_ai_pattern, content, flags=re.DOTALL):
                self.logger.info("AI分析部分已经更新过")
                new_content = content
            else:
                self.logger.info("未找到AI分析部分")
                new_content = content
            
            # 写入更新后的内容
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            if re.search(original_ai_pattern, content, flags=re.DOTALL):
                self.logger.info(f"已更新原始报告，添加AI分析链接")
            elif re.search(updated_ai_pattern, content, flags=re.DOTALL):
                self.logger.info(f"AI分析部分已经更新过")
            else:
                self.logger.info(f"未找到AI分析部分")
        except Exception as e:
            self.logger.error(f"更新原始报告失败: {e}")
    
    def find_latest_report(self, reports_dir):
        """查找最新的报告文件"""
        try:
            latest_report = None
            latest_time = 0
            
            for root, dirs, files in os.walk(reports_dir):
                for file in files:
                    if file.endswith('.html') and '_summary_' in file:
                        file_path = os.path.join(root, file)
                        mod_time = os.path.getmtime(file_path)
                        if mod_time > latest_time:
                            latest_time = mod_time
                            latest_report = file_path
            
            return latest_report
        except Exception as e:
            self.logger.error(f"查找最新报告失败: {e}")
            return None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='JMeter 压测报告 AI 分析脚本')
    parser.add_argument('--report', type=str, help='指定要分析的报告文件')
    parser.add_argument('--config', type=str, help='指定配置文件路径')
    parser.add_argument('--reports-dir', type=str, default='../reports', help='报告目录路径')
    
    args = parser.parse_args()
    
    analyzer = AIAnalyzer(args.config)
    
    # 确定要分析的报告文件
    if args.report:
        report_file = args.report
    else:
        report_file = analyzer.find_latest_report(args.reports_dir)
    
    if not report_file:
        print("未找到报告文件")
        return
    
    print(f"分析报告: {report_file}")
    
    # 分析报告
    ai_report = analyzer.analyze_report(report_file, {})
    
    if ai_report:
        print(f"AI 分析报告生成完成: {ai_report}")
    else:
        print("AI 分析报告生成失败")


if __name__ == "__main__":
    main()