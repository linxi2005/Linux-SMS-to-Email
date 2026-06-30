# EC20 SMS Forwarder

面向 Linux 小盒子、ARMv7、Ubuntu 20 的移远 EC20 短信接收与邮件转发系统。

## 功能

- 多个 EC20 模块配置与持久化
- 串口独占锁定
- 启动初始化：`ATE0`、`AT+CMGF=1`、`AT+CPMS="MT","MT","MT"`、`AT+CNMI=2,1,0,0,0`
- 监听 `+CMTI`，收到通知后执行 `AT+CMGR=index`
- UCS2 中文短信自动解码
- SQLite 存储与 hash 去重
- SMTP 邮件转发与手动重发
- 手动读取模块内短信，不入库，仅页面显示
- AT 调试、日志、数据库维护页面

## 安装

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## 运行

```bash
python app.py
```

默认访问：

```text
http://设备IP:5000
```

默认登录：

```text
用户名：admin
密码：admin
```

部署后请立即修改 `config/config.json` 中的管理员密码哈希和 `secret_key`。

## 模块配置

模块信息保存到：

```text
config/modem_config.json
```

示例：

```json
{
  "modems": [
    {"port": "/dev/ttyUSB2", "remark": "EC20-1", "enabled": true}
  ]
}
```

也可以在 Web 后台的模块管理页面添加、修改备注、删除或重启模块。

## 邮件配置

邮件配置保存到：

```text
config/mail.json
```

支持 SSL/TLS、多个收件人和变量模板。

## systemd

复制服务文件：

```bash
sudo cp systemd/sms-forward.service /etc/systemd/system/sms-forward.service
sudo systemctl daemon-reload
sudo systemctl enable sms-forward
sudo systemctl start sms-forward
```

请根据实际安装目录修改服务文件中的 `WorkingDirectory` 和 `ExecStart`。
