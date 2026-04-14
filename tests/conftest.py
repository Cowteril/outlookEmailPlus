"""
pytest配置文件
为所有测试设置必要的环境变量
"""

import os
import sys
from pathlib import Path

# 设置测试环境变量
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-pytest')


def pytest_configure(config):
    """pytest配置钩子"""
    # 确保可以导入项目模块
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
