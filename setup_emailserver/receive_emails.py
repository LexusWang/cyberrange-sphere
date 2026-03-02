#!/usr/bin/env python3
"""
邮件接收脚本 - 用于在C机器上接收邮件并下载附件
"""

import imaplib
import email
from email.header import decode_header
import os
import argparse
from datetime import datetime

def decode_str(s):
    """解码邮件头"""
    if s is None:
        return ""
    value, encoding = decode_header(s)[0]
    if isinstance(value, bytes):
        if encoding:
            return value.decode(encoding)
        return value.decode('utf-8', errors='ignore')
    return value

def download_attachments(msg, output_dir):
    """下载邮件附件"""
    attachments = []
    
    for part in msg.walk():
        # 检查是否是附件
        if part.get_content_maintype() == 'multipart':
            continue
        if part.get('Content-Disposition') is None:
            continue
            
        filename = part.get_filename()
        if filename:
            # 解码文件名
            filename = decode_str(filename)
            
            # 保存附件
            filepath = os.path.join(output_dir, filename)
            
            # 避免重复文件名
            counter = 1
            while os.path.exists(filepath):
                name, ext = os.path.splitext(filename)
                filepath = os.path.join(output_dir, f"{name}_{counter}{ext}")
                counter += 1
            
            with open(filepath, 'wb') as f:
                f.write(part.get_payload(decode=True))
            
            file_size = os.path.getsize(filepath)
            attachments.append({
                'filename': os.path.basename(filepath),
                'path': filepath,
                'size': file_size
            })
            print(f"  └─ 附件已保存: {filepath} ({file_size} bytes)")
    
    return attachments

def get_email_body(msg):
    """提取邮件正文"""
    body = ""
    
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            
            # 跳过附件
            if "attachment" in content_disposition:
                continue
            
            # 获取正文
            if content_type == "text/plain":
                try:
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    break
                except:
                    pass
            elif content_type == "text/html" and not body:
                try:
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                except:
                    pass
    else:
        try:
            body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        except:
            body = str(msg.get_payload())
    
    return body

def receive_emails(imap_server, imap_port, username, password, output_dir, 
                   limit=10, unread_only=False):
    """
    连接IMAP服务器并接收邮件
    """
    try:
        # 连接到IMAP服务器
        print(f"正在连接到 {imap_server}:{imap_port}...")
        mail = imaplib.IMAP4(imap_server, imap_port)
        
        # 登录
        print(f"正在登录 {username}...")
        mail.login(username, password)
        
        # 选择收件箱
        mail.select('INBOX')
        
        # 搜索邮件
        if unread_only:
            status, messages = mail.search(None, 'UNSEEN')
            print("只显示未读邮件")
        else:
            status, messages = mail.search(None, 'ALL')
            print("显示所有邮件")
        
        # 获取邮件ID列表
        email_ids = messages[0].split()
        
        if not email_ids:
            print("\n📭 收件箱为空")
            return []
        
        total_emails = len(email_ids)
        print(f"\n📬 找到 {total_emails} 封邮件")
        
        # 限制显示数量
        if limit and limit < total_emails:
            email_ids = email_ids[-limit:]  # 获取最新的N封
            print(f"   只显示最新的 {limit} 封\n")
        else:
            print()
        
        # 创建输出目录
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"✓ 创建输出目录: {output_dir}\n")
        
        emails_data = []
        
        # 遍历邮件
        for i, email_id in enumerate(email_ids, 1):
            # 获取邮件
            status, msg_data = mail.fetch(email_id, '(RFC822)')
            
            # 解析邮件
            msg = email.message_from_bytes(msg_data[0][1])
            
            # 提取信息
            subject = decode_str(msg.get('Subject', '(无主题)'))
            from_addr = decode_str(msg.get('From', ''))
            to_addr = decode_str(msg.get('To', ''))
            date = msg.get('Date', '')
            
            print(f"{'='*60}")
            print(f"邮件 #{i}")
            print(f"{'='*60}")
            print(f"主题: {subject}")
            print(f"发件人: {from_addr}")
            print(f"收件人: {to_addr}")
            print(f"日期: {date}")
            
            # 获取正文
            body = get_email_body(msg)
            print(f"\n正文预览:")
            print(f"  {body[:200]}{'...' if len(body) > 200 else ''}")
            
            # 下载附件
            print(f"\n附件:")
            attachments = download_attachments(msg, output_dir)
            if not attachments:
                print("  └─ 无附件")
            
            print()  # 空行分隔
            
            emails_data.append({
                'id': email_id.decode(),
                'subject': subject,
                'from': from_addr,
                'to': to_addr,
                'date': date,
                'body': body,
                'attachments': attachments
            })
        
        # 关闭连接
        mail.close()
        mail.logout()
        
        print(f"✅ 成功接收 {len(emails_data)} 封邮件")
        if any(e['attachments'] for e in emails_data):
            total_attachments = sum(len(e['attachments']) for e in emails_data)
            print(f"✅ 下载了 {total_attachments} 个附件到: {output_dir}")
        
        return emails_data
        
    except imaplib.IMAP4.error as e:
        print(f"❌ IMAP错误: {e}")
        print("\n可能的原因:")
        print("  1. 用户名或密码错误")
        print("  2. IMAP服务未启动")
        print("  3. 网络连接问题")
        return []
    except Exception as e:
        print(f"❌ 错误: {e}")
        return []


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='接收邮件并下载附件',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 接收所有邮件
  %(prog)s --server 192.168.1.100 --user victim --password victim123
  
  # 只接收未读邮件
  %(prog)s --server 192.168.1.100 --user victim --password victim123 --unread
  
  # 限制显示最新10封
  %(prog)s --server 192.168.1.100 --user victim --password victim123 --limit 10
  
  # 指定附件保存目录
  %(prog)s --server 192.168.1.100 --user victim --password victim123 \\
    --output ./downloads
        """
    )
    
    parser.add_argument('--server', required=True,
                       help='IMAP服务器地址')
    parser.add_argument('--port', type=int, default=143,
                       help='IMAP端口 (默认143)')
    parser.add_argument('--user', required=True,
                       help='用户名 (不含@domain)')
    parser.add_argument('--password', required=True,
                       help='密码')
    parser.add_argument('--output', default='./attachments',
                       help='附件保存目录 (默认: ./attachments)')
    parser.add_argument('--limit', type=int, default=10,
                       help='显示邮件数量限制 (默认10, 0表示全部)')
    parser.add_argument('--unread', action='store_true',
                       help='只显示未读邮件')
    
    args = parser.parse_args()
    
    print(f"""
╔════════════════════════════════════════════════════════╗
║              邮件接收与附件下载工具                    ║
╚════════════════════════════════════════════════════════╝

配置:
  IMAP服务器: {args.server}:{args.port}
  用户名: {args.user}
  输出目录: {args.output}
  限制: {args.limit if args.limit > 0 else '无限制'}
  模式: {'未读邮件' if args.unread else '所有邮件'}

""")
    
    emails = receive_emails(
        args.server,
        args.port,
        args.user,
        args.password,
        args.output,
        args.limit if args.limit > 0 else None,
        args.unread
    )
    
    if emails:
        print(f"""
{'='*60}
📊 接收统计
{'='*60}
总邮件数: {len(emails)}
有附件: {sum(1 for e in emails if e['attachments'])}
总附件数: {sum(len(e['attachments']) for e in emails)}
保存位置: {args.output}
{'='*60}
""")
