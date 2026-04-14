"""
邮件安全扫描服务单元测试
测试各种检测规则和扫描功能
"""

import pytest
from datetime import datetime
from outlook_web.services.email_security import (
    EmailSecurityScanner,
    PhishingURLRule,
    SuspiciousSenderRule,
    MaliciousAttachmentRule,
    SuspiciousSubjectRule,
    scan_email_for_security,
    scan_emails_batch
)


class TestPhishingURLRule:
    """测试钓鱼URL检测规则"""

    def test_no_phishing_url(self):
        """测试正常邮件"""
        rule = PhishingURLRule()
        email = {
            'subject': 'Team Meeting',
            'body': 'Let\'s meet tomorrow to discuss the project.',
            'body_preview': 'Let\'s meet tomorrow'
        }
        result = rule.check(email)
        assert result is None

    def test_suspicious_phishing_domain(self):
        """测试可疑钓鱼域名"""
        rule = PhishingURLRule()
        email = {
            'subject': 'Verify Your Account',
            'body': 'Click http://microsoft-security.xyz to verify',
            'body_preview': 'Click http://microsoft-security.xyz'
        }
        result = rule.check(email)
        assert result is not None
        assert '钓鱼域名' in result or 'phishing' in result.lower()

    def test_urgent_subject_with_url(self):
        """测试紧急主题+URL组合"""
        rule = PhishingURLRule()
        email = {
            'subject': 'URGENT: Verify Now or Account Suspended',
            'body': 'Click http://example.com/verify immediately',
            'body_preview': 'Click http://example.com/verify'
        }
        result = rule.check(email)
        assert result is not None
        assert '紧急' in result or 'urgent' in result.lower()


class TestSuspiciousSenderRule:
    """测试可疑发件人检测规则"""

    def test_normal_sender(self):
        """测试正常发件人"""
        rule = SuspiciousSenderRule()
        email = {
            'from': 'colleague@company.com',
            'subject': 'Project Update'
        }
        result = rule.check(email)
        assert result is None

    def test_fake_microsoft_with_free_email(self):
        """测试假冒微软但使用免费邮箱"""
        rule = SuspiciousSenderRule()
        email = {
            'from': 'security-alert@gmail.com',
            'subject': 'Microsoft Account Verification Required'
        }
        result = rule.check(email)
        assert result is not None
        assert 'Microsoft' in result or 'microsoft' in result.lower()

    def test_fake_apple_with_free_email(self):
        """测试假冒Apple但使用免费邮箱"""
        rule = SuspiciousSenderRule()
        email = {
            'from': 'apple-support@yahoo.com',
            'subject': 'Apple ID Suspended'
        }
        result = rule.check(email)
        assert result is not None


class TestMaliciousAttachmentRule:
    """测试恶意附件检测规则"""

    def test_no_attachment(self):
        """测试无附件邮件"""
        rule = MaliciousAttachmentRule()
        email = {
            'has_attachments': False,
            'subject': 'Hello'
        }
        result = rule.check(email)
        assert result is None

    def test_attachment_with_urgent_subject(self):
        """测试附件+紧急主题"""
        rule = MaliciousAttachmentRule()
        email = {
            'has_attachments': True,
            'subject': 'URGENT: Open Immediately'
        }
        result = rule.check(email)
        assert result is not None
        assert '附件' in result or 'attachment' in result.lower()


class TestSuspiciousSubjectRule:
    """测试可疑主题检测规则"""

    def test_normal_subject(self):
        """测试正常主题"""
        rule = SuspiciousSubjectRule()
        email = {
            'subject': 'Project Meeting Tomorrow'
        }
        result = rule.check(email)
        assert result is None

    def test_phishing_keywords(self):
        """测试钓鱼关键词"""
        rule = SuspiciousSubjectRule()
        email = {
            'subject': 'Verify Your Account Now or Suspended'
        }
        result = rule.check(email)
        assert result is not None

    def test_spam_patterns(self):
        """测试垃圾邮件模式"""
        rule = SuspiciousSubjectRule()
        email = {
            'subject': 'CONGRATULATIONS! You Won a Prize'
        }
        result = rule.check(email)
        assert result is not None


class TestEmailSecurityScanner:
    """测试邮件安全扫描器"""

    def test_safe_email(self):
        """测试安全邮件"""
        scanner = EmailSecurityScanner()
        email = {
            'id': 'test-001',
            'subject': 'Team Meeting',
            'body': 'Let\'s meet tomorrow',
            'body_preview': 'Let\'s meet tomorrow',
            'from': 'colleague@company.com',
            'has_attachments': False,
            'date': '2026-04-14T10:00:00Z'
        }
        result = scanner.scan_email(email)
        assert result['risk_level'] == 'safe'
        assert len(result['risks']) == 0
        assert result['email_id'] == 'test-001'

    def test_high_risk_email(self):
        """测试高危邮件"""
        scanner = EmailSecurityScanner()
        email = {
            'id': 'test-002',
            'subject': 'URGENT: Verify Your Microsoft Account Now',
            'body': 'Click http://microsoft-security.xyz to verify immediately',
            'body_preview': 'Click http://microsoft-security.xyz',
            'from': 'security-alert@gmail.com',
            'has_attachments': True,
            'date': '2026-04-14T10:00:00Z'
        }
        result = scanner.scan_email(email)
        assert result['risk_level'] == 'high'
        assert len(result['risks']) >= 2

    def test_medium_risk_email(self):
        """测试中危邮件"""
        scanner = EmailSecurityScanner()
        email = {
            'id': 'test-003',
            'subject': 'CONGRATULATIONS! You Won a Prize',
            'body': 'Click here to claim your reward now!',
            'body_preview': 'Click here to claim',
            'from': 'promo@lottery.com',
            'has_attachments': False,
            'date': '2026-04-14T10:00:00Z'
        }
        result = scanner.scan_email(email)
        assert result['risk_level'] in ['medium', 'low']

    def test_batch_scan(self):
        """测试批量扫描"""
        scanner = EmailSecurityScanner()
        emails = [
            {
                'id': 'batch-001',
                'subject': 'Safe Email',
                'body': 'Normal content',
                'body_preview': 'Normal',
                'from': 'test@test.com',
                'has_attachments': False,
                'date': '2026-04-14T10:00:00Z'
            },
            {
                'id': 'batch-002',
                'subject': 'URGENT: Verify Now',
                'body': 'Click http://evil.com',
                'body_preview': 'Click http://evil.com',
                'from': 'scam@gmail.com',
                'has_attachments': True,
                'date': '2026-04-14T10:00:00Z'
            }
        ]
        results = scanner.scan_emails(emails)
        assert len(results) == 2
        assert results[0]['risk_level'] == 'safe'
        assert results[1]['risk_level'] == 'high'


class TestConvenienceFunctions:
    """测试便捷函数"""

    def test_scan_email_for_security(self):
        """测试单封邮件扫描便捷函数"""
        email = {
            'id': 'conv-001',
            'subject': 'Test',
            'body': 'Test body',
            'body_preview': 'Test',
            'from': 'test@test.com',
            'has_attachments': False,
            'date': '2026-04-14T10:00:00Z'
        }
        result = scan_email_for_security(email)
        assert 'risk_level' in result
        assert 'risks' in result
        assert 'email_id' in result

    def test_scan_emails_batch(self):
        """测试批量扫描便捷函数"""
        emails = [
            {
                'id': f'batch-{i}',
                'subject': 'Test',
                'body': 'Test body',
                'body_preview': 'Test',
                'from': 'test@test.com',
                'has_attachments': False,
                'date': '2026-04-14T10:00:00Z'
            }
            for i in range(5)
        ]
        results = scan_emails_batch(emails)
        assert len(results) == 5


class TestRiskLevelCalculation:
    """测试风险等级计算"""

    def test_no_risks_safe(self):
        """测试无风险=安全"""
        scanner = EmailSecurityScanner()
        result = scanner._calculate_risk_level([], {})
        assert result == 'safe'

    def test_single_risk_low(self):
        """测试单个风险=低危"""
        scanner = EmailSecurityScanner()
        result = scanner._calculate_risk_level(['Suspicious subject'], {})
        assert result == 'low'

    def test_multiple_risks_medium(self):
        """测试多个风险=中危"""
        scanner = EmailSecurityScanner()
        result = scanner._calculate_risk_level(['Risk 1', 'Risk 2'], {})
        assert result == 'medium'

    def test_phishing_domain_high(self):
        """测试钓鱼域名=高危"""
        scanner = EmailSecurityScanner()
        result = scanner._calculate_risk_level(
            ['钓鱼域名: evil.com'],
            {}
        )
        assert result == 'high'

    def test_three_risks_high(self):
        """测试3个风险=高危"""
        scanner = EmailSecurityScanner()
        result = scanner._calculate_risk_level(
            ['Risk 1', 'Risk 2', 'Risk 3'],
            {}
        )
        assert result == 'high'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
