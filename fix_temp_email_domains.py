import sqlite3
import json

conn = sqlite3.connect('data/outlook_accounts.db')
cursor = conn.cursor()

# 更新域名配置
domains_config = json.dumps(["mail.chatgpt.org.uk"], ensure_ascii=False)
cursor.execute("UPDATE settings SET value = ? WHERE key = 'temp_mail_domains'", (domains_config,))

# 更新默认域名
cursor.execute("UPDATE settings SET value = ? WHERE key = 'temp_mail_default_domain'", ("mail.chatgpt.org.uk",))

conn.commit()
print("Domain configuration updated successfully")
print("Domains: mail.chatgpt.org.uk")
print("Default domain: mail.chatgpt.org.uk")

conn.close()
