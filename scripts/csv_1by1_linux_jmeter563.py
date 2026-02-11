#!/usr/bin/env python3
"""
JMeter 5.6.3 HTML报告生成脚本 - 使用JMeter内置报告功能
"""

import os
import sys
import subprocess
import time
import datetime
import json
import shutil
from pathlib import Path
import re

# 配置文件路径
CONFIG_FILE = Path("/app/config/jmeter_config.json")
JMETER_PROPERTIES_FILE = Path("/app/config/jmeter2.properties")

def load_config():
    """加载配置文件"""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 设置基础目录
        BASE_DIR = Path("/app")
        TEST_PLAN_DIR = BASE_DIR / "test_plan"
        RESULTS_DIR = BASE_DIR / "results"
        REPORTS_BASE_DIR = BASE_DIR / "reports"
        
        # 返回配置字典 - 使用配置文件中的值
        return {
            'jmeter_path': config.get('jmeter_path', '/opt/apache-jmeter-5.6.3/bin/jmeter'),
            'base_url': config.get('base_url', '192.168.0.158'),
            'port': config.get('port', '5046'),
            'threads': config.get('threads', 50),
            'rampup': config.get('rampup', 10),
            'duration': config.get('duration', 30),
            'interval_between_tests': config.get('interval_between_tests', 10),
            'base_dir': BASE_DIR,
            'test_plan_dir': TEST_PLAN_DIR,
            'results_dir': RESULTS_DIR,
            'reports_base_dir': REPORTS_BASE_DIR,
            'jmeter_properties_file': JMETER_PROPERTIES_FILE
        }
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        # 返回默认配置
        BASE_DIR = Path("/app")
        return {
            'jmeter_path': '/opt/apache-jmeter-5.6.3/bin/jmeter',
            'base_url': '192.168.0.158',
            'port': '5046',
            'threads': 50,
            'rampup': 10,
            'duration': 30,
            'interval_between_tests': 10,
            'base_dir': BASE_DIR,
            'test_plan_dir': BASE_DIR / "test_plan",
            'results_dir': BASE_DIR / "results",
            'reports_base_dir': BASE_DIR / "reports",
            'jmeter_properties_file': JMETER_PROPERTIES_FILE
        }

def setup_logging():
    """简化日志设置"""
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    return logging.getLogger()

def get_jmx_files_sorted(test_plan_dir):
    """获取并排序jmx文件"""
    jmx_files = []
    for file_path in test_plan_dir.glob('*.jmx'):
        match = re.search(r'^(\d+)_', file_path.name)
        if match:
            number = int(match.group(1))
            jmx_files.append((number, file_path))
    
    jmx_files.sort(key=lambda x: x[0])
    return [file_path for _, file_path in jmx_files]

def run_single_test(jmx_file, timestamp, config):
    """执行单个JMeter测试"""
    logger = setup_logging()
    test_name = jmx_file.stem
    
    # 从配置获取参数
    jmeter_path = config['jmeter_path']
    threads = config['threads']
    rampup = config['rampup']
    duration = config['duration']
    base_url = config['base_url']
    port = config['port']
    results_dir = config['results_dir']
    reports_base_dir = config['reports_base_dir']
    jmeter_properties_file = config.get('jmeter_properties_file')
    
    # 检查JMeter路径
    if not os.path.exists(jmeter_path):
        logger.error(f"JMeter路径不存在: {jmeter_path}")
        return False
    
    # 检查jmeter.properties文件
    if not jmeter_properties_file.exists():
        logger.error(f"jmeter.properties配置文件不存在: {jmeter_properties_file}")
        logger.error("请确保配置文件已正确创建")
        return False
    
    # 创建结果和报告目录
    results_dir.mkdir(parents=True, exist_ok=True)
    report_dir = reports_base_dir / f"{test_name}_{timestamp}"
    report_dir.mkdir(parents=True, exist_ok=True)
    
    result_file = results_dir / f"{test_name}_{timestamp}.jtl"
    
    # 构建JMeter命令 - 使用配置文件
    jmeter_args = [
        jmeter_path,
        '-n',  # 非GUI模式
        '-t', str(jmx_file),
        '-l', str(result_file),
        '-e',  # 测试结束后生成报告
        '-o', str(report_dir),
        '-p', str(jmeter_properties_file),  # 加载properties配置文件
        f'-Jthreads={threads}',
        f'-Jrampup={rampup}',
        f'-Jduration={duration}',
        f'-Jbase_url={base_url}',
        f'-Jport={port}',
        # 性能优化参数
        '-Dlog4j2.formatMsgNoLookups=true',
        '-Jjava.awt.headless=true',
        '-Djava.awt.headless=true'
    ]
    
    # 设置JMeter环境变量
    env = os.environ.copy()
    env['JVM_ARGS'] = '-Djava.awt.headless=true -Xmx4096m -Xms1024m -XX:MaxMetaspaceSize=512m'
    
    logger.info(f"开始执行测试: {test_name}")
    logger.info(f"线程数: {threads}, 启动时间: {rampup}秒, 持续时间: {duration}秒")
    logger.info(f"目标URL: {base_url}:{port}")
    logger.info(f"JMeter内存配置: 最大4GB, 初始1GB")
    logger.info(f"使用配置文件: {jmeter_properties_file}")
    logger.info(f"输出格式: CSV (JMeter内置报告生成器需要)")
    
    try:
        # 执行JMeter测试
        process = subprocess.Popen(jmeter_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                  text=True, shell=False, env=env)
        
        # 计算超时时间
        total_timeout = duration + rampup + 600
        
        stdout, stderr = process.communicate(timeout=total_timeout)
        
        # 记录输出
        if stdout:
            for line in stdout.split('\n'):
                if line.strip():
                    logger.info(f"JMeter: {line}")
        if stderr:
            for line in stderr.split('\n'):
                if line.strip() and 'Nashorn' not in line:
                    logger.warning(f"JMeter: {line}")
        
        if process.returncode == 0:
            logger.info(f"测试 {test_name} 执行完成")
            
            # 检查结果文件
            if result_file.exists():
                jtl_size = result_file.stat().st_size
                logger.info(f"JTL文件大小: {jtl_size} 字节")
                
                # 检查报告是否生成
                index_html = report_dir / "index.html"
                if index_html.exists():
                    logger.info(f"HTML报告已生成: {index_html}")
                    
                    # 不移动报告文件，保留在原始目录
                    report_files = list(report_dir.iterdir())
                    logger.info(f"报告目录包含 {len(report_files)} 个文件，保留在原始位置: {report_dir}")
                    
                    return True
                else:
                    logger.warning(f"HTML报告未生成，尝试重新生成")
                    # 使用JMeter重新生成HTML报告
                    return generate_jmeter_html_report(config, result_file, report_dir, test_name, logger)
            else:
                logger.error(f"JTL结果文件未生成: {result_file}")
                return False
        else:
            logger.error(f"测试 {test_name} 执行失败，退出码: {process.returncode}")
            # 记录详细的错误信息
            if stderr:
                error_lines = [line for line in stderr.split('\n') if line.strip()]
                for i, line in enumerate(error_lines[:10]):
                    logger.error(f"错误详情 {i+1}: {line}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"测试 {test_name} 执行超时")
        if process:
            process.terminate()
        return False
    except Exception as e:
        logger.error(f"执行过程中发生错误: {e}")
        return False

def generate_jmeter_html_report(config, jtl_file, report_dir, test_name, logger):
    """使用JMeter内置功能生成HTML报告"""
    try:
        logger.info(f"使用JMeter内置功能生成HTML报告: {test_name}")
        
        jmeter_path = config['jmeter_path']
        jtl_size = jtl_file.stat().st_size
        jtl_size_mb = jtl_size / (1024 * 1024)
        
        logger.info(f"JTL文件大小: {jtl_size_mb:.2f} MB")
        
        # 根据JTL文件大小动态设置超时时间
        if jtl_size_mb <= 5:
            report_timeout = 180  # 3分钟
        elif jtl_size_mb <= 15:
            report_timeout = 300  # 5分钟
        elif jtl_size_mb <= 50:
            report_timeout = 480  # 8分钟
        else:
            report_timeout = 600  # 10分钟
        
        # JMeter内置报告生成参数 - 修复版本
        report_args = [
            jmeter_path,
            '-g', str(jtl_file),  # 生成报告
            '-o', str(report_dir),
            '-n',  # 非GUI模式
            '-Jjava.awt.headless=true',
            '-Djava.awt.headless=true',
            
            # 简化报告参数，避免复杂配置导致失败
            '-Jjmeter.reportgenerator.overall_granularity=60000',  # 聚合粒度60秒
            '-Jjmeter.reportgenerator.report_title=' + test_name,
            '-Jjmeter.reportgenerator.exclude_controllers=false',
            '-Jjmeter.reportgenerator.generate_report_ui.generation_timeout=' + str(report_timeout),
            
            # 内存优化
            '-Jjmeter.save.saveservice.autoflush=true',
            '-Jjmeter.save.saveservice.thread_counts=true',
            '-Jjmeter.save.saveservice.latency=true',
            '-Jjmeter.save.saveservice.connect_time=true',
            '-Jjmeter.save.saveservice.idle_time=true',
            '-Jjmeter.save.saveservice.timestamp_format=yyyy/MM/dd HH:mm:ss',
            '-Jjmeter.save.saveservice.default_delimiter=,',
            '-Jjmeter.save.saveservice.print_field_names=true'
        ]
        
        # 环境变量设置 - 优化内存配置
        env = os.environ.copy()
        env['JVM_ARGS'] = '-Djava.awt.headless=true -Xms512m -Xmx2048m -XX:MaxMetaspaceSize=512m'
        
        logger.info(f"报告生成超时时间: {report_timeout} 秒")
        logger.info(f"使用JMeter内置报告生成功能")
        logger.info(f"JMeter报告生成内存配置: 最大2GB")
        
        try:
            report_process = subprocess.Popen(
                report_args, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True, 
                shell=False, 
                env=env
            )
            
            report_stdout, report_stderr = report_process.communicate(timeout=report_timeout)
            
            # 记录详细的输出信息
            if report_stdout:
                for line in report_stdout.split('\n'):
                    if line.strip():
                        logger.info(f"JMeter报告生成: {line}")
            if report_stderr:
                for line in report_stderr.split('\n'):
                    if line.strip():
                        logger.warning(f"JMeter报告生成警告: {line}")
            
            if report_process.returncode == 0:
                index_html = report_dir / "index.html"
                if index_html.exists():
                    logger.info(f"HTML报告生成成功: {report_dir}")
                    
                    # 检查报告目录内容
                    report_files = list(report_dir.iterdir())
                    logger.info(f"报告目录包含 {len(report_files)} 个文件")
                    
                    # 不移动报告文件，保留在原始目录
                    logger.info(f"报告文件保留在原始目录: {report_dir}")
                    
                    return True
                else:
                    logger.warning(f"HTML报告生成完成但index.html不存在，检查目录内容")
                    report_files = list(report_dir.iterdir())
                    logger.info(f"报告目录包含的文件: {[f.name for f in report_files]}")
                    return generate_simple_html_report(jtl_file, report_dir, test_name, logger)
            else:
                logger.warning(f"HTML报告生成失败，退出码: {report_process.returncode}")
                # 记录详细的错误信息
                if report_stderr:
                    error_lines = [line for line in report_stderr.split('\n') if line.strip()]
                    for i, line in enumerate(error_lines[:10]):  # 只显示前10行错误
                        logger.error(f"错误详情 {i+1}: {line}")
                return generate_simple_html_report(jtl_file, report_dir, test_name, logger)
                
        except subprocess.TimeoutExpired:
            logger.warning(f"HTML报告生成超时({report_timeout}秒)，生成简单报告")
            return generate_simple_html_report(jtl_file, report_dir, test_name, logger)
        except Exception as e:
            logger.warning(f"HTML报告生成异常: {e}")
            return generate_simple_html_report(jtl_file, report_dir, test_name, logger)
            
    except Exception as e:
        logger.error(f"生成HTML报告时发生错误: {e}")
        return False

def generate_simple_html_report(jtl_file, report_dir, test_name, logger):
    """生成简单HTML报告（备用方案）"""
    logger.info(f"为 {test_name} 生成简单HTML报告")
    
    try:
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
        
        report_dir.mkdir(parents=True, exist_ok=True)
        index_file = report_dir / "index.html"
        with open(index_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"简单HTML报告已生成: {index_file}")
        logger.info(f"报告文件保留在原始目录: {report_dir}")
        return True
        
    except Exception as e:
        logger.error(f"生成简单HTML报告时出错: {e}")
        return False

def move_reports_to_base_dir(report_dir, reports_base_dir, test_name, logger):
    """移动JMeter自动生成的报告文件到reports目录，并按JMX文件名重命名"""
    try:
        logger.info(f"开始移动报告文件从 {report_dir} 到 {reports_base_dir}")
        
        # 检查源目录是否存在
        if not report_dir.exists():
            logger.warning(f"报告目录不存在: {report_dir}")
            return False
        
        # 获取报告目录中的所有文件
        files_to_move = []
        for file_path in report_dir.iterdir():
            if file_path.is_file():
                files_to_move.append(file_path)
        
        if not files_to_move:
            logger.warning(f"在 {report_dir} 中未找到报告文件")
            return False
        
        logger.info(f"找到 {len(files_to_move)} 个报告文件需要移动")
        
        moved_count = 0
        for source_file in files_to_move:
            # 根据文件名决定目标文件名
            if source_file.name.lower() == 'index.html':
                target_name = f"{test_name}_index.html"
            else:
                # 其他文件，保留原文件名但添加前缀
                target_name = f"{test_name}_{source_file.name}"
            
            target_file = reports_base_dir / target_name
            
            try:
                # 移动文件
                shutil.move(str(source_file), str(target_file))
                logger.info(f"已移动文件: {source_file.name} -> {target_name}")
                moved_count += 1
            except Exception as e:
                logger.error(f"移动文件 {source_file.name} 时出错: {e}")
        
        # 检查是否所有文件都移动成功
        if moved_count == len(files_to_move):
            logger.info(f"所有 {moved_count} 个报告文件已成功移动到reports目录")
            
            # 尝试删除空目录
            try:
                if report_dir.exists():
                    # 检查目录是否为空
                    remaining_files = list(report_dir.iterdir())
                    if len(remaining_files) == 0:
                        report_dir.rmdir()
                        logger.info(f"已删除空报告目录: {report_dir}")
                    else:
                        logger.info(f"报告目录非空，保留目录: {report_dir}")
            except Exception as e:
                logger.warning(f"删除报告目录时出错: {e}")
            
            return True
        else:
            logger.warning(f"部分文件移动失败: {moved_count}/{len(files_to_move)} 个文件移动成功")
            return False
            
    except Exception as e:
        logger.error(f"移动报告文件时发生错误: {e}")
        return False

def main():
    """主函数"""
    logger = setup_logging()
    logger.info("JMeter 5.6.3 HTML报告生成脚本启动")
    
    # 加载配置
    config = load_config()
    logger.info("配置加载完成")
    
    # 获取测试计划文件
    test_plan_dir = config['test_plan_dir']
    jmx_files = get_jmx_files_sorted(test_plan_dir)
    
    if not jmx_files:
        logger.error(f"在 {test_plan_dir} 中未找到任何jmx文件")
        return
    
    logger.info(f"找到 {len(jmx_files)} 个测试计划文件")
    
    # 生成时间戳
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 执行所有测试
    for jmx_file in jmx_files:
        logger.info(f"开始处理测试计划: {jmx_file.name}")
        
        success = run_single_test(jmx_file, timestamp, config)
        
        if success:
            logger.info(f"测试 {jmx_file.name} 完成")
        else:
            logger.error(f"测试 {jmx_file.name} 失败")
        
        # 测试间隔
        interval = config.get('interval_between_tests', 10)
        if jmx_file != jmx_files[-1]:  # 不是最后一个测试
            logger.info(f"等待 {interval} 秒后执行下一个测试...")
            time.sleep(interval)
    
    logger.info("所有测试执行完成")
    logger.info("所有报告文件保留在各自的时间戳目录中，如: 1_login_20260114_165949")

if __name__ == "__main__":
    main()