#!/usr/bin/env python3
"""
发送带附件的钓鱼邮件测试脚本
用于从A机器发送邮件到B服务器
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import argparse
import os

def send_email_with_attachment(smtp_server, smtp_port, from_addr, to_addr, 
                                subject, body_html, attachment_path=None):
    """
    发送带附件的HTML邮件
    """
    try:
        # 创建邮件对象
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = from_addr
        msg['To'] = to_addr
        
        # 添加HTML正文
        html_part = MIMEText(body_html, 'html')
        msg.attach(html_part)
        
        # 添加附件
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                
                filename = os.path.basename(attachment_path)
                part.add_header('Content-Disposition', 
                              f'attachment; filename={filename}')
                msg.attach(part)
            print(f"✓ 已添加附件: {filename}")
        
        # 连接SMTP服务器并发送
        with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
            server.set_debuglevel(0)  # 设为1可看详细日志
            server.sendmail(from_addr, to_addr, msg.as_string())
        
        print(f"✓ 邮件已成功发送到 {to_addr}")
        return True
        
    except Exception as e:
        print(f"✗ 发送失败: {e}")
        return False


# 钓鱼邮件模板
TEMPLATES = {
    "malware": {
        "subject": "重要文件需要您审阅",
        "body": """
        <html>
        <body>
            <p>亲爱的同事，</p>
            <p>附件中包含本月的重要报告，请查收并回复。</p>
            <p><strong>请尽快下载并查看附件文档。</strong></p>
            <p>如有疑问请联系人力资源部。</p>
            <br>
            <p>人力资源部</p>
            <p><small>此邮件由系统自动发送</small></p>
        </body>
        </html>
        """
    },
    
    "invoice_attachment": {
        "subject": "发票 #2024-INV-8372",
        "body": """
        <html>
        <body style="font-family: Arial, sans-serif;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd;">
                <h2 style="color: #333;">未支付发票提醒</h2>
                <p>您好，</p>
                <p>附件中是您未支付的发票副本。</p>
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <tr style="background: #f5f5f5;">
                        <td style="padding: 10px; border: 1px solid #ddd;">发票编号</td>
                        <td style="padding: 10px; border: 1px solid #ddd;">INV-2024-8372</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #ddd;">金额</td>
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>$8,500.00</strong></td>
                    </tr>
                    <tr style="background: #f5f5f5;">
                        <td style="padding: 10px; border: 1px solid #ddd;">到期日</td>
                        <td style="padding: 10px; border: 1px solid #ddd; color: red;"><strong>今天</strong></td>
                    </tr>
                </table>
                <p><strong>请下载附件查看详细信息并尽快支付。</strong></p>
                <p>如有疑问，请回复此邮件。</p>
                <br>
                <p>财务部<br>
                电话: 555-0123<br>
                邮箱: finance@company.com</p>
            </div>
        </body>
        </html>
        """
    },
    
    "resume": {
        "subject": "求职申请 - 高级软件工程师",
        "body": """
        <html>
        <body>
            <p>尊敬的招聘经理，</p>
            <p>我对贵公司发布的高级软件工程师职位非常感兴趣。</p>
            <p>附件是我的简历，期待您的回复。</p>
            <br>
            <p>最好的祝愿，</p>
            <p>张三<br>
            手机: 138-0000-0000<br>
            邮箱: zhangsan@email.com</p>
        </body>
        </html>
        """
    },
    
    "contract": {
        "subject": "合同文件待签署",
        "body": """
        <html>
        <body>
            <h2 style="color: #1a73e8;">DocuSign - 文件需要您的签名</h2>
            <p>您好，</p>
            <p>以下文件正在等待您的电子签名：</p>
            <ul>
                <li>文件名称: 服务协议 2024.pdf</li>
                <li>发件人: 法务部</li>
                <li>截止日期: 48小时内</li>
            </ul>
            <p><strong>请下载附件并按照说明完成签署。</strong></p>
            <p>如果您没有请求此文档，请忽略此邮件。</p>
            <br>
            <p>此邮件由 DocuSign 电子签名服务发送</p>
        </body>
        </html>
        """
    }
}


def create_fake_pdf():
    """创建一个假的PDF文件用于测试"""
    fake_pdf = "test_document.pdf"
    if not os.path.exists(fake_pdf):
        # 创建一个假的PDF（实际是文本文件）
        with open(fake_pdf, 'w') as f:
            f.write("%PDF-1.4\n")
            f.write("This is a test file for phishing simulation.\n")
            f.write("In a real attack, this could be malware.\n")
        print(f"✓ 创建测试文件: {fake_pdf}")
    return fake_pdf


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='发送带附件的钓鱼测试邮件',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用模板发送带附件
  %(prog)s --server 192.168.1.100 --to victim@test.local \\
    --template invoice_attachment --attachment malware.exe
  
  # 自定义邮件
  %(prog)s --server 192.168.1.100 --to user@test.local \\
    --subject "Important" --body "<h1>Click me</h1>" \\
    --attachment document.pdf
        """
    )
    
    parser.add_argument('--server', required=True, 
                       help='SMTP服务器地址')
    parser.add_argument('--port', type=int, default=25, 
                       help='SMTP端口 (默认25)')
    parser.add_argument('--from', dest='from_addr', 
                       default='admin@company.com', 
                       help='发件人地址')
    parser.add_argument('--to', dest='to_addr', required=True, 
                       help='收件人地址')
    parser.add_argument('--template', choices=TEMPLATES.keys(), 
                       help='使用预定义模板')
    parser.add_argument('--subject', help='自定义主题')
    parser.add_argument('--body', help='自定义HTML正文')
    parser.add_argument('--attachment', help='附件文件路径')
    parser.add_argument('--create-fake', action='store_true',
                       help='创建一个假的PDF文件用于测试')
    
    args = parser.parse_args()
    
    # 创建假文件选项
    if args.create_fake:
        fake_file = create_fake_pdf()
        if not args.attachment:
            args.attachment = fake_file
    
    # 确定邮件内容
    if args.template:
        template = TEMPLATES[args.template]
        subject = args.subject or template['subject']
        body = args.body or template['body']
    elif args.subject and args.body:
        subject = args.subject
        body = args.body
    else:
        parser.error("必须指定 --template 或同时指定 --subject 和 --body")
    
    print(f"""
╔════════════════════════════════════════════════════════╗
║          发送带附件的钓鱼测试邮件                      ║
╚════════════════════════════════════════════════════════╝

配置:
  SMTP: {args.server}:{args.port}
  发件人: {args.from_addr}
  收件人: {args.to_addr}
  主题: {subject}
  附件: {args.attachment or '无'}
  
正在发送...
""")
    
    success = send_email_with_attachment(
        args.server,
        args.port,
        args.from_addr,
        args.to_addr,
        subject,
        body,
        args.attachment
    )
    
    if success:
        print("""
✅ 发送成功！

下一步: 在接收端(C机器)使用邮件客户端或脚本接收邮件
""")
    else:
        print("\n❌ 发送失败")
