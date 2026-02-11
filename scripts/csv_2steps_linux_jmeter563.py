#!/usr/bin/env python3
"""
JMeter 5.6.3 HTML报告生成脚本 - 优化版
解决大JTL文件生成报告失败的问题
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

# 导入报告汇总模块
# 导入增强版HTML报告模块

# 配置文件路径
CONFIG_FILE = Path("/app/config/jmeter_config.json")
JMETER_PROPERTIES_FILE = Path("/app/config/jmeter2.properties")

# 全局日志实例
_logger = None

def get_logger():
    """获取日志实例（单例模式）"""
    global _logger
    if _logger is None:
        import logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )
        _logger = logging.getLogger()
    return _logger

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
            'project_name': config.get('project_name', 'default'),
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
            'project_name': 'default',
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

def detect_jtl_format(jtl_file):
    """检测JTL文件格式"""
    try:
        with open(jtl_file, 'r', encoding='utf-8') as f:
            content = f.read(1000)
        return {
            'is_csv': ',' in content and 'timeStamp' in content,
            'is_xml': '<?xml' in content or '<testResults' in content
        }
    except Exception:
        return {'is_csv': False, 'is_xml': False}

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

def run_single_test(jmx_file, timestamp, config):
    """执行单个JMeter测试，只生成JTL文件，不生成报告"""
    logger = get_logger()
    test_name = jmx_file.stem
    
    # 从配置获取参数
    jmeter_path = config['jmeter_path']
    project_name = config.get('project_name', 'default')
    threads = config['threads']
    rampup = config['rampup']
    duration = config['duration']
    base_url = config['base_url']
    port = config['port']
    results_dir = config['results_dir']
    
    # 检查JMeter路径
    if not os.path.exists(jmeter_path):
        logger.error(f"JMeter路径不存在: {jmeter_path}")
        return False, None
    
    # 创建结果目录
    results_dir.mkdir(parents=True, exist_ok=True)
    # 使用项目名称作为JTL文件名前缀
    result_file = results_dir / f"{project_name}_{test_name}_{timestamp}.jtl"
    
    # 构建JMeter命令 - 只生成JTL，不生成报告
    jmeter_args = [
        jmeter_path,
        '-n',  # 非GUI模式
        '-t', str(jmx_file),
        '-l', str(result_file),
        '-p', str(config['jmeter_properties_file']),
        f'-Jthreads={threads}',
        f'-Jrampup={rampup}',
        f'-Jduration={duration}',
        f'-Jbase_url={base_url}',
        f'-Jport={port}',
        '-Dlog4j2.formatMsgNoLookups=true',
        '-Jjava.awt.headless=true',
        '-Djava.awt.headless=true'
    ]
    
    # 设置JMeter环境变量
    env = os.environ.copy()
    env['JVM_ARGS'] = '-Djava.awt.headless=true -Xmx4096m -Xms1024m -XX:MaxMetaspaceSize=512m'
    
    logger.info(f"开始执行测试: {test_name}")
    logger.info(f"线程数: {threads}, 启动时间: {rampup}秒, 持续时间: {duration}秒")
    
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
        
        if process.returncode == 0:
            logger.info(f"测试 {test_name} 执行完成")
            
            # 检查结果文件
            if result_file.exists():
                jtl_size = result_file.stat().st_size
                logger.info(f"JTL文件大小: {jtl_size} 字节")
                return True, result_file
            else:
                logger.error(f"JTL结果文件未生成: {result_file}")
                return False, None
        else:
            logger.error(f"测试 {test_name} 执行失败，退出码: {process.returncode}")
            return False, None
            
    except subprocess.TimeoutExpired:
        logger.error(f"测试 {test_name} 执行超时")
        if process:
            process.terminate()
        return False, None
    except Exception as e:
        logger.error(f"执行过程中发生错误: {e}")
        return False, None

def generate_batch_html_reports(config, jtl_files, timestamp, logger):
    """批量生成HTML报告 - 优化版"""
    try:
        # 在函数内部导入模块，避免模块级别的问题
        try:
            from report_summary import generate_report_summary
        except ImportError as e:
            logger.warning(f"无法导入report_summary模块: {e}")
            generate_report_summary = None
        
        try:
            from enhanced_html_report import generate_enhanced_html_report
        except ImportError as e:
            logger.warning(f"无法导入enhanced_html_report模块: {e}")
            generate_enhanced_html_report = None
        
        jmeter_path = config['jmeter_path']
        reports_base_dir = config['reports_base_dir']
        project_name = config.get('project_name', 'default')
        
        # 生成项目名称+日期的目录名
        current_date = datetime.datetime.now().strftime("%Y%m%d")
        project_report_dir = reports_base_dir / f"{project_name}_{current_date}"
        project_report_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"开始批量生成HTML报告，共 {len(jtl_files)} 个JTL文件")
        logger.info(f"报告存储目录: {project_report_dir}")
        
        # 为每个测试创建独立的报告目录
        for jtl_file in jtl_files:
            # 直接使用JTL文件名（去掉扩展名）作为报告目录名
            report_dir_name = jtl_file.stem
            report_dir = project_report_dir / report_dir_name
            report_dir.mkdir(parents=True, exist_ok=True)
            
            # 从JTL文件名提取测试名称（去掉时间戳部分，用于报告标题）
            jtl_stem = jtl_file.stem
            test_name = jtl_stem  # 设置默认值为完整的文件名（不含扩展名）
            if '_' in jtl_stem:
                last_underscore = jtl_stem.rfind('_')
                time_part = jtl_stem[last_underscore+1:]
                if re.match(r'^\d{8}_\d{6}$', time_part):
                    test_name = jtl_stem[:last_underscore]
            
            logger.info(f"为 {test_name} 生成报告到: {report_dir}")
            
            # 检查JTL文件格式
            format_info = detect_jtl_format(jtl_file)
            logger.info(f"JTL文件格式检测: CSV={format_info['is_csv']}, XML={format_info['is_xml']}")
            
            # 根据JTL文件大小设置超时时间和JVM内存
            jtl_size_mb = jtl_file.stat().st_size / (1024 * 1024)
            if jtl_size_mb <= 5:
                report_timeout = 180
                jvm_memory = '-Xms1g -Xmx4g'
            elif jtl_size_mb <= 15:
                report_timeout = 300
                jvm_memory = '-Xms3g -Xmx8g'  # 从2g/6g增加到3g/8g
            elif jtl_size_mb <= 50:
                report_timeout = 600  # 增加超时时间
                jvm_memory = '-Xms3g -Xmx8g'
            else:
                report_timeout = 900  # 大型文件增加超时
                jvm_memory = '-Xms4g -Xmx12g'
            
            # 常规的JMeter报告生成参数 - 适合JMeter 5.6.3
            report_args = [
                jmeter_path,
                '-g', str(jtl_file),
                '-o', str(report_dir),
                '-Jjava.awt.headless=true',
                '-Djava.awt.headless=true',
                # 基本报告配置
                '-Jjmeter.reportgenerator.overall_granularity=60000',  # 数据点粒度(ms)
                '-Jjmeter.reportgenerator.report_title=' + test_name,
                '-Jjmeter.save.saveservice.timestamp_format=yyyy/MM/dd HH:mm:ss',  # 时间戳格式
                
                # 报告内容配置 - 简化配置，避免复杂过滤
                '-Jjmeter.reportgenerator.exporter.html.show_controllers_only=false',  # 显示所有采样器
                '-Jjmeter.reportgenerator.exporter.html.auto_size_images=true',  # 自动调整图片大小
                
                # 数据保存配置
                '-Jjmeter.save.saveservice.output_format=csv',
                '-Jjmeter.save.saveservice.print_field_names=true',
                
                # 图表配置 - 启用常用图表
                '-Jjmeter.reportgenerator.graph.responseTimeOverTime.enabled=true',
                '-Jjmeter.reportgenerator.graph.throughputOverTime.enabled=true',
                '-Jjmeter.reportgenerator.graph.responseCodesOverTime.enabled=true',
                '-Jjmeter.reportgenerator.graph.activeThreadsOverTime.enabled=true',
                '-Jjmeter.reportgenerator.graph.transactionsPerSecond.enabled=true',
                
                # 添加统计信息配置
                '-Jjmeter.reportgenerator.apdex_satisfied_threshold=500',
                '-Jjmeter.reportgenerator.apdex_tolerated_threshold=1500'
            ]
            
            # 环境变量设置 - 增加JVM内存
            env = os.environ.copy()
            env['JVM_ARGS'] = f'-Djava.awt.headless=true {jvm_memory} -XX:MaxMetaspaceSize=1024m'
            
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
                        logger.info(f"✅ {test_name} HTML报告生成成功")
                        report_files = list(report_dir.iterdir())
                        logger.info(f"报告目录 {report_dir} 包含 {len(report_files)} 个文件")
                    else:
                        logger.warning(f"⚠️ {test_name} 报告生成完成但index.html不存在")
                        # 如果增强报告模块存在，使用它
                        if generate_enhanced_html_report:
                            generate_enhanced_html_report(jtl_file, report_dir, test_name, logger)
                        else:
                            logger.warning(f"⚠️ 增强报告模块不可用，无法为 {test_name} 生成备用报告")
                else:
                    logger.error(f"❌ {test_name} HTML报告生成失败，退出码: {report_process.returncode}")
                    # 如果增强报告模块存在，使用它
                    if generate_enhanced_html_report:
                        generate_enhanced_html_report(jtl_file, report_dir, test_name, logger)
                    else:
                        logger.warning(f"⚠️ 增强报告模块不可用，无法为 {test_name} 生成备用报告")
                    
            except subprocess.TimeoutExpired:
                logger.warning(f"⏰ {test_name} HTML报告生成超时")
                # 如果增强报告模块存在，使用它
                if generate_enhanced_html_report:
                    generate_enhanced_html_report(jtl_file, report_dir, test_name, logger)
                else:
                    logger.warning(f"⚠️ 增强报告模块不可用，无法为 {test_name} 生成备用报告")
            except Exception as e:
                logger.error(f"❌ {test_name} HTML报告生成异常: {e}")
                # 如果增强报告模块存在，使用它
                if generate_enhanced_html_report:
                    generate_enhanced_html_report(jtl_file, report_dir, test_name, logger)
                else:
                    logger.warning(f"⚠️ 增强报告模块不可用，无法为 {test_name} 生成备用报告")
        
        logger.info("批量报告生成完成")
        
        # 第三阶段：生成报告汇总页面（调用独立模块）
        logger.info("    ")
        logger.info("======== 第三阶段：生成报告汇总页面 =========")
        try:
            if generate_report_summary:
                summary_success = generate_report_summary(config, logger, timestamp)
                if summary_success:
                    logger.info("🎉 报告汇总页面生成完成")
                else:
                    logger.warning("⚠️ 报告汇总页面生成失败，但脚本继续执行")
            else:
                logger.warning("⚠️ 报告汇总模块不可用，跳过汇总页面生成")
        except Exception as e:
            logger.error(f"❌ 报告汇总页面生成过程中出现异常: {e}")
            logger.warning("⚠️ 报告汇总页面生成失败，但脚本继续执行")
        
        return True
        
    except Exception as e:
        logger.error(f"批量生成HTML报告时发生错误: {e}")
        return False

def generate_report_summary_wrapper(config, logger, timestamp):
    """报告汇总页面的包装函数，处理模块导入问题"""
    try:
        from report_summary import generate_report_summary
        return generate_report_summary(config, logger, timestamp)
    except ImportError as e:
        logger.warning(f"无法导入report_summary模块: {e}")
        return False
    except Exception as e:
        logger.error(f"报告汇总页面生成过程中出现异常: {e}")
        return False

def move_reports_to_base_dir(report_dir, reports_base_dir, test_name, logger):
    """移动报告文件"""
    try:
        logger.info(f"开始移动报告文件从 {report_dir} 到 {reports_base_dir}")
        
        if not report_dir.exists():
            logger.warning(f"报告目录不存在: {report_dir}")
            return False
        
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
            if source_file.name.lower() == 'index.html':
                target_name = f"{test_name}_index.html"
            else:
                target_name = f"{test_name}_{source_file.name}"
            
            target_file = reports_base_dir / target_name
            
            try:
                shutil.move(str(source_file), str(target_file))
                logger.info(f"已移动文件: {source_file.name} -> {target_name}")
                moved_count += 1
            except Exception as e:
                logger.error(f"移动文件 {source_file.name} 时出错: {e}")
        
        if moved_count == len(files_to_move):
            logger.info(f"所有 {moved_count} 个报告文件已成功移动")
            try:
                if report_dir.exists():
                    remaining_files = list(report_dir.iterdir())
                    if len(remaining_files) == 0:
                        report_dir.rmdir()
                        logger.info(f"已删除空报告目录: {report_dir}")
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
    logger = get_logger()
    logger.info("JMeter 5.6.3 批量HTML报告生成脚本启动")
    
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
    
    # 第一阶段：执行所有测试，生成JTL文件
    logger.info("    ")
    logger.info("======== 第一阶段：执行所有JMeter测试 ========")
    jtl_files = []
    successful_tests = []
    project_name = config.get('project_name', 'default')
    
    for jmx_file in jmx_files:
        logger.info(f"开始处理测试计划: {jmx_file.name}")
        
        success, jtl_file = run_single_test(jmx_file, timestamp, config)
        
        if success and jtl_file:
            successful_tests.append(jmx_file.stem)
            jtl_files.append(jtl_file)
            logger.info(f"✅ 测试 {jmx_file.name} 完成")
        else:
            logger.error(f"❌ 测试 {jmx_file.name} 失败")
        
        # 测试间隔
        interval = config.get('interval_between_tests', 10)
        if jmx_file != jmx_files[-1]:
            logger.info(f"等待 {interval} 秒后执行下一个测试...")
            time.sleep(interval)
    
    logger.info(f"测试执行完成，成功 {len(successful_tests)}/{len(jmx_files)} 个测试")
    
    # 第二阶段：批量生成HTML报告
    if jtl_files:
        logger.info("    ")
        logger.info("======== 第二阶段：批量生成HTML报告 =========")
        batch_success = generate_batch_html_reports(config, jtl_files, timestamp, logger)
        
        if batch_success:
            logger.info("🎉 所有报告生成完成")
            
            # 第三阶段：生成报告汇总页面（使用包装函数）
            logger.info("    ")
            logger.info("======== 第三阶段：生成报告汇总页面 =========")
            try:
                summary_success = generate_report_summary_wrapper(config, logger, timestamp)
                if summary_success:
                    logger.info("🎉 报告汇总页面生成完成")
                else:
                    logger.warning("⚠️ 报告汇总页面生成失败，但脚本继续执行")
            except Exception as e:
                logger.error(f"❌ 报告汇总页面生成过程中出现异常: {e}")
                logger.warning("⚠️ 报告汇总页面生成失败，但脚本继续执行")
        else:
            logger.error("❌ 批量报告生成过程中出现错误")
    else:
        logger.error("❌ 没有成功的测试，无法生成报告")
    
    logger.info("脚本执行完成")

if __name__ == "__main__":
    main()