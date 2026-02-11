#!/usr/bin/env python3
"""
简单的JMeter报告AI分析脚本
功能：
1. 从summary HTML文件中提取报告列表
2. 读取每个报告对应的index.html文件
3. 提取HTML中的文字和表格数据
4. 将提取的数据发送给AI进行分析
"""

import os
import re
import json
import requests
import datetime


class SimpleAIAnalyzer:
    """简单的AI分析器类"""
    
    def __init__(self, config_file=None):
        """初始化分析器"""
        self.config = self.load_config(config_file)
    
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
                "qianwen": "https://dashscope.aliyun.com/api​",
                "moon": "https://api.moonshot.cn/v1/chat/completions",
                "yunwu": "https://ark.cn-shanghai.volces.com/api/v3/completions"
            },
            "model_names": {
                "deepseek": "deepseek-chat",
                "qianwen": "qwen-plus",
                "moon": "moonshot-v1-8k",
                "yunwu": "skylark-lite​"
            },
            "max_tokens": 2000,
            "temperature": 0.7
        }
        
        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                
                # 合并配置
                for key, value in user_config.items():
                    if key in default_config and isinstance(default_config[key], dict) and isinstance(value, dict):
                        default_config[key].update(value)
                    else:
                        default_config[key] = value
            except Exception as e:
                print(f"加载配置文件失败: {e}")
        
        return default_config
    
    def extract_report_list(self, summary_file):
        """从summary HTML文件中提取报告列表"""
        report_list = []
        
        try:
            with open(summary_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            print(f"读取summary文件成功，文件大小: {len(content)} 字符")
            
            # 提取报告列表中的链接，使用更精确的正则表达式
            report_links = re.findall(r'<a\s+href="([^"]+)"[^>]*>\s*查看详细报告\s*<\/a>', content, re.IGNORECASE)
            
            print(f"找到 {len(report_links)} 个报告链接")
            for i, link in enumerate(report_links):
                print(f"链接 {i+1}: {link}")
            
            summary_dir = os.path.dirname(summary_file)
            print(f"summary文件目录: {summary_dir}")
            
            for link in report_links:
                # 构建完整的报告路径
                full_path = os.path.join(summary_dir, link)
                print(f"构建的完整路径: {full_path}")
                
                # 确保路径存在
                if os.path.exists(full_path):
                    print(f"路径存在: {full_path}")
                    report_info = {
                        "path": full_path,
                        "name": os.path.basename(os.path.dirname(full_path)),
                        "link": link
                    }
                    report_list.append(report_info)
                else:
                    print(f"路径不存在: {full_path}")
        except Exception as e:
            print(f"提取报告列表失败: {e}")
        
        print(f"最终提取到 {len(report_list)} 个报告")
        return report_list
    
    def extract_html_content(self, html_file):
        """提取HTML文件中的文字和表格数据"""
        try:
            with open(html_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            extracted_data = {
                "file": html_file,
                "content": {},
                "tables": []
            }
            
            # 提取Test and Report information
            test_info_match = re.search(r'<h2>Test and Report information<\/h2>(.*?)<\/div>', content, re.DOTALL)
            if test_info_match:
                test_info_html = test_info_match.group(1)
                test_info_items = re.findall(r'<tr>(.*?)<\/tr>', test_info_html, re.DOTALL)
                test_info = {}
                for item in test_info_items:
                    key_match = re.search(r'<td[^>]*>(.*?)<\/td>', item)
                    value_match = re.search(r'<td[^>]*>(.*?)<\/td>', item, re.DOTALL)
                    if key_match and value_match:
                        key = key_match.group(1).strip()
                        value = value_match.group(1).strip()
                        # 去除引号
                        value = value.replace('"', '')
                        test_info[key] = value
                extracted_data["content"]["test_info"] = test_info
            
            # 查找dashboard.js文件路径
            dashboard_js_match = re.search(r'<script src="(content/js/dashboard.js)"><\/script>', content)
            if dashboard_js_match:
                dashboard_js_path = os.path.join(os.path.dirname(html_file), dashboard_js_match.group(1))
                print(f"找到dashboard.js文件: {dashboard_js_path}")
                
                # 读取dashboard.js文件
                if os.path.exists(dashboard_js_path):
                    with open(dashboard_js_path, 'r', encoding='utf-8') as f:
                        js_content = f.read()
                    
                    # 简化的方法：直接搜索关键词
                    # 提取APDEX分数
                    if '#apdexTable' in js_content:
                        # 搜索APDEX分数
                        apdex_start = js_content.find('#apdexTable')
                        if apdex_start != -1:
                            # 搜索overall数据
                            overall_start = js_content.find('"overall":', apdex_start)
                            if overall_start != -1:
                                data_start = js_content.find('[', overall_start)
                                data_end = js_content.find(']', data_start)
                                if data_start != -1 and data_end != -1:
                                    apdex_values = js_content[data_start+1:data_end].split(',')
                                    if apdex_values:
                                        apdex_score = apdex_values[0].strip()
                                        extracted_data["content"]["apdex_score"] = apdex_score
                                        print(f"提取到APDEX分数: {apdex_score}")
                    
                    # 提取Statistics数据
                    if '#statisticsTable' in js_content:
                        # 搜索Statistics表格数据
                        stats_start = js_content.find('#statisticsTable')
                        if stats_start != -1:
                            # 提取表头
                            titles_start = js_content.find('"titles":', stats_start)
                            titles_end = js_content.find(']', titles_start)
                            if titles_start != -1 and titles_end != -1:
                                titles_str = js_content[titles_start+8:titles_end]
                                # 解析表头
                                headers = re.findall(r'"([^"]+)"', titles_str)
                                print(f"提取到表头: {headers}")
                            
                            # 提取总体数据
                            overall_start = js_content.find('"overall":', stats_start)
                            if overall_start != -1:
                                data_start = js_content.find('[', overall_start)
                                data_end = js_content.find(']', data_start)
                                if data_start != -1 and data_end != -1:
                                    overall_data_str = js_content[data_start+1:data_end]
                                    overall_data = []
                                    # 处理字符串和数字混合的情况
                                    for item in overall_data_str.split(','):
                                        item = item.strip()
                                        if item.startswith('"') and item.endswith('"'):
                                            overall_data.append(item[1:-1])
                                        else:
                                            overall_data.append(item)
                                    print(f"提取到总体数据: {overall_data[:5]}...")
                            
                            # 提取items数据
                            items_start = js_content.find('"items":', stats_start)
                            if items_start != -1:
                                items_end = js_content.find(']', items_start)
                                if items_end != -1:
                                    items_str = js_content[items_start+8:items_end]
                                    # 提取每个项目的数据
                                    item_data_matches = re.findall(r'"data":\s*\[(.*?)\]', items_str)
                                    
                                    # 构建表格数据
                                    table_data = []
                                    if headers and overall_data:
                                        if len(overall_data) == len(headers):
                                            row_data = {}
                                            for i, header in enumerate(headers):
                                                row_data[header] = overall_data[i]
                                            table_data.append(row_data)
                                    
                                    # 添加items数据
                                    for item_data_str in item_data_matches:
                                        item_data = []
                                        for item in item_data_str.split(','):
                                            item = item.strip()
                                            if item.startswith('"') and item.endswith('"'):
                                                item_data.append(item[1:-1])
                                            else:
                                                item_data.append(item)
                                        if headers and len(item_data) == len(headers):
                                            row_data = {}
                                            for i, header in enumerate(headers):
                                                row_data[header] = item_data[i]
                                            table_data.append(row_data)
                                    
                                    if table_data:
                                        extracted_data["tables"].append({
                                            "name": "Statistics",
                                            "headers": headers,
                                            "data": table_data
                                        })
                                        print(f"提取到Statistics表格数据: {len(table_data)} 行")
                    
                    # 提取Errors数据
                    if '#errorsTable' in js_content:
                        # 搜索Errors表格数据
                        errors_start = js_content.find('#errorsTable')
                        if errors_start != -1:
                            # 提取表头
                            titles_start = js_content.find('"titles":', errors_start)
                            titles_end = js_content.find(']', titles_start)
                            if titles_start != -1 and titles_end != -1:
                                titles_str = js_content[titles_start+8:titles_end]
                                headers = re.findall(r'"([^"]+)"', titles_str)
                                print(f"提取到Errors表头: {headers}")
                            
                            # 提取items数据
                            items_start = js_content.find('"items":', errors_start)
                            if items_start != -1:
                                items_end = js_content.find(']', items_start)
                                if items_end != -1:
                                    items_str = js_content[items_start+8:items_end]
                                    item_data_matches = re.findall(r'"data":\s*\[(.*?)\]', items_str)
                                    
                                    table_data = []
                                    for item_data_str in item_data_matches:
                                        item_data = []
                                        for item in item_data_str.split(','):
                                            item = item.strip()
                                            if item.startswith('"') and item.endswith('"'):
                                                item_data.append(item[1:-1])
                                            else:
                                                item_data.append(item)
                                        if headers and len(item_data) == len(headers):
                                            row_data = {}
                                            for i, header in enumerate(headers):
                                                row_data[header] = item_data[i]
                                            table_data.append(row_data)
                                    
                                    if table_data:
                                        extracted_data["tables"].append({
                                            "name": "Errors",
                                            "headers": headers,
                                            "data": table_data
                                        })
                                        print(f"提取到Errors表格数据: {len(table_data)} 行")
            
            return extracted_data
        except Exception as e:
            print(f"提取HTML内容失败: {e}")
            return {"file": html_file, "content": {}, "tables": []}
    
    def build_ai_prompt(self, extracted_data_list):
        """构建AI分析提示"""
        prompt = "你是性能测试专家，分析一下这个jmeter html报告\n\n"
        
        print(f"开始构建AI提示，处理 {len(extracted_data_list)} 个报告")
        
        for i, extracted_data in enumerate(extracted_data_list, 1):
            file_name = os.path.basename(extracted_data["file"])
            print(f"处理报告 {i}: {file_name}")
            prompt += f"## 报告 {i}: {file_name}\n\n"
            
            # 添加测试信息
            if extracted_data["content"].get("test_info"):
                print(f"  提取到测试信息: {len(extracted_data['content']['test_info'])} 项")
                prompt += "### 测试信息\n"
                test_info = extracted_data["content"]["test_info"]
                for key, value in test_info.items():
                    prompt += f"- {key}: {value}\n"
                prompt += "\n"
            else:
                print("  未提取到测试信息")
            
            # 添加APDEX
            if extracted_data["content"].get("apdex_score"):
                print(f"  提取到APDEX分数: {extracted_data['content']['apdex_score']}")
                prompt += "### APDEX 性能指数\n"
                prompt += f"- APDEX 分数: {extracted_data['content']['apdex_score']}\n\n"
            else:
                print("  未提取到APDEX分数")
            
            # 添加表格数据
            print(f"  提取到 {len(extracted_data['tables'])} 个表格")
            for table in extracted_data["tables"]:
                print(f"  处理表格: {table['name']}, 包含 {len(table['data'])} 行数据")
                prompt += f"### {table['name']} 表格\n"
                # 添加表头
                headers = table['headers']
                prompt += "| " + " | ".join(headers) + " |\n"
                prompt += "| " + " | ".join(["---"] * len(headers)) + " |\n"
                # 添加数据行
                for row in table['data']:
                    row_values = [row.get(header, "-") for header in headers]
                    prompt += "| " + " | ".join(row_values) + " |\n"
                prompt += "\n"
        
        print(f"AI提示构建完成，长度: {len(prompt)}")
        return prompt
    
    def call_ai_service(self, prompt):
        """调用AI服务"""
        ai_service = self.config["ai_service"]
        api_key = self.config["api_keys"][ai_service]
        api_endpoint = self.config["api_endpoints"][ai_service]
        model_name = self.config["model_names"][ai_service]
        
        if not api_key:
            print(f"未配置 {ai_service} 的API密钥，无法调用AI服务")
            return "需要配置API密钥才能使用AI分析功能"
        
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
            
            response = requests.post(api_endpoint, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"调用AI服务失败: {e}")
            return f"调用AI服务失败: {e}"
    
    def analyze_summary_report(self, summary_file):
        """分析summary报告"""
        print(f"开始分析报告: {summary_file}")
        
        # 提取报告列表
        report_list = self.extract_report_list(summary_file)
        print(f"找到 {len(report_list)} 个详细报告")
        
        # 提取每个报告的内容
        extracted_data_list = []
        for report_info in report_list:
            print(f"提取报告内容: {report_info['name']}")
            extracted_data = self.extract_html_content(report_info['path'])
            
            # 输出提取到的详细数据
            print("\n提取到的详细数据:")
            print("=" * 60)
            
            # 输出测试信息
            content = extracted_data.get("content", {})
            if content:
                print("测试基本信息:")
                test_info = content.get("test_info", {})
                if test_info:
                    for key, value in test_info.items():
                        print(f"- {key}: {value}")
                else:
                    print("- 无测试信息")
            
            # 输出APDEX分数
            apdex_score = content.get("apdex_score", "")
            if apdex_score:
                print(f"APDEX性能指数: {apdex_score}")
            else:
                print("APDEX性能指数: 无")
            
            # 输出表格数据
            tables = extracted_data.get("tables", [])
            if tables:
                print("表格数据:")
                for table in tables:
                    table_name = table.get("name", "Unknown")
                    data = table.get("data", [])
                    print(f"- {table_name}: {len(data)} 行数据")
                    
                    # 输出Statistics表格的前几行数据
                    if table_name == "Statistics" and data:
                        print("  前2行数据:")
                        headers = table.get("headers", [])
                        if headers:
                            # 打印表头
                            header_str = "  | " + " | ".join([h[:10].ljust(10) for h in headers]) + " |"
                            print(header_str)
                            print("  | " + " | ".join(["-" * 10 for _ in headers]) + " |")
                        
                        # 打印前2行数据
                        for i, row in enumerate(data[:2]):
                            row_values = [str(row.get(h, ""))[:10].ljust(10) for h in headers]
                            row_str = f"  | {' | '.join(row_values)} |"
                            print(row_str)
            
            print("=" * 60)
            extracted_data_list.append(extracted_data)
        
        # 构建AI提示
        prompt = self.build_ai_prompt(extracted_data_list)
        print(f"构建AI提示完成，长度: {len(prompt)}")
        
        # 调用AI服务
        analysis_result = self.call_ai_service(prompt)
        print(f"AI分析完成")
        
        # 生成分析报告文件
        summary_dir = os.path.dirname(summary_file)
        summary_name = os.path.basename(summary_file)
        
        # 提取项目名称
        project_name = "default"
        if '_summary_' in summary_name:
            project_name = summary_name.split('_summary_')[0]
            # 处理可能的项目名称重复问题
            # 例如，从 "入学评测_入学评测_5_list_20260209" 中提取 "入学评测"
            parts = project_name.split('_')
            if len(parts) > 1:
                # 检查是否有重复的项目名称
                # 例如，"入学评测_入学评测_5_list_20260209" 中，前两个部分相同
                if parts[0] == parts[1]:
                    project_name = parts[0]
        
        # 生成时间戳
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 检查并复制marked.min.js文件到reports目录
        marked_js_source = os.path.join(os.path.dirname(__file__), 'static', 'js', 'marked.min.js')
        marked_js_dest_dir = os.path.join(summary_dir, 'static', 'js')
        marked_js_dest = os.path.join(marked_js_dest_dir, 'marked.min.js')
        
        print(f"检查marked.min.js文件...")
        print(f"源文件路径: {marked_js_source}")
        print(f"目标文件路径: {marked_js_dest}")
        
        if os.path.exists(marked_js_source):
            # 创建目标目录
            os.makedirs(marked_js_dest_dir, exist_ok=True)
            # 复制文件
            try:
                import shutil
                shutil.copy2(marked_js_source, marked_js_dest)
                print(f"成功复制marked.min.js到{marked_js_dest}")
            except Exception as e:
                print(f"复制marked.min.js失败: {e}")
        else:
            print(f"marked.min.js源文件不存在: {marked_js_source}")
        
        # 生成AIReport报告
        if '_summary_' in summary_name:
            ai_report_name = summary_name.replace('_summary_', '_AIReport_')
        else:
            ai_report_name = f"AIReport_{timestamp}.html"
        
        ai_report_path = os.path.join(summary_dir, ai_report_name)
        
        # 生成AIReport报告
        simple_analysis_content = self.generate_simple_analysis_html(analysis_result, summary_file, "")
        
        with open(ai_report_path, 'w', encoding='utf-8') as f:
            f.write(simple_analysis_content)
        
        # 更新原始报告，添加AI分析链接（指向AIReport报告）
        self.update_original_report(summary_file, ai_report_name)
        
        print(f"AI分析报告生成完成: {ai_report_path}")
        return ai_report_path
    
    def generate_ai_report_html(self, analysis_result, summary_file, project_name):
        """生成AIReport HTML内容"""
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        summary_name = os.path.basename(summary_file)
        
        # 生成报告标题
        report_title = f"{project_name} AI性能分析报告"
        
        # 处理AI分析结果，确保格式正确
        processed_analysis = analysis_result.strip()
        
        # 生成HTML内容
        html = f'''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report_title}</title>
    <script src="./static/js/marked.min.js"></script>
    <style>
        body {{
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }}
        .header {{
            background-color: #333;
            color: white;
            padding: 40px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 36px;
            font-weight: bold;
        }}
        .header-info {{
            background-color: #f8f9fa;
            padding: 20px;
            border-bottom: 1px solid #e9ecef;
        }}
        .header-info .info-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 30px;
            margin-bottom: 10px;
        }}
        .header-info .info-item {{
            flex: 1;
            min-width: 200px;
        }}
        .header-info .info-label {{
            font-weight: bold;
            color: #495057;
        }}
        .content {{
            padding: 40px;
        }}
        .section {{
            margin-bottom: 50px;
        }}
        .section h2 {{
            color: #333;
            font-size: 24px;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #007bff;
        }}
        .analysis-content {{
            line-height: 1.8;
            color: #333;
            font-size: 16px;
        }}
        .analysis-content h1, .analysis-content h2, .analysis-content h3, .analysis-content h4, .analysis-content h5, .analysis-content h6 {{
            color: #333;
            margin-top: 30px;
            margin-bottom: 15px;
        }}
        .analysis-content h1 {{
            font-size: 24px;
            border-bottom: 2px solid #e9ecef;
            padding-bottom: 10px;
        }}
        .analysis-content h2 {{
            font-size: 20px;
            border-bottom: 1px solid #e9ecef;
            padding-bottom: 8px;
        }}
        .analysis-content h3 {{
            font-size: 18px;
        }}
        .analysis-content h4 {{
            font-size: 16px;
        }}
        .analysis-content p {{
            margin-bottom: 15px;
        }}
        .analysis-content ul, .analysis-content ol {{
            margin-bottom: 15px;
            padding-left: 30px;
        }}
        .analysis-content li {{
            margin-bottom: 8px;
        }}
        .analysis-content strong {{
            font-weight: bold;
            color: #333;
        }}
        .analysis-content em {{
            font-style: italic;
        }}
        .analysis-content code {{
            background-color: #f8f9fa;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: 'Courier New', Courier, monospace;
        }}
        .analysis-content pre {{
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            margin-bottom: 15px;
        }}
        .analysis-content pre code {{
            background-color: transparent;
            padding: 0;
        }}
        .analysis-content blockquote {{
            border-left: 4px solid #007bff;
            padding-left: 15px;
            margin: 15px 0;
            color: #666;
        }}
        .analysis-content table {{
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
            font-size: 14px;
        }}
        .analysis-content th, .analysis-content td {{
            border: 1px solid #ddd;
            padding: 10px;
            text-align: left;
        }}
        .analysis-content th {{
            background-color: #f2f2f2;
            font-weight: bold;
            color: #333;
        }}
        .analysis-content tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        .analysis-content tr:hover {{
            background-color: #f5f5f5;
        }}
        .footer {{
            background-color: #333;
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .back-link {{
            display: inline-block;
            margin-top: 30px;
            padding: 12px 24px;
            background-color: #007bff;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            transition: background-color 0.3s;
            font-weight: bold;
        }}
        .back-link:hover {{
            background-color: #0069d9;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{report_title}</h1>
        </div>
        
        <div class="header-info">
            <div class="info-row">
                <div class="info-item">
                    <span class="info-label">分析时间:</span> {current_time}
                </div>
                <div class="info-item">
                    <span class="info-label">原始报告:</span> {summary_name}
                </div>
            </div>
        </div>
        
        <div class="content">
            <div class="section">
                <h2>分析摘要</h2>
                <div class="analysis-content" id="markdown-content">
                    <!-- Markdown内容将通过JavaScript渲染 -->
                </div>
            </div>
        </div>
        
        <div class="footer">
            <a href="{summary_name}" class="back-link">返回原始报告</a>
            <p style="margin-top: 20px; font-size: 14px; color: #ccc;">报告生成时间: {current_time}</p>
        </div>
    </div>
    <script>
        // 使用marked.js渲染Markdown
        document.addEventListener('DOMContentLoaded', function() {{
            const markdownContent = `{processed_analysis}`;
            const htmlContent = marked(markdownContent);
            document.getElementById('markdown-content').innerHTML = htmlContent;
        }});
    </script>
</body>
</html>
'''
        
        return html
    
    def generate_simple_analysis_html(self, analysis_result, summary_file, ai_report_name):
        """生成简单分析HTML内容，包含链接到AIReport"""
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        summary_name = os.path.basename(summary_file)
        
        # 提取项目名称
        import re
        project_name_match = re.search(r'^(.*?)_', summary_name)
        if project_name_match:
            project_name = project_name_match.group(1)
        else:
            project_name = "未知项目"
        
        # 生成报告标题
        report_title = f"{project_name} AI性能测试报告分析"
        
        # 过滤掉开头的自我介绍语句
        import re
        # 匹配所有以"好的，作为"开头的语句，直到第一个句号或逗号
        filtered_analysis = re.sub(r'^好的，作为.*?(?:[。，]|$)\s*', '', analysis_result.strip(), flags=re.DOTALL)
        # 处理AI分析结果，将Markdown转换为HTML
        processed_analysis = self.markdown_to_html(filtered_analysis)
        
        # 生成HTML内容
        html = f'''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report_title}</title>
    <style>
        body {{
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            text-align: center;
        }}
        h2 {{
            color: #333;
            font-size: 20px;
            margin-top: 30px;
            margin-bottom: 15px;
            padding-bottom: 8px;
            border-bottom: 2px solid #007bff;
        }}
        h3 {{
            color: #555;
            font-size: 18px;
            margin-top: 20px;
            margin-bottom: 10px;
        }}
        h4 {{
            color: #666;
            font-size: 16px;
            margin-top: 15px;
            margin-bottom: 8px;
        }}
        .info {{ 
            margin-bottom: 20px;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 5px;
        }}
        .info-label {{
            font-weight: bold;
        }}
        .analysis-content {{
            line-height: 1.8;
            margin: 20px 0;
        }}
        .analysis-content p {{
            margin-bottom: 15px;
        }}
        .analysis-content ul, .analysis-content ol {{
            margin-bottom: 15px;
            padding-left: 30px;
        }}
        .analysis-content li {{
            margin-bottom: 8px;
        }}
        .analysis-content strong {{ 
            font-weight: bold;
            color: #333;
        }}
        .analysis-content em {{
            font-style: italic;
        }}
        .analysis-content code {{
            background-color: #f8f9fa;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: 'Courier New', Courier, monospace;
        }}
        .analysis-content pre {{
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            margin-bottom: 15px;
        }}
        .analysis-content pre code {{
            background-color: transparent;
            padding: 0;
        }}
        .analysis-content blockquote {{
            border-left: 4px solid #007bff;
            padding-left: 15px;
            margin: 15px 0;
            color: #666;
        }}
        .ai-report-link {{
            display: inline-block;
            margin: 20px 0;
            padding: 10px 20px;
            background-color: #007bff;
            color: white;
            text-decoration: none;
            border-radius: 5px;
        }}
        .ai-report-link:hover {{
            background-color: #0069d9;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{report_title}</h1>
        <div class="info">
            <p><span class="info-label">分析时间:</span> {current_time}</p>
            <p><span class="info-label">原始报告:</span> {summary_name}</p>
        </div>
        <div class="analysis-content">
            {processed_analysis}
        </div>
        <a href="{summary_name}" class="ai-report-link" target="_blank">返回测试报告汇总</a>
    </div>
</body>
</html>
'''
        
        return html
    
    def markdown_to_html(self, markdown_text):
        """将Markdown文本转换为HTML"""
        # 首先处理表格，因为表格需要特殊处理
        def process_tables(text):
            lines = text.split('\n')
            in_table = False
            table_lines = []
            result = []
            
            for line in lines:
                if '|' in line:
                    if not in_table:
                        in_table = True
                    table_lines.append(line.strip())
                else:
                    if in_table:
                        # 处理表格
                        if len(table_lines) >= 2:
                            # 提取表头
                            header_line = table_lines[0]
                            separator_line = table_lines[1]
                            data_lines = table_lines[2:]
                            
                            # 解析表头
                            headers = [h.strip() for h in header_line.split('|') if h.strip()]
                            
                            # 生成HTML表格
                            html_table = '<table style="border-collapse: collapse; width: 100%; margin: 20px 0;">' 
                            html_table += '<thead>'
                            html_table += '<tr>'
                            for header in headers:
                                html_table += f'<th style="border: 1px solid #ddd; padding: 8px; text-align: left; background-color: #f2f2f2;">{header}</th>'
                            html_table += '</tr>'
                            html_table += '</thead>'
                            html_table += '<tbody>'
                            
                            # 处理数据行
                            for data_line in data_lines:
                                cells = [c.strip() for c in data_line.split('|') if c.strip()]
                                if cells:
                                    html_table += '<tr>'
                                    for cell in cells:
                                        html_table += f'<td style="border: 1px solid #ddd; padding: 8px;">{cell}</td>'
                                    html_table += '</tr>'
                            
                            html_table += '</tbody>'
                            html_table += '</table>'
                            result.append(html_table)
                        
                        # 重置表格状态
                        in_table = False
                        table_lines = []
                    
                    # 添加非表格行
                    result.append(line)
            
            # 处理最后一个表格
            if in_table and len(table_lines) >= 2:
                # 提取表头
                header_line = table_lines[0]
                separator_line = table_lines[1]
                data_lines = table_lines[2:]
                
                # 解析表头
                headers = [h.strip() for h in header_line.split('|') if h.strip()]
                
                # 生成HTML表格
                html_table = '<table style="border-collapse: collapse; width: 100%; margin: 20px 0;">' 
                html_table += '<thead>'
                html_table += '<tr>'
                for header in headers:
                    html_table += f'<th style="border: 1px solid #ddd; padding: 8px; text-align: left; background-color: #f2f2f2;">{header}</th>'
                html_table += '</tr>'
                html_table += '</thead>'
                html_table += '<tbody>'
                
                # 处理数据行
                for data_line in data_lines:
                    cells = [c.strip() for c in data_line.split('|') if c.strip()]
                    if cells:
                        html_table += '<tr>'
                        for cell in cells:
                            html_table += f'<td style="border: 1px solid #ddd; padding: 8px;">{cell}</td>'
                        html_table += '</tr>'
                
                html_table += '</tbody>'
                html_table += '</table>'
                result.append(html_table)
            
            return '\n'.join(result)
        
        # 处理表格
        html = process_tables(markdown_text)
        
        # 处理标题
        html = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        
        # 处理粗体
        html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
        
        # 处理斜体
        html = re.sub(r'\*(.*?)\*', r'<em>\1</em>', html)
        
        # 处理代码
        html = re.sub(r'`(.*?)`', r'<code>\1</code>', html)
        
        # 处理代码块
        html = re.sub(r'```(.*?)```', r'<pre><code>\1</code></pre>', html, flags=re.DOTALL)
        
        # 处理引用
        html = re.sub(r'^> (.*?)$', r'<blockquote>\1</blockquote>', html, flags=re.MULTILINE)
        
        # 处理无序列表
        html = re.sub(r'^- (.*?)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        # 包装无序列表项
        html = re.sub(r'(<li>.*?</li>)', r'<ul>\1</ul>', html, flags=re.DOTALL)
        
        # 处理有序列表
        html = re.sub(r'^\d+\. (.*?)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        # 包装有序列表项
        html = re.sub(r'(<li>.*?</li>)', r'<ol>\1</ol>', html, flags=re.DOTALL)
        
        # 处理分割线
        html = re.sub(r'^---$', r'<hr>', html, flags=re.MULTILINE)
        
        # 处理链接
        html = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2" target="_blank">\1</a>', html)
        
        # 处理换行符
        html = html.replace('\n\n', '</p><p>').replace('\n', '<br>')
        
        # 添加段落标签
        html = f'<p>{html}</p>'
        
        # 清理多余的标签
        html = html.replace('</p><p></p>', '</p>')
        html = html.replace('<p></p>', '')
        
        return html
    
    def update_original_report(self, summary_file, ai_report_name):
        """更新原始报告，添加AI分析链接"""
        try:
            # 读取原始报告内容
            with open(summary_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检查是否包含AI分析部分
            import re
            
            # 定义原始AI分析部分的模式
            original_ai_pattern = r'<div\s+class="stat-card"\s+style="background-color:\s*#fff3cd;">\s*<div\s+class="stat-value"\s+style="color:\s*#666;">\s*AI分析\s*</div>\s*<div\s+style="font-size:\s*12px;\s*color:\s*#dc3545;\s*margin-top:\s*5px;">\s*无\s*</div>\s*</div>'
            
            # 定义更新后AI分析部分的模式
            updated_ai_pattern = r'<div\s+class="stat-card"\s+style="background-color:\s*#fff3cd;">\s*<div\s+class="stat-value"\s+style="color:\s*#666;">\s*<a\s+href=".*?"\s+style="color:\s*#28a745;\s*text-decoration:\s*none;"\s+target="_blank">AI分析</a>\s*</div>\s*<div\s+style="font-size:\s*12px;\s*color:\s*#666;\s*margin-top:\s*5px;">\s*点击查看\s*</div>\s*</div>'
            
            # 检查是否是原始AI分析部分（需要更新）
            if re.search(original_ai_pattern, content, flags=re.DOTALL):
                print("找到原始AI分析部分，需要更新")
                
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
                new_content = re.sub(original_ai_pattern, new_ai_section, content, flags=re.DOTALL)
            # 检查是否已经是更新后的AI分析部分
            elif re.search(updated_ai_pattern, content, flags=re.DOTALL):
                print("AI分析部分已经更新过")
                new_content = content
            else:
                print("未找到AI分析部分")
                new_content = content
            
            # 写入更新后的内容
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
        except Exception as e:
            print(f"更新原始报告失败: {e}")


def main():
    """主函数"""
    import argparse
    import os
    
    parser = argparse.ArgumentParser(description='简单的JMeter报告AI分析脚本')
    parser.add_argument('--summary', type=str, required=True, help='指定要分析的summary报告文件')
    parser.add_argument('--config', type=str, help='指定配置文件路径')
    
    args = parser.parse_args()
    
    # 设置默认配置文件路径
    if not args.config:
        # 尝试从默认位置加载配置文件
        default_config = os.path.join(os.path.dirname(__file__), '..', 'config', 'ai_config.json')
        if os.path.exists(default_config):
            args.config = default_config
            print(f"使用默认配置文件: {default_config}")
        else:
            print("未找到默认配置文件，使用空配置")
    
    analyzer = SimpleAIAnalyzer(args.config)
    analyzer.analyze_summary_report(args.summary)


if __name__ == "__main__":
    main()
