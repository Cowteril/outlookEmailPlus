"""
邮件安全扫描服务
检测危险邮件，包括钓鱼链接、恶意附件、可疑发件人等
"""

import re
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path


class SecurityRule:
    """安全规则基类"""

    def check(self, email: Dict) -> Optional[str]:
        """
        检查邮件是否违反此规则

        Args:
            email: 邮件数据字典

        Returns:
            如果违反规则，返回风险描述；否则返回None
        """
        raise NotImplementedError


class PhishingURLRule(SecurityRule):
    """钓鱼URL检测规则"""

    # 可疑的域名特征
    SUSPICIOUS_PATTERNS = [
        r'microsoft-security\.xyz',  # 假冒微软
        r'microsoft365\.security',
        r'office365\-verify\.com',
        r'account\-verification\.microsoft',
        r'secure\-account\.microsoft',
        r'outlook\-login\.microsoft',
    ]

    # 可疑的URL关键词
    SUSPICIOUS_KEYWORDS = [
        'verify', 'confirm', 'suspend', 'urgent',
        'immediate', 'account', 'security', 'update'
    ]

    def check(self, email: Dict) -> Optional[str]:
        """检查钓鱼链接"""
        subject = email.get('subject', '').lower()
        body = email.get('body', '').lower()
        body_preview = email.get('body_preview', '').lower()

        # 检查可疑域名
        for pattern in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, body, re.IGNORECASE):
                return f"检测到钓鱼域名: {pattern}"

        # 检查可疑URL + 紧急关键词组合
        if any(kw in subject for kw in ['urgent', 'immediate', 'suspend', 'verify']):
            # 检查是否有URL
            urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', body)
            if urls:
                return f"可疑紧急主题 + URL组合: {subject[:50]}"

        return None


class SuspiciousSenderRule(SecurityRule):
    """可疑发件人检测规则"""

    # 免费邮箱域名（通常用于钓鱼）
    FREE_EMAIL_DOMAINS = [
        'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
        'qq.com', '163.com', '126.com'
    ]

    # 官方机构应该使用的域名
    OFFICIAL_DOMAINS = {
        'microsoft': ['microsoft.com', 'microsoft365.com', 'office.com'],
        'apple': ['apple.com', 'icloud.com'],
        'google': ['google.com', 'gmail.com'],
        'amazon': ['amazon.com', 'amazon.support'],
        'facebook': ['facebook.com', 'meta.com'],
    }

    def check(self, email: Dict) -> Optional[str]:
        """检查可疑发件人"""
        from_email = email.get('from', '')
        subject = email.get('subject', '').lower()

        # 提取发件人域名
        match = re.search(r'@([^>\s]+)', from_email)
        if not match:
            return None

        domain = match.group(1).lower()

        # 检查是否声称是官方机构但使用免费邮箱
        for company, official_domains in self.OFFICIAL_DOMAINS.items():
            if company in subject:
                if domain in self.FREE_EMAIL_DOMAINS:
                    return f"冒充{company.capitalize()}但使用免费邮箱: {domain}"
                if domain not in official_domains:
                    return f"可疑的{company.capitalize()}发件人域名: {domain}"

        return None


class MaliciousAttachmentRule(SecurityRule):
    """恶意附件检测规则"""

    # 危险文件扩展名
    DANGEROUS_EXTENSIONS = [
        '.exe', '.scr', '.bat', '.cmd', '.com', '.pif',
        '.vbs', '.js', '.jse', '.wsf', '.wsh', '.msi',
        '.docm', '.xlsm', '.pptm',  # 启用宏的Office文档
    ]

    # 可疑的附件名
    SUSPICIOUS_NAMES = [
        'invoice', 'payment', 'urgent', 'document',
        'scan', 'photo', 'resume', 'cv'
    ]

    def check(self, email: Dict) -> Optional[str]:
        """检查恶意附件"""
        has_attachments = email.get('has_attachments', False)
        subject = email.get('subject', '').lower()

        if not has_attachments:
            return None

        # 如果有附件 + 紧急主题，标记为可疑
        if any(kw in subject for kw in ['urgent', 'immediate', 'asap', 'important']):
            return f"可疑附件 + 紧急主题组合"

        # 注意：Graph API没有提供附件详细信息
        # 这里只做基础检测
        return "邮件包含附件（需要人工审查）"


class SuspiciousSubjectRule(SecurityRule):
    """可疑主题检测规则"""

    # 常见的钓鱼主题关键词
    PHISHING_KEYWORDS = [
        'verify your account', 'account suspended', 'urgent action required',
        'security alert', 'confirm your identity', 'update payment information',
        'your account will be closed', 'unusual sign-in activity',
        'click here to', 'immediate attention', 'verify now',
    ]

    # 垃圾邮件特征（使用更宽松的匹配）
    SPAM_PATTERNS = [
        r'congratulations.*you.*won',
        r'you.*have.*been.*selected',
        r'claim.*your.*prize',
        r'urgent.*business.*proposal',
        r'lottery|winner|jackpot',
    ]

    def check(self, email: Dict) -> Optional[str]:
        """检查可疑主题"""
        subject = email.get('subject', '').lower()

        # 检查钓鱼关键词
        for keyword in self.PHISHING_KEYWORDS:
            if keyword in subject:
                return f"可疑主题关键词: {keyword}"

        # 检查垃圾邮件模式（不区分大小写）
        for pattern in self.SPAM_PATTERNS:
            if re.search(pattern, subject, re.IGNORECASE):
                return f"垃圾邮件模式: {pattern}"

        return None


class EmailSecurityScanner:
    """邮件安全扫描器"""

    def __init__(self):
        """初始化扫描器"""
        self.rules = [
            PhishingURLRule(),
            SuspiciousSenderRule(),
            MaliciousAttachmentRule(),
            SuspiciousSubjectRule(),
        ]

    def scan_email(self, email: Dict) -> Dict:
        """
        扫描单封邮件

        Args:
            email: 邮件数据字典，需要包含:
                   - id: 邮件ID
                   - subject: 主题
                   - body: 正文
                   - body_preview: 正文预览
                   - from: 发件人
                   - has_attachments: 是否有附件
                   - date: 日期

        Returns:
            扫描结果字典:
            {
                'email_id': str,
                'risk_level': 'high' | 'medium' | 'low' | 'safe',
                'risks': List[str],
                'scan_time': datetime
            }
        """
        risks = []

        # 应用所有规则
        for rule in self.rules:
            risk = rule.check(email)
            if risk:
                risks.append(risk)

        # 计算风险等级
        risk_level = self._calculate_risk_level(risks, email)

        return {
            'email_id': email.get('id'),
            'risk_level': risk_level,
            'risks': risks,
            'scan_time': datetime.now()
        }

    def _calculate_risk_level(self, risks: List[str], email: Dict) -> str:
        """
        根据检测到的风险计算风险等级

        Args:
            risks: 风险列表
            email: 邮件数据

        Returns:
            风险等级: 'high', 'medium', 'low', 'safe'
        """
        if not risks:
            return 'safe'

        # 高危条件
        if any('钓鱼域名' in risk or '冒充' in risk for risk in risks):
            return 'high'

        # 如果有多个风险
        if len(risks) >= 3:
            return 'high'

        # 如果有2个风险
        if len(risks) >= 2:
            return 'medium'

        # 中危条件
        if any('紧急主题' in risk or '可疑主题' in risk for risk in risks):
            return 'medium'

        # 低危
        return 'low'

    def scan_emails(self, emails: List[Dict]) -> List[Dict]:
        """
        批量扫描邮件

        Args:
            emails: 邮件列表

        Returns:
            扫描结果列表
        """
        return [self.scan_email(email) for email in emails]


# 便捷函数
def scan_email_for_security(email: Dict) -> Dict:
    """
    扫描单封邮件的安全风险

    Args:
        email: 邮件数据

    Returns:
        扫描结果
    """
    scanner = EmailSecurityScanner()
    return scanner.scan_email(email)


def scan_emails_batch(emails: List[Dict]) -> List[Dict]:
    """
    批量扫描邮件

    Args:
        emails: 邮件列表

    Returns:
        扫描结果列表
    """
    scanner = EmailSecurityScanner()
    return scanner.scan_emails(emails)
