import sqlite3
import json

conn = sqlite3.connect('data/outlook_accounts.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 检查临时邮箱配置
cursor.execute("SELECT key, value FROM settings WHERE key LIKE 'temp_mail_%'")
configs = cursor.fetchall()

print("临时邮箱配置：")
for config in configs:
    try:
        value_json = json.loads(config['value'])
        print(f"\n{config['key']}:")
        print(json.dumps(value_json, indent=2, ensure_ascii=False))
    except:
        print(f"\n{config['key']}: {config['value']}")

conn.close()
