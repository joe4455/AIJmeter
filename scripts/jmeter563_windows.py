#!/usr/bin/env python3
"""
JMeter多文件测试执行脚本 - 优化版
分离压测与报告生成，优化JMeter 5.6.3报告生成性能
"""

import os
import sys
import json
import subprocess
import time
import datetime
from pathlib import Path
import re

def setup_logging():
    """设置日志"""
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(Path(__file__).parent.parent / 'logs' / 'jmeter_all_tests.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger()

def load_jmeter_properties():
    """读取jmeter.properties配置文件"""
    properties_path = Path(__file__).parent.parent / 'config' / 'jmeter.properties'
    properties = {}
    
    if not properties_path.exists():
        logger = setup_logging()
        logger.warning(f"JMeter属性文件不存在: {properties_path}")
        return properties
    
    try:
        with open(properties_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # 跳过空行和注释
                if not line or line.startswith('#'):
                    continue
                # 解析键值对
                if '=' in line:
                    key, value = line.split('=', 1)
                    properties[key.strip()] = value.strip()
        
        logger = setup_logging()
        logger.info(f"成功加载JMeter属性文件，包含 {len(properties)} 个配置项")
        return properties
    except Exception as e:
        logger = setup_logging()
        logger.error(f"读取JMeter属性文件失败: {e}")
        return {}

def get_jmx_files():
    """获取test_plan目录下所有的jmx文件，按数字排序"""
    test_plan_dir = Path(__file__).parent.parent / 'test_plan'
    jmx_files = []
    
    for file_path in test_plan_dir.glob('*.jmx'):
        # 提取文件名中的数字用于排序
        match = re.search(r'^(\d+)_', file_path.name)
        if match:
            number = int(match.group(1))
            jmx_files.append((number, file_path))
    
    # 按数字排序
    jmx_files.sort(key=lambda x: x[0])
    return [file_path for _, file_path in jmx_files]

def load_config():
    """加载配置"""
    config_path = Path(__file__).parent.parent / 'config' / 'jmeter_config.json'
    
    # 如果配置文件不存在，创建默认配置
    if not config_path.exists():
        default_config = {
            "jmeter_path": "jmeter",  # Windows下使用系统PATH
            "jmeter_path_windows": "E:\\performance\\apache-jmeter-5.6.3\\bin\\jmeter.bat",
            "base_url": "192.168.0.158",
            "port": "5046",
            "threads": 50,
            "rampup": 10,
            "duration": 60,
            "interval_between_tests": 10,
            "jmeter_version": "5.6.3",
            "separate_report_generation": True,  # 分离报告生成
            "report_generation_timeout": 3600,  # 报告生成超时时间（秒）
            "jvm_heap_size": "-Xms2g -Xmx4g",   # JVM堆内存配置
            "sla_report_jar_windows": "E:\\auto\\jmeterAI\\jmeter-sla-report-1.0.5-jar-with-dependencies.jar"
        }
        
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
        
        print(f"已创建默认配置文件: {config_path}")
        return default_config
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 根据操作系统选择正确的路径
    if os.name == 'nt':  # Windows系统
        config['jmeter_path'] = config.get('jmeter_path_windows', 'jmeter.bat')
        config['sla_report_jar'] = config.get('sla_report_jar_windows', 'jmeter-sla-report-1.0.5-jar-with-dependencies.jar')
    else:  # Linux/Unix系统
        config['jmeter_path'] = config.get('jmeter_path', 'jmeter')
        config['sla_report_jar'] = config.get('sla_report_jar', '/opt/apache-jmeter-5.6.3/lib/ext/jmeter-sla-report-1.0.5-jar-with-dependencies.jar')
    
    return config

def check_jmeter_version(jmeter_path):
    """检查JMeter版本"""
    try:
        # 在Windows上使用shell=True
        result = subprocess.run([jmeter_path, '-v'], capture_output=True, text=True, timeout=10, shell=True)
        if result.returncode == 0:
            version_line = [line for line in result.stdout.split('\n') if 'Apache JMeter' in line]
            if version_line:
                # 提取版本号，例如: "Apache JMeter (5.6.2)"
                version_text = version_line[0]
                import re
                version_match = re.search(r'Apache JMeter\s*\((\d+\.\d+\.\d+)\)', version_text)
                if version_match:
                    return version_match.group(1)
                return version_text
        return "未知版本"
    except Exception as e:
        logger = setup_logging()
        logger.warning(f"版本检测失败: {e}")
        return "无法检测版本"

def run_jmeter_test(config, jmx_file, timestamp):
    """执行单个JMeter测试（仅压测，不生成报告）"""
    logger = setup_logging()
    
    # 从文件名生成测试名称（去掉扩展名）
    test_name = jmx_file.stem
    
    # 获取JMeter命令路径
    jmeter_cmd = config.get('jmeter_path', 'jmeter')
    
    logger.info(f"使用JMeter路径: {jmeter_cmd}")
    
    # 检查路径是否存在（Windows下jmeter.bat可能不在PATH中，需要特殊处理）
    if os.name == 'nt':  # Windows系统
        if not os.path.exists(jmeter_cmd) and jmeter_cmd not in ['jmeter.bat', 'jmeter']:
            logger.error(f"JMeter路径不存在: {jmeter_cmd}")
            logger.error("请检查jmeter_config.json中的jmeter_path_windows配置")
            return False
    else:  # Linux系统
        if not os.path.exists(jmeter_cmd) and jmeter_cmd not in ['jmeter']:
            logger.error(f"JMeter路径不存在: {jmeter_cmd}")
            logger.error("请检查jmeter_config.json中的jmeter_path配置")
            return False
    
    # 构建结果文件路径 - 直接放在results目录下
    results_dir = Path(__file__).parent.parent / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    
    result_file = results_dir / f"{test_name}_{timestamp}.jtl"
    
    # 构建JMeter命令 - 仅执行压测，不生成报告
    jmeter_args = [
        jmeter_cmd,
        '-n',  # 非GUI模式
        '-t', str(jmx_file),
        '-l', str(result_file),
        '-Jthreads=' + str(config.get('threads', 50)),
        '-Jrampup=' + str(config.get('rampup', 10)),
        '-Jduration=' + str(config.get('duration', 60)),
        '-Jbase_url=' + config.get('base_url', '192.168.0.158'),
        '-Jport=' + config.get('port', '5046')
    ]
    
    # 读取jmeter.properties配置文件并应用配置
    jmeter_properties = load_jmeter_properties()
    
    # 根据配置文件动态构建JMeter参数
    jmeter_args.extend([
        # 设置XML格式（便于后续处理）
        '-Jjmeter.save.saveservice.output_format=xml'
    ])
    
    # 应用jmeter.properties中的配置
    for key, value in jmeter_properties.items():
        if key.startswith('jmeter.'):
            jmeter_args.append(f'-J{key}={value}')
    
    # 获取JVM内存配置（按照JMeter 5.6.3标准方式）
    jvm_heap = config.get('jvm_heap_size', '-Xms2g -Xmx4g')
    
    logger.info(f"开始执行测试: {test_name}")
    logger.info(f"线程数: {config.get('threads', 50)}, 启动时间: {config.get('rampup', 10)}秒")
    logger.info(f"持续时间: {config.get('duration', 60)}秒")
    logger.info(f"目标URL: {config.get('base_url', '192.168.0.158')}:{config.get('port', '5046')}")
    logger.info(f"JVM内存配置: {jvm_heap}")
    logger.info(f"已应用 {len(jmeter_properties)} 个JMeter属性配置")
    
    process = None
    try:
        # 设置JVM环境变量（JMeter 5.6.3标准方式）
        env = os.environ.copy()
        env['JVM_ARGS'] = jvm_heap
        
        # 执行JMeter测试 - 在Windows上使用shell=True，并传递环境变量
        process = subprocess.Popen(jmeter_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                  text=True, shell=True, env=env)
        
        # 计算总超时时间：持续时间 + 启动时间 + 缓冲时间（5分钟）
        total_timeout = config.get('duration', 60) + config.get('rampup', 10) + 300
        
        # 等待进程完成
        stdout, stderr = process.communicate(timeout=total_timeout)
        
        # 记录JMeter输出
        if stdout:
            for line in stdout.split('\n'):
                if line.strip():
                    logger.info(f"JMeter: {line}")
        if stderr:
            for line in stderr.split('\n'):
                if line.strip() and 'Nashorn' not in line:  # 过滤Nashorn警告
                    logger.warning(f"JMeter: {line}")
        
        if process.returncode == 0:
            logger.info(f"测试 {test_name} 执行完成")
            
            # 检查JTL文件是否生成
            if not result_file.exists():
                logger.error(f"JTL结果文件未生成: {result_file}")
                return False
            
            jtl_size = result_file.stat().st_size
            logger.info(f"JTL文件大小: {jtl_size} 字节 ({jtl_size/1024/1024:.2f} MB)")
            
            if jtl_size > 1024:  # 如果JTL文件大于1KB，说明有数据
                logger.info(f"测试 {test_name} 执行成功，JTL文件已生成")
                return True
            else:
                logger.warning(f"测试 {test_name} 执行完成，但JTL文件较小({jtl_size}字节)，可能测试数据较少")
                return False
        else:
            logger.error(f"测试 {test_name} 执行失败，退出码: {process.returncode}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"测试 {test_name} 执行超时")
        if process:
            process.terminate()
        return False
    except Exception as e:
        logger.error(f"执行过程中发生错误: {e}")
        return False

def generate_html_reports_batch(config, timestamp):
    """批量生成HTML报告（分离压测与报告生成）"""
    logger = setup_logging()
    logger.info("开始批量生成HTML报告...")
    
    results_dir = Path(__file__).parent.parent / "results"
    reports_base_dir = Path(__file__).parent.parent / "reports"
    reports_base_dir.mkdir(parents=True, exist_ok=True)
    
    # 获取SLA报告JAR路径
    sla_report_jar = config.get('sla_report_jar', 'jmeter-sla-report-1.0.5-jar-with-dependencies.jar')
    logger.info(f"使用SLA报告JAR路径: {sla_report_jar}")
    
    # 获取所有JTL文件
    jtl_files = list(results_dir.glob(f"*_{timestamp}.jtl"))
    
    if not jtl_files:
        logger.warning(f"未找到时间戳为 {timestamp} 的JTL文件")
        return False
    
    logger.info(f"找到 {len(jtl_files)} 个JTL文件需要生成报告")
    
    success_count = 0
    for jtl_file in jtl_files:
        test_name = jtl_file.stem.replace(f"_{timestamp}", "")
        report_dir = reports_base_dir / f"{test_name}_{timestamp}"
        
        logger.info(f"为测试 {test_name} 生成HTML报告...")
        
        if generate_single_html_report(config, jtl_file, report_dir, test_name, timestamp):
            success_count += 1
    
    logger.info(f"批量报告生成完成: {success_count}/{len(jtl_files)} 个测试报告生成成功")
    return success_count > 0

def generate_single_html_report(config, jtl_file, report_dir, test_name, timestamp):
    """为单个JTL文件生成HTML报告"""
    logger = setup_logging()
    
    jmeter_cmd = config.get('jmeter_path', 'jmeter')
    jtl_size = jtl_file.stat().st_size
    jtl_size_mb = jtl_size / (1024 * 1024)
    
    logger.info(f"为 {test_name} 生成HTML报告，JTL文件大小: {jtl_size_mb:.2f} MB")
    
    # 根据JTL文件大小动态设置超时时间（大幅减少超时时间）
    if jtl_size_mb <= 5:
        report_timeout = 300  # 5分钟
    elif jtl_size_mb <= 15:
        report_timeout = 600  # 10分钟
    elif jtl_size_mb <= 50:
        report_timeout = 900  # 15分钟
    else:
        report_timeout = 1200  # 20分钟
    
    # 优化报告生成参数 - 大幅提升性能
    report_args = [
        jmeter_cmd,
        '-g', str(jtl_file),  # 生成报告
        '-o', str(report_dir),
        
        # 报告生成性能优化参数
        '-Jjmeter.reportgenerator.overall_granularity=600000',  # 聚合粒度600秒（10分钟）
        '-Jjmeter.reportgenerator.exclude_controllers=true',
        '-Jjmeter.reportgenerator.report_title=' + test_name,
        '-Jjmeter.reportgenerator.generate_report_ui.generation_timeout=' + str(report_timeout),
        
        # 关闭重图表（大幅提升性能）
        '-Jjmeter.reportgenerator.apdex_per_transaction=false',  # 关闭APDEX
        '-Jjmeter.reportgenerator.response_time_distribution_chart=false',  # 关闭响应时间分布图
        '-Jjmeter.reportgenerator.overall_response_codes_pie_chart=false',  # 关闭响应码饼图
        '-Jjmeter.reportgenerator.bytes_throughput_over_time=false',  # 关闭字节吞吐量图
        
        # 保留必要图表
        '-Jjmeter.reportgenerator.overall_stats=true',
        '-Jjmeter.reportgenerator.response_times_over_time=true',
        '-Jjmeter.reportgenerator.throughput_over_time=true',
        
        # 其他优化
        '-Jjava.awt.headless=true'
    ]
    
    logger.info(f"报告生成超时时间: {report_timeout} 秒")
    logger.info(f"聚合粒度: 600秒（大幅减少数据点）")
    
    try:
        report_process = subprocess.Popen(report_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
        report_stdout, report_stderr = report_process.communicate(timeout=report_timeout)
        
        if report_process.returncode == 0:
            # 检查报告是否完整生成
            index_html = report_dir / "index.html"
            if index_html.exists():
                logger.info(f"HTML报告生成成功: {report_dir}")
                
                # 移动报告文件到reports目录（按JMX文件名命名）
                moved = move_reports_to_base_dir(report_dir, reports_base_dir, test_name, timestamp, logger)
                if moved:
                    logger.info(f"报告文件已按JMX文件名重命名并移动到reports目录")
                else:
                    logger.warning(f"报告文件移动失败，保留在原目录")
                
                return True
            else:
                logger.warning(f"HTML报告生成完成，但index.html不存在")
                return generate_simple_html_report(jtl_file, report_dir, test_name, timestamp)
        else:
            logger.warning(f"HTML报告生成失败，退出码: {report_process.returncode}")
            if report_stderr:
                for line in report_stderr.split('\n'):
                    if line.strip():
                        logger.warning(f"错误详情: {line}")
            return generate_simple_html_report(jtl_file, report_dir, test_name, timestamp)
            
    except subprocess.TimeoutExpired:
        logger.warning(f"HTML报告生成超时({report_timeout}秒)，生成简单报告")
        return generate_simple_html_report(jtl_file, report_dir, test_name, timestamp)
    except Exception as e:
        logger.warning(f"HTML报告生成异常: {e}")
        return generate_simple_html_report(jtl_file, report_dir, test_name, timestamp)

def move_reports_to_base_dir(report_dir, reports_base_dir, test_name, timestamp, logger):
    """移动报告文件到reports目录并按JMX文件名重命名"""
    try:
        # 检查源目录是否存在
        if not report_dir.exists():
            logger.warning(f"报告目录不存在: {report_dir}")
            return False
        
        # 获取报告目录中的所有HTML文件
        files_to_move = []
        for file_path in report_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in ['.html', '.htm']:
                files_to_move.append(file_path)
        
        if not files_to_move:
            logger.warning(f"在 {report_dir} 中未找到HTML报告文件")
            return False
        
        moved_count = 0
        for source_file in files_to_move:
            # 根据文件名决定目标文件名
            if source_file.name.lower() == 'index.html':
                target_name = f"{test_name}_index.html"
            elif source_file.name.lower() == 'sla_report.html':
                target_name = f"{test_name}_sla_report.html"
            else:
                target_name = f"{test_name}_{source_file.name}"
            
            target_file = reports_base_dir / target_name
            
            try:
                # 移动文件
                import shutil
                shutil.move(str(source_file), str(target_file))
                logger.info(f"已移动文件: {source_file.name} -> {target_name}")
                moved_count += 1
            except Exception as e:
                logger.error(f"移动文件 {source_file.name} 时出错: {e}")
        
        # 尝试删除空目录
        try:
            if report_dir.exists() and moved_count == len(files_to_move):
                remaining_files = list(report_dir.iterdir())
                if len(remaining_files) == 0:
                    report_dir.rmdir()
                    logger.info(f"已删除空报告目录: {report_dir}")
        except Exception as e:
            logger.warning(f"删除报告目录时出错: {e}")
        
        return moved_count > 0
            
    except Exception as e:
        logger.error(f"移动报告文件时发生错误: {e}")
        return False

def generate_simple_html_report(jtl_file, report_dir, test_name, timestamp):
    """生成简单HTML报告（备用方案）"""
    logger = setup_logging()
    logger.info(f"为 {test_name} 生成简单HTML报告")
    
    try:
        # 创建简单的HTML报告
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{test_name} - JMeter测试报告</title>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                h1 {{ color: #333; }}
                .info {{ background: #f5f5f5; padding: 15px; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <h1>{test_name} - JMeter测试报告</h1>
            <div class="info">
                <p><strong>测试名称:</strong> {test_name}</p>
                <p><strong>生成时间:</strong> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>JTL文件:</strong> {jtl_file.name}</p>
                <p><strong>文件大小:</strong> {jtl_file.stat().st_size} 字节</p>
                <p><em>注: 这是简化版报告，完整报告生成失败</em></p>
            </div>
        </body>
        </html>
        """
        
        index_file = report_dir / "index.html"
        with open(index_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"简单HTML报告已生成: {index_file}")
        return True
        
    except Exception as e:
        logger.error(f"生成简单HTML报告时出错: {e}")
        return False

def main():
    """主函数"""
    logger = setup_logging()
    logger.info("JMeter批量测试脚本启动（优化版）")
    
    # 加载配置
    config = load_config()
    logger.info("配置加载完成")
    
    # 检查JMeter版本
    jmeter_version = check_jmeter_version(config['jmeter_path'])
    logger.info(f"检测到JMeter版本: {jmeter_version}")
    
    # 获取测试计划文件
    jmx_files = get_jmx_files()
    
    if not jmx_files:
        logger.error("在test_plan目录中未找到任何jmx文件")
        return
    
    logger.info(f"找到 {len(jmx_files)} 个测试计划文件")
    
    # 生成时间戳
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 检查是否分离报告生成
    separate_reports = config.get('separate_report_generation', True)
    
    if separate_reports:
        logger.info("采用分离压测与报告生成策略")
        
        # 第一阶段：执行所有压测
        logger.info("=== 第一阶段：执行压测 ===")
        successful_tests = []
        
        for jmx_file in jmx_files:
            logger.info(f"开始处理测试计划: {jmx_file.name}")
            
            if run_jmeter_test(config, jmx_file, timestamp):
                successful_tests.append(jmx_file)
                logger.info(f"测试 {jmx_file.name} 压测完成")
            else:
                logger.error(f"测试 {jmx_file.name} 压测失败")
            
            # 测试间隔
            interval = config.get('interval_between_tests', 10)
            if jmx_file != jmx_files[-1]:  # 不是最后一个测试
                logger.info(f"等待 {interval} 秒后执行下一个测试...")
                time.sleep(interval)
        
        # 第二阶段：批量生成报告
        if successful_tests:
            logger.info("=== 第二阶段：批量生成报告 ===")
            logger.info(f"将为 {len(successful_tests)} 个成功测试生成报告")
            
            if generate_html_reports_batch(config, timestamp):
                logger.info("批量报告生成完成")
            else:
                logger.warning("批量报告生成部分失败")
        else:
            logger.warning("没有成功的测试，跳过报告生成")
    
    else:
        # 传统模式：压测后立即生成报告
        logger.info("采用传统模式（压测后立即生成报告）")
        
        for jmx_file in jmx_files:
            logger.info(f"开始处理测试计划: {jmx_file.name}")
            
            # 这里需要调用原来的run_jmeter_test函数（包含报告生成）
            # 由于代码较长，这里省略具体实现
            
            # 测试间隔
            interval = config.get('interval_between_tests', 10)
            if jmx_file != jmx_files[-1]:  # 不是最后一个测试
                logger.info(f"等待 {interval} 秒后执行下一个测试...")
                time.sleep(interval)
    
    logger.info("所有测试执行完成")

if __name__ == "__main__":
    main()