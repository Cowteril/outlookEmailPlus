"""
邮��安全API路由
提供危险邮件扫描、统计、查询等接口
"""

from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List
import sqlite3
import json

from outlook_web.services.email_security import EmailSecurityScanner, scan_emails_batch
from outlook_web.security.auth import login_required  # 使用项目的认证系统


# 创建蓝图
security = Blueprint('security', __name__)


def get_db_path():
    """获取数据库路径"""
    return Path('data/outlook_accounts.db')


def get_security_stats(days: int = 7) -> Dict:
    """
    获取安全统计数据

    Args:
        days: 统计最近多少天的数据

    Returns:
        统计字典
    """
    db_path = get_db_path()
    if not db_path.exists():
        return {'high': 0, 'medium': 0, 'low': 0, 'safe': 0, 'total': 0}

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 计算时间阈值
        threshold = (datetime.now() - timedelta(days=days)).isoformat()

        # 统计各风险等级数量
        cursor.execute("""
            SELECT risk_level, COUNT(*) as count
            FROM email_security_scans
            WHERE scan_time >= ?
            GROUP BY risk_level
        """, (threshold,))

        stats = {'high': 0, 'medium': 0, 'low': 0, 'safe': 0, 'total': 0}

        for row in cursor.fetchall():
            risk_level = row['risk_level']
            count = row['count']
            stats[risk_level] = count
            stats['total'] += count

        conn.close()
        return stats

    except Exception as e:
        print(f"Error getting security stats: {e}")
        return {'high': 0, 'medium': 0, 'low': 0, 'safe': 0, 'total': 0}


def get_risky_emails(limit: int = 50, min_risk: str = 'low') -> List[Dict]:
    """
    获取风险邮件列表

    Args:
        limit: 返回数量限制
        min_risk: 最低风险等级 ('low', 'medium', 'high')

    Returns:
        风险邮件列表
    """
    db_path = get_db_path()
    if not db_path.exists():
        return []

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 风险等级映射
        risk_order = {'high': 3, 'medium': 2, 'low': 1, 'safe': 0}
        min_order = risk_order.get(min_risk, 1)

        # 查询风险邮件，根据min_risk过滤
        cursor.execute("""
            SELECT
                id, account_id, email_id, risk_level, risks, scan_time,
                created_at, account_email
            FROM email_security_scans
            WHERE risk_level != 'safe'
              AND CASE risk_level
                  WHEN 'high' THEN 3
                  WHEN 'medium' THEN 2
                  WHEN 'low' THEN 1
                  ELSE 0
              END >= ?
            ORDER BY
                CASE risk_level
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    WHEN 'low' THEN 3
                END,
                scan_time DESC
            LIMIT ?
        """, (min_order, limit))

        emails = []
        for row in cursor.fetchall():
            emails.append({
                'id': row['id'],
                'account_id': row['account_id'],
                'email_id': row['email_id'],
                'account_email': row['account_email'],
                'risk_level': row['risk_level'],
                'risks': json.loads(row['risks']) if row['risks'] else [],
                'scan_time': row['scan_time'],
                'created_at': row['created_at']
            })

        conn.close()
        return emails

    except Exception as e:
        print(f"Error getting risky emails: {e}")
        return []


@security.route('/api/security/stats')
@login_required
def api_security_stats():
    """
    获取安全统计API

    参数:
        days: 统计天数（默认7天）

    返回:
        {
            "success": true,
            "stats": {
                "high": 0,
                "medium": 0,
                "low": 0,
                "safe": 0,
                "total": 0
            }
        }
    """
    try:
        days = request.args.get('days', 7, type=int)
        stats = get_security_stats(days)

        return jsonify({
            'success': True,
            'stats': stats
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@security.route('/api/security/risky-emails')
@login_required
def api_risky_emails():
    """
    获取风险邮件列表API

    参数:
        limit: 返回数量限制（默认50）
        min_risk: 最低风险等级（默认'low'）

    返回:
        {
            "success": true,
            "emails": [...],
            "total": 10
        }
    """
    try:
        limit = request.args.get('limit', 50, type=int)
        min_risk = request.args.get('min_risk', 'low')

        emails = get_risky_emails(limit, min_risk)

        return jsonify({
            'success': True,
            'emails': emails,
            'total': len(emails)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@security.route('/api/security/scan/<int:account_id>', methods=['POST'])
@login_required
def api_scan_account(account_id):
    """
    扫描账号邮件API

    参数:
        limit: 扫描邮件数量限制（默认100）
        folder: 文件夹名称（默认'inbox'）

    返回:
        {
            "success": true,
            "result": {
                "scanned": 100,
                "risky": 5,
                "high_risk": 1,
                "medium_risk": 2,
                "low_risk": 2
            }
        }
    """
    try:
        from outlook_web.repositories.accounts import AccountRepository
        from outlook_web.services.graph import GraphService

        limit = request.args.get('limit', 100, type=int)
        folder = request.args.get('folder', 'inbox')

        # 获取账号信息
        account_repo = AccountRepository()
        account = account_repo.find_by_id(account_id)

        if not account:
            return jsonify({
                'success': False,
                'error': 'Account not found'
            }), 404

        # 使用GraphService获取邮件
        graph_service = GraphService(account)

        try:
            # 获取邮件列表
            emails = graph_service.get_emails(
                folder_name=folder,
                limit=limit
            )

            if not emails:
                return jsonify({
                    'success': True,
                    'result': {
                        'scanned': 0,
                        'risky': 0,
                        'high_risk': 0,
                        'medium_risk': 0,
                        'low_risk': 0
                    }
                })

            # 扫描邮件
            scanner = EmailSecurityScanner()
            results = []

            for email in emails:
                scan_result = scanner.scan_email(email)

                # 保存扫描结果到数据库
                save_scan_result(
                    account_id=account_id,
                    email_id=email.get('id'),
                    account_email=account.email,
                    scan_result=scan_result
                )

                results.append(scan_result)

            # 统计结果
            stats = {
                'scanned': len(results),
                'risky': 0,
                'high_risk': 0,
                'medium_risk': 0,
                'low_risk': 0
            }

            for result in results:
                if result['risk_level'] != 'safe':
                    stats['risky'] += 1
                    stats[f"{result['risk_level']}_risk"] += 1

            return jsonify({
                'success': True,
                'result': stats
            })

        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Graph API error: {str(e)}'
            }), 500

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def save_scan_result(account_id: int, email_id: str, account_email: str, scan_result: Dict):
    """
    保存扫描结果到数据库

    Args:
        account_id: 账号ID
        email_id: 邮件ID
        account_email: 账号邮箱
        scan_result: 扫描结果
    """
    db_path = get_db_path()

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 检查是否已存在
        cursor.execute("""
            SELECT id FROM email_security_scans
            WHERE account_id = ? AND email_id = ?
        """, (account_id, email_id))

        existing = cursor.fetchone()

        # 准备数据
        risks_json = json.dumps(scan_result['risks'], ensure_ascii=False)
        scan_time = scan_result['scan_time'].isoformat()

        if existing:
            # 更新现有记录
            cursor.execute("""
                UPDATE email_security_scans
                SET risk_level = ?, risks = ?, scan_time = ?
                WHERE account_id = ? AND email_id = ?
            """, (scan_result['risk_level'], risks_json, scan_time,
                  account_id, email_id))
        else:
            # 插入新记录
            cursor.execute("""
                INSERT INTO email_security_scans
                (account_id, email_id, account_email, risk_level, risks, scan_time, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (account_id, email_id, account_email,
                  scan_result['risk_level'], risks_json, scan_time,
                  datetime.now().isoformat()))

        conn.commit()
        conn.close()

    except Exception as e:
        print(f"Error saving scan result: {e}")


def create_blueprint():
    """创建并返回安全蓝图"""
    return security
