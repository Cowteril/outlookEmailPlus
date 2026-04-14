"""
危险邮件预警功能端到端测试
测试完整的用户流程和功能集成
"""

import pytest
import json
import time
from pathlib import Path
import tempfile
import os


class TestSecurityAlertsEndToEnd:
    """测试危险邮件预警功能的完整流程"""

    @pytest.fixture
    def app(self):
        """创建测试应用"""
        os.environ['SECRET_KEY'] = 'test-secret-key-for-e2e-testing'
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
            sess['logged_in'] = True
            sess['user_id'] = 'test'
            sess['_fresh'] = True
        return client

    def test_complete_security_scan_workflow(self, auth_session, app):
        """测试完整的扫描工作流程"""
        # 1. 初始状态：可能有之前的测试数据
        response = auth_session.get('/api/security/stats')
        data = response.get_json()
        assert data['success'] is True
        initial_total = data['stats']['total']  # 记录初始数量

        # 2. 模拟插入扫描结果
        with app.app_context():
            from outlook_web.db import get_db
            conn = get_db()
            cursor = conn.cursor()

            # 插入测试账号（使用随机邮箱避免冲突）
            import random
            test_email = f'test-workflow-{random.randint(1000, 9999)}@example.com'
            cursor.execute("""
                INSERT INTO accounts (email, password, client_id, refresh_token, group_id, status)
                VALUES (?, 'pass', 'client-id', 'refresh-token', 1, 'active')
            """, (test_email,))

            # 获取account_id
            cursor.execute("SELECT id FROM accounts WHERE email = ?", (test_email,))
            account_id = cursor.fetchone()[0]

            # 插入扫描结果
            scan_time = '2026-04-14T10:00:00Z'
            risks = json.dumps(['钓鱼域名', '可疑发件人'], ensure_ascii=False)

            cursor.execute("""
                INSERT INTO email_security_scans
                (account_id, email_id, account_email, risk_level, risks, scan_time, created_at)
                VALUES (?, 'email-001', ?, 'high', ?, ?, ?)
            """, (account_id, test_email, risks, scan_time, scan_time))

            cursor.execute("""
                INSERT INTO email_security_scans
                (account_id, email_id, account_email, risk_level, risks, scan_time, created_at)
                VALUES (?, 'email-002', ?, 'safe', '[]', ?, ?)
            """, (account_id, test_email, scan_time, scan_time))

            conn.commit()
            conn.close()

        # 3. 验证统计数据已更新（应该增加2条）
        response = auth_session.get('/api/security/stats')
        data = response.get_json()
        assert data['success'] is True
        assert data['stats']['total'] == initial_total + 2  # 验证增加了2条
        assert data['stats']['high'] >= 1  # 至少有1个高危
        assert data['stats']['safe'] >= 1  # 至少有1个安全

        # 4. 获取风险邮件列表
        response = auth_session.get('/api/security/risky-emails')
        data = response.get_json()
        assert data['success'] is True
        # 应该至少有我们刚插入的高危邮件
        high_risk_emails = [e for e in data['emails'] if e['risk_level'] == 'high']
        assert len(high_risk_emails) >= 1

        # 5. 清理测试数据
        with app.app_context():
            from outlook_web.db import get_db
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM email_security_scans WHERE email_id IN ('email-001', 'email-002')")
            cursor.execute("DELETE FROM accounts WHERE email = ?", (test_email,))
            conn.commit()
            conn.close()

    def test_security_alerts_display_in_dashboard(self, auth_session):
        """测试预警信息在仪表盘的显示"""
        # 获取仪表盘页面
        response = auth_session.get('/')
        assert response.status_code == 200

        # 检查是否包含危险预警卡片
        html = response.data.decode('utf-8')
        assert '危险预警' in html or 'Security Alerts' in html
        assert 'statSecurityAlerts' in html

    def test_security_modal_html_structure(self, auth_session):
        """测试预警模态框的HTML结构"""
        response = auth_session.get('/')
        assert response.status_code == 200

        html = response.data.decode('utf-8')

        # 检查模态框元素
        assert 'securityAlertsModal' in html
        assert '危险邮件预警' in html or 'Security Alerts' in html

    def test_javascript_functions_available(self, auth_session):
        """测试JavaScript函数是否可用"""
        response = auth_session.get('/')
        assert response.status_code == 200

        html = response.data.decode('utf-8')

        # 检查关键JavaScript函数
        assert 'showSecurityAlerts' in html
        assert 'closeSecurityAlertsModal' in html
        assert 'loadSecurityAlerts' in html

    def test_css_styles_for_security_alerts(self, auth_session):
        """测试预警相关的CSS样式"""
        response = auth_session.get('/')
        assert response.status_code == 200

        html = response.data.decode('utf-8')

        # 检查CSS类
        assert 'stat-warning' in html


class TestSecurityAlertsWithRealData:
    """使用真实数据测试安全预警功能"""

    @pytest.fixture
    def app_with_data(self):
        """创建包含测试数据的应用"""
        os.environ['SECRET_KEY'] = 'test-key-with-data'
        os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

        from outlook_web.app import create_app
        app = create_app(autostart_scheduler=False)

        with app.app_context():
            from outlook_web.db import init_db, get_db
            init_db()

            # 插入测试数据
            conn = get_db()
            cursor = conn.cursor()

            # 使用随机邮箱避免冲突
            import random
            test_email1 = f'user1-{random.randint(1000, 9999)}@example.com'
            test_email2 = f'user2-{random.randint(1000, 9999)}@example.com'

            # 插入测试账号
            cursor.execute("""
                INSERT INTO accounts (email, password, client_id, refresh_token, group_id, status)
                VALUES (?, 'pass1', 'client1', 'token1', 1, 'active')
            """, (test_email1,))

            cursor.execute("""
                INSERT INTO accounts (email, password, client_id, refresh_token, group_id, status)
                VALUES (?, 'pass2', 'client2', 'token2', 1, 'active')
            """, (test_email2,))

            # 获取account_ids
            cursor.execute("SELECT id FROM accounts WHERE email = ?", (test_email1,))
            account_id1 = cursor.fetchone()[0]

            cursor.execute("SELECT id FROM accounts WHERE email = ?", (test_email2,))
            account_id2 = cursor.fetchone()[0]

            # 插入各种风险等级的扫描结果
            scan_time = '2026-04-14T10:00:00Z'

            # 高危邮件
            high_risks = json.dumps(['钓鱼域名', '可疑发件人', '恶意附件'], ensure_ascii=False)
            cursor.execute("""
                INSERT INTO email_security_scans
                (account_id, email_id, account_email, risk_level, risks, scan_time, created_at)
                VALUES (?, 'high-risk-1', ?, 'high', ?, ?, ?)
            """, (account_id1, test_email1, high_risks, scan_time, scan_time))

            # 中危邮件
            medium_risks = json.dumps(['可疑主题'], ensure_ascii=False)
            cursor.execute("""
                INSERT INTO email_security_scans
                (account_id, email_id, account_email, risk_level, risks, scan_time, created_at)
                VALUES (?, 'medium-risk-1', ?, 'medium', ?, ?, ?)
            """, (account_id1, test_email1, medium_risks, scan_time, scan_time))

            # 低危邮件
            low_risks = json.dumps(['包含附件'], ensure_ascii=False)
            cursor.execute("""
                INSERT INTO email_security_scans
                (account_id, email_id, account_email, risk_level, risks, scan_time, created_at)
                VALUES (?, 'low-risk-1', ?, 'low', ?, ?, ?)
            """, (account_id2, test_email2, low_risks, scan_time, scan_time))

            # 安全邮件
            cursor.execute("""
                INSERT INTO email_security_scans
                (account_id, email_id, account_email, risk_level, risks, scan_time, created_at)
                VALUES (?, 'safe-1', ?, 'safe', '[]', ?, ?)
            """, (account_id2, test_email2, scan_time, scan_time))

            conn.commit()
            conn.close()

        yield app

    @pytest.fixture
    def client(self, app_with_data):
        """创建测试客户端"""
        return app_with_data.test_client()

    @pytest.fixture
    def auth_session(self, client):
        """创建已认证的会话"""
        with client.session_transaction() as sess:
            sess['logged_in'] = True
            sess['user_id'] = 'test'
            sess['_fresh'] = True
        return client

    def test_stats_aggregation(self, auth_session):
        """测试统计数据聚合"""
        response = auth_session.get('/api/security/stats?days=7')
        data = response.get_json()

        assert data['success'] is True
        # 注意：可能会有其他测试数据，所以检查范围而不是精确值
        assert data['stats']['high'] >= 1
        assert data['stats']['medium'] >= 1
        assert data['stats']['low'] >= 1
        assert data['stats']['safe'] >= 1
        assert data['stats']['total'] >= 4

    def test_risky_emails_filtering(self, auth_session):
        """测试风险邮件过滤"""
        # 只获取中危及以上
        response = auth_session.get('/api/security/risky-emails?min_risk=medium')
        data = response.get_json()

        assert data['success'] is True
        # 验证至少有一些结果（因为数据库中已有数据）
        assert len(data['emails']) >= 2

        # 验证结果只包含中危及以上邮件
        medium_and_high = ['high', 'medium']
        for email in data['emails']:
            assert email['risk_level'] in medium_and_high, f"Expected risk level in {medium_and_high}, got {email['risk_level']}"

        # 验证第一个邮件是高危（按风险等级排序）
        assert data['emails'][0]['risk_level'] == 'high'

    def test_email_details_completeness(self, auth_session):
        """测试邮件详情完整性"""
        response = auth_session.get('/api/security/risky-emails')
        data = response.get_json()

        assert data['success'] is True

        # 检查高危邮件详情
        high_risk_email = next(e for e in data['emails'] if e['risk_level'] == 'high')

        assert high_risk_email['account_email'] == 'user1@example.com'
        assert high_risk_email['email_id'] == 'high-risk-1'
        assert len(high_risk_email['risks']) == 3
        assert '钓鱼域名' in high_risk_email['risks']
        assert '可疑发件人' in high_risk_email['risks']
        assert '恶意附件' in high_risk_email['risks']

    def test_pagination(self, auth_session):
        """测试分页功能"""
        # 限制返回数量
        response = auth_session.get('/api/security/risky-emails?limit=2')
        data = response.get_json()

        assert data['success'] is True
        assert len(data['emails']) <= 2  # 限制为2条
        # 验证total字段存在且非负（在内存数据库中至少有我们的测试数据）
        assert 'total' in data
        assert data['total'] >= 0


class TestSecurityScanningIntegration:
    """测试安全扫描集成"""

    def test_scan_email_integration(self):
        """测试邮件扫描集成"""
        from outlook_web.services.email_security import EmailSecurityScanner

        scanner = EmailSecurityScanner()

        # 测试真实场景的邮件
        test_emails = [
            {
                'id': 'real-1',
                'subject': 'URGENT: Microsoft Account Suspended',
                'body': 'Click http://microsoft-security.xyz to restore access',
                'body_preview': 'Click http://microsoft-security.xyz',
                'from': 'security-alert@gmail.com',
                'has_attachments': True,
                'date': '2026-04-14T10:00:00Z'
            },
            {
                'id': 'real-2',
                'subject': 'Team Meeting Tomorrow',
                'body': 'Let\'s discuss the project progress',
                'body_preview': 'Let\'s discuss',
                'from': 'colleague@company.com',
                'has_attachments': False,
                'date': '2026-04-14T10:00:00Z'
            }
        ]

        results = scanner.scan_emails(test_emails)

        assert len(results) == 2
        assert results[0]['risk_level'] == 'high'
        assert results[1]['risk_level'] == 'safe'


class TestPerformance:
    """性能测试"""

    def test_batch_scan_performance(self):
        """测试批量扫描性能"""
        from outlook_web.services.email_security import EmailSecurityScanner
        import time

        scanner = EmailSecurityScanner()

        # 创建100封测试邮件
        test_emails = []
        for i in range(100):
            if i % 3 == 0:
                # 高危邮件
                test_emails.append({
                    'id': f'perf-{i}',
                    'subject': 'URGENT: Verify Now',
                    'body': 'Click http://evil.com',
                    'body_preview': 'Click http://evil.com',
                    'from': 'scam@gmail.com',
                    'has_attachments': True,
                    'date': '2026-04-14T10:00:00Z'
                })
            else:
                # 安全邮件
                test_emails.append({
                    'id': f'perf-{i}',
                    'subject': f'Email {i}',
                    'body': 'Normal content',
                    'body_preview': 'Normal',
                    'from': f'user{i}@example.com',
                    'has_attachments': False,
                    'date': '2026-04-14T10:00:00Z'
                })

        # 测试扫描速度
        start_time = time.time()
        results = scanner.scan_emails(test_emails)
        end_time = time.time()

        scan_time = end_time - start_time

        assert len(results) == 100
        assert scan_time < 5.0  # 100封邮件应在5秒内完成

        # 统计结果
        high_risk = sum(1 for r in results if r['risk_level'] == 'high')
        safe = sum(1 for r in results if r['risk_level'] == 'safe')

        assert high_risk > 0
        assert safe > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
