# 外网访问指南

## 前置条件

- Python 环境已配置，依赖已安装 (`pip install -r requirements.txt`)
- cloudflared 已下载（放置于 `D:\AI\cloudflared-windows-amd64.exe`）

## 启动步骤

需要打开 **两个终端窗口**，分别运行以下命令：

### 终端 1 - 启动 Web 服务

```bash
cd /d E:\Workspace\open\SmartLottery-AI
python main.py serve
```

服务默认监听 `http://0.0.0.0:8080`，局域网可通过 `http://192.168.1.32:8080` 访问。

### 终端 2 - 启动外网隧道

```powershell
D:\AI\cloudflared-windows-amd64.exe tunnel --url http://localhost:8080
```

启动后终端会输出类似以下格式的公网地址：

```
https://xxx-xxx-xxx.trycloudflare.com
```

将此地址发给朋友即可外网访问。

## 注意事项

- 隧道地址**每次启动都会变化**，关闭后失效，适合临时测试
- 两个终端窗口都需要保持运行，关闭任一窗口服务将中断
- 免费方案，无需注册 Cloudflare 账号
