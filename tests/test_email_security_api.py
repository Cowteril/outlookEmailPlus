"""
邮件安全API接口集成测试
测试所有安全相关的API端点
"""

import pytest
import json
from pathlib import Path
import sqlite3
import tempfile
import os


# 确保可以导入应用模块
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSecurityAPI:
    """测试安全API接口"""

    @pytest.fixture
    def db_path(self):
        """创建临时数据库路径"""
        temp_db = tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False)
        temp_db.close()
        yield temp_db.name
        # 清理
        try:
            os.unlink(temp_db.name)
        except:
            pass

    @pytest.fixture
    def app(self, db_path):
        """创建测试应用实例"""
        # 设置测试环境变量
        os.environ['SECRET_KEY'] = 'test-secret-key-for-testing'
        os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'

        from outlook_web.app import create_app
        app = create_app(autostart_scheduler=False)

        # 初始化测试数据库
        with app.app_context():
            from outlook_web.db import init_db
            init_db()

            # 使用应用的数据库连接
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # 插入测试账号
            cursor.execute("""
                INSERT INTO accounts (email, password, client_id, refresh_token, group_id, status)
                VALUES (?, ?, ?, ?, 1, 'active')
            """, ('test@example.com', 'password', 'client-id', 'refresh-token'))

            conn.commit()
            conn.close()

        yield app

    @pytest.fixture
    def client(self, app):
        """创建测试客户端"""
        return app.test_client()

    @pytest.fixture
    def auth_session(self, client):
        """创建已认证的会话"""
        with client.session_transaction() as sess:
            sess['user_id'] = 'test'
            sess['_fresh'] = True
        return client

    @pytest.fixture
    def db_conn(self, app):
        """提供数据库连接的fixture"""
        db_path = app.config.get('DATABASE_URL', '').replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        yield conn
        conn.close()

    def test_security_stats_api_no_data(self, auth_session):
        """测试安全统计API（无数据）"""
        response = auth_session.get('/api/security/stats?days=7')
        assert response.status_code == 200

        data = response.get_json()
        assert data['success'] is True
        assert 'stats' in data
        assert data['stats']['high'] == 0
        assert data['stats']['medium'] == 0
        assert data['stats']['low'] == 0
        assert data['stats']['safe'] == 0

    def test_security_stats_api_with_data(self, auth_session, app):
        """测试安全统计API（有数据）"""
        with app.app_context():
            from outlook_web.db import get_db
            conn = get_db()
            cursor = conn.cursor()

            # 插入扫描记录
            scan_time = '2026-04-14T10:00:00Z'
            cursor.execute("""
                INSERT INTO email_security_scans
                (account_id, email_id, account_email, risk_level, risks, scan_time, created_at)
                VALUES (1, 'email-1', 'test@example.com', 'high', '["Risk 1", "Risk 2"]', ?, ?)
            """, (scan_time, scan_time))

            cursor.execute("""
                INSERT INTO email_security_scans
                (account_id, email_id, account_email, risk_level, risks, scan_time, created_at)
                VALUES (1, 'email-2', 'test@example.com', 'safe', '[]', ?, ?)
            """, (scan_time, scan_time))

            conn.commit()
            conn.close()

        response = auth_session.get('/api/security/stats?days=7')
        assert response.status_code == 200

        data = response.get_json()
        assert data['success'] is True
        assert data['stats']['high'] == 1
        assert data['stats']['safe'] == 1

    def test_risky_emails_api_no_data(self, auth_session):
        """测试风险邮件列表API（无数据）"""
        response = auth_session.get('/api/security/risky-emails?limit=10')
        assert response.status_code == 200

        data = response.get_json()
        assert data['success'] is True
        assert data['emails'] == []
        assert data['total'] == 0

    def test_risky_emails_api_with_data(self, auth_session, app):
        """测试风险邮件列表API（有数据）"""
        with app.app_context():
            from outlook_web.db import get_db
            conn = get_db()
            cursor = conn.cursor()

            scan_time = '2026-04-14T10:00:00Z'
            risks = json.dumps(['钓鱼域名', '可疑发件人'], ensure_ascii=False)

            cursor.execute("""
                INSERT INTO email_security_scans
                (account_id, email_id, account_email, risk_level, risks, scan_time, created_at)
                VALUES (1, 'email-1', 'test@example.com', 'high', ?, ?, ?)
            """, (risks, scan_time, scan_time))

            conn.commit()
            conn.close()

        response = auth_session.get('/api/security/risky-emails?limit=10')
        assert response.status_code == 200

        data = response.get_json()
        assert data['success'] is True
        assert len(data['emails']) == 1
        assert data['emails'][0]['risk_level'] == 'high'
        assert len(data['emails'][0]['risks']) == 2

    def test_risky_emails_api_min_risk_filter(self, auth_session, app):
        """测试风险等级过滤"""
        with app.app_context():
            from outlook_web.db import get_db
            conn = get_db()
            cursor = conn.cursor()

            scan_time = '2026-04-14T10:00:00Z'

            # 插入不同风险等级的邮件
            cursor.execute("""
                INSERT INTO email_security_scans
                (account_id, email_id, account_email, risk_level, risks, scan_time, created_at)
                VALUES (1, 'email-1', 'test@example.com', 'high', '["Risk"]', ?, ?)
            """, (scan_time, scan_time))

            cursor.execute("""
                INSERT INTO email_security_scans
                (account_id, email_id, account_email, risk_level, risks, scan_time, created_at)
                VALUES (1, 'email-2', 'test@example.com', 'low', '["Risk"]', ?, ?)
            """, (scan_time, scan_time))

            conn.commit()
            conn.close()

        # 只返回中危及以上
        response = auth_session.get('/api/security/risky-emails?limit=10&min_risk=medium')
        assert response.status_code == 200

        data = response.get_json()
        assert data['success'] is True
        assert len(data['emails']) == 1
        assert data['emails'][0]['risk_level'] == 'high'

    def test_security_api_requires_login(self, client):
        """测试API需要登录"""
        response = client.get('/api/security/stats')
        # 未登录应该返回重定向或401
        assert response.status_code in [302, 401, 403]

    def test_security_stats_api_custom_days(self, auth_session):
        """测试自定义统计天数"""
        response = auth_session.get('/api/security/stats?days=30')
        assert response.status_code == 200

        data = response.get_json()
        assert data['success'] is True
        assert 'stats' in data

    def test_security_stats_api_invalid_days(self, auth_session):
        """测试无效的天数参数"""
        response = auth_session.get('/api/security/stats?days=invalid')
        # 应该返回400或使用默认值
        assert response.status_code in [200, 400]


class TestSecurityAPIDataIntegrity:
    """测试API数据完整性"""

    @pytest.fixture
    def app(self):
        """创建测试应用"""
        os.environ['SECRET_KEY'] = 'test-secret-key'
        os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

        from outlook_web.app import create_app
        app = create_app(autostart_scheduler=False)

        with app.app_context():
            from outlook_web.db import init_db
            init_db()

        yield app

    @pytest.fixture
    def client(self, app):
        """创建测试客户端"""
        return app.test_client()

    @pytest.fixture
    def auth_session(self, client):
        """创建已认证的会话"""
        with client.session_transaction() as sess:
            sess['user_id'] = 'test'
            sess['_fresh'] = True
        return client

    def test_email_security_scans_table_structure(self, app):
        """测试email_security_scans表结构"""
        with app.app_context():
            from outlook_web.db import get_db
            conn = get_db()
            cursor = conn.cursor()

            # 检查表是否存在
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='email_security_scans'
            """)
            result = cursor.fetchone()
            assert result is not None

            # 检查列
            cursor.execute("PRAGMA table_info(email_security_scans)")
            columns = {col[1] for col in cursor.fetchall()}

            required_columns = {
                'id', 'account_id', 'email_id', 'account_email',
                'risk_level', 'risks', 'scan_time', 'created_at'
            }
            assert required_columns.issubset(columns)

            conn.close()

    def test_indexes_created(self, app):
        """测试索引是否创建"""
        with app.app_context():
            from outlook_web.db import get_db
            conn = get_db()
            cursor = conn.cursor()

            # 检查索引
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='index' AND tbl_name='email_security_scans'
            """)
            indexes = cursor.fetchall()

            # 应该有至少4个索引
            assert len(indexes) >= 4

            # 检查关键索引
            index_names = {idx[0] for idx in indexes}
            assert 'idx_email_security_scans_account_id' in index_names
            assert 'idx_email_security_scans_risk_level' in index_names

            conn.close()

    def test_risk_level_constraint(self, app):
        """测试risk_level约束"""
        with app.app_context():
            from outlook_web.db import get_db
            conn = get_db()
            cursor = conn.cursor()

            # 尝试插入无效的风险等级
            try:
                cursor.execute("""
                    INSERT INTO email_security_scans
                    (account_id, email_id, account_email, risk_level, risks, scan_time, created_at)
                    VALUES (1, 'test-id', 'test@example.com', 'invalid', '[]', '2026-04-14T10:00:00Z', '2026-04-14T10:00:00Z')
                """)
                conn.commit()
                assert False, "Should have failed due to CHECK constraint"
            except sqlite3.IntegrityError:
                # 预期的行为
                pass
            finally:
                conn.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
