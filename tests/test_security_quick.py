"""
使用现有数据库的快速测试
"""

import sys
from pathlib import Path

# 确保可以导入应用模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from outlook_web.services.email_security import EmailSecurityScanner


def test_scanner_with_real_emails():
    """测试扫描器使���真实邮件数据"""
    scanner = EmailSecurityScanner()

    # 测试安全邮件
    safe_email = {
        'id': 'test-safe',
        'subject': 'Team Meeting',
        'body': 'Let\'s meet tomorrow',
        'body_preview': 'Let\'s meet tomorrow',
        'from': 'colleague@company.com',
        'has_attachments': False,
        'date': '2026-04-14T10:00:00Z'
    }

    result = scanner.scan_email(safe_email)
    assert result['risk_level'] == 'safe'
    print(f"[PASS] Safe email test - Risk level: {result['risk_level']}")

    # 测试高危邮件
    phishing_email = {
        'id': 'test-risk',
        'subject': 'URGENT: Verify Your Microsoft Account Now',
        'body': 'Click http://microsoft-security.xyz to verify immediately',
        'body_preview': 'Click http://microsoft-security.xyz',
        'from': 'security-alert@gmail.com',
        'has_attachments': True,
        'date': '2026-04-14T10:00:00Z'
    }

    result = scanner.scan_email(phishing_email)
    assert result['risk_level'] == 'high'
    assert len(result['risks']) >= 2
    print(f"[PASS] High risk email test - Risk level: {result['risk_level']}")
    print(f"       Risks detected: {result['risks']}")

    print("\n[SUCCESS] All scanner tests passed!")


if __name__ == '__main__':
    test_scanner_with_real_emails()
