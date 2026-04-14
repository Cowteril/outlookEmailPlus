"""
使用真实数据库的API集成测试
避免临时数据库问题
"""

import pytest
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSecurityAPIWithRealDB:
    """使用真实数据库的API测试"""

    @pytest.fixture(scope='module')
    def app(self):
        """创建测试应用（使用真实数据库）"""
        # 不修改环境变量，使用项目现有数据库
        from outlook_web.app import create_app
        app = create_app(autostart_scheduler=False)
        yield app

    @pytest.fixture
    def client(self, app):
        """测试客户端"""
        return app.test_client()

    @pytest.fixture
    def auth_session(self, client):
        """认证会话"""
        with client.session_transaction() as sess:
            sess['user_id'] = 'test'
            sess['_fresh'] = True
        return client

    def test_security_stats_api(self, auth_session):
        """测试安全统计API"""
        response = auth_session.get('/api/security/stats?days=7')
        assert response.status_code == 200

        data = response.get_json()
        assert data['success'] is True
        assert 'stats' in data

        # 验证数据结构
        stats = data['stats']
        assert 'high' in stats
        assert 'medium' in stats
        assert 'low' in stats
        assert 'safe' in stats
        assert 'total' in stats

    def test_risky_emails_api(self, auth_session):
        """测试风险邮件列表API"""
        response = auth_session.get('/api/security/risky-emails?limit=10')
        assert response.status_code == 200

        data = response.get_json()
        assert data['success'] is True
        assert 'emails' in data
        assert 'total' in data

    def test_api_response_format(self, auth_session):
        """测试API响应格式"""
        response = auth_session.get('/api/security/stats?days=7')
        assert response.status_code == 200

        data = response.get_json()

        # 验证响应结构
        assert isinstance(data.get('success'), bool)
        assert isinstance(data.get('stats'), dict)

    def test_api_with_different_days(self, auth_session):
        """测试不同的统计天数"""
        for days in [1, 7, 30, 90]:
            response = auth_session.get(f'/api/security/stats?days={days}')
            assert response.status_code == 200

            data = response.get_json()
            assert data['success'] is True

    def test_api_error_handling(self, auth_session):
        """测试API错误处理"""
        # 测试无效的days参数
        response = auth_session.get('/api/security/stats?days=invalid')
        # 应该返回200但使用默认值，或者400错误
        assert response.status_code in [200, 400]


class TestSecurityAPIAuthentication:
    """测试API认证"""

    @pytest.fixture
    def app(self):
        """创建测试应用"""
        from outlook_web.app import create_app
        app = create_app(autostart_scheduler=False)
        yield app

    @pytest.fixture
    def client(self, app):
        """测试客户端"""
        return app.test_client()

    def test_unauthenticated_request(self, client):
        """测试未认证请求"""
        response = client.get('/api/security/stats')
        # 应该返回302重定向到登录页
        assert response.status_code in [302, 401, 403]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
