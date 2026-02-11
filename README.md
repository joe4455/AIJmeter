# jmeterAI-JTP
A platform for performance testing and stress testing, implemented based on Jmeter, and supports multiple testing scenarios and report analysis. Unmanned monitoring, continuous batch stress testing, generation of comprehensive stress testing results, and AI analysis report.
#
jmeter压测平台，性能测试和压力测试的平台，基于Jmeter实现，支持多种测试场景和报表分析。
无人看守、批量持续压测、形成综合压测结果。通过不同AI服务实现AI分析报告。


# 使用步骤
## 压测参数
### 1，填入应用配置
压测环境和项目，压测并发数，压测时间等，自动传入jmx脚本中。
### 2，上传jmx压测脚本
支持多脚本压测
### 3，执行测试
<img width="1900" height="888" alt="image" src="https://github.com/user-attachments/assets/9dd64cce-19cd-42b0-a404-0612477d81c3" />

### 4，执行过程日志
显示测试过程，AI分析报告过程。以及一些操作的过程

### 5，测试报告
执行完成后，可以查看jmeter html报告。

### 6，AI分析报告
生成的jmeter report通过AI进行分析，形成简明、容易理解的报告。

### 7，JTL文件管理
压测后形成的jtl报告，进行管理

### 8，测试报告历史记录
回顾之前的压测记录，以及对测试报告进行管理
<img width="1880" height="889" alt="image" src="https://github.com/user-attachments/assets/5002cf4f-0d5c-4ff7-bdd8-2698b14090d0" />

### 9，查看jmeter报告
#### summary报告
记录压测相关信息和简略的统计分析。以及对应的jmeter报告列表
<img width="1884" height="894" alt="image" src="https://github.com/user-attachments/assets/5afc602b-8ab2-45b7-bd95-3753476aa29f" />

#### AI分析报告
支持deepseek，千问，月之暗面等
<img width="1880" height="893" alt="image" src="https://github.com/user-attachments/assets/74e34e5a-fcb3-4b13-b3ba-333d75416cd6" />

#### jmeter report
<img width="1910" height="914" alt="image" src="https://github.com/user-attachments/assets/1e333fb5-552f-4e74-9b04-a21251a72560" />




## 项目结构

- `config/` - 配置文件
  - `batches.json` - 批次配置
  - `jmeter.properties` - JMeter属性配置
- `scripts/` - Python脚本
  - `run_batch.py` - 主执行脚本
  - `generate_summary.py` - 生成汇总报告
  - `utils.py` - 工具函数
- `test_plan/` - JMeter测试计划
  - `all_tests.jmx` - 单文件多模块测试计划
- `data/` - 测试数据
  - `users.csv` - 用户数据
- `results/` - 原始结果文件
- `reports/` - HTML报告
- `logs/` - 日志文件

## 使用方法

1. 安装依赖：`pip install -r requirements.txt`
2. 配置批次参数：编辑 `config/batches.json`
3. 运行测试：`python scripts/run_batch.py`
4. 生成报告：`python scripts/generate_summary.py`

# 联系

email： joe45@live.com
qq：
wechat：



