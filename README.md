<div align="center">
    <h1>CxKitty-Tool</h1>
    <p>超星学习通 · 课程试题爬取与导出工具</p>

  <img alt="Python" src="https://img.shields.io/badge/Python-3.10+-blue?logo=python">
  <img alt="Flask" src="https://img.shields.io/badge/Web-Flask-green?logo=flask">
  <img alt="License" src="https://img.shields.io/github/license/Mafeixxn/CxKitty-Tool">
  <img alt="Last Commit" src="https://img.shields.io/github/last-commit/Mafeixxn/CxKitty-Tool">
</div>

---

## 简介

基于 [SocialSisterYi/CxKitty](https://github.com/SocialSisterYi/CxKitty) 二次开发，保留其优秀 API 层，将自动化答题功能改造为**课程试题浏览与导出**工具。提供干净现代的 Web 界面，方便你整理和保存课程题目。

## 特性

- **Web 可视化界面** — 浏览器即用，无需命令行，现代 UI 设计
- **双登录方式** — 支持手机号密码登录和学习通 APP 扫码登录
- **课程总览** — 卡片式展示所有课程，状态一目了然
- **章节浏览** — 查看每个章节的视频、文档、测验任务点
- **试题查看** — 题目、选项、正确答案高亮，支持已批阅试题回顾
- **一键导出** — 生成 Word (.docx) 文档，带实时进度条
- **会话持久化** — 登录一次，后续自动恢复，无需反复输入密码

## 快速开始

### 环境要求

- Python 3.10+

### 安装运行

```bash
# 克隆仓库
git clone https://github.com/Mafeixxn/CxKitty-Tool.git
cd CxKitty-Tool

# 安装依赖
pip install flask requests qrcode pycryptodome lxml pyyaml jsonpath-python wcwidth beautifulsoup4 rich python-docx

# 启动
python -m web.app
```

**Windows 用户**：直接双击 `启动WebUI.bat`

浏览器会自动打开 `http://127.0.0.1:5000`，登录后即可使用。

## 使用说明

1. 打开后进入登录页，输入手机号和密码，或切换到二维码扫码登录
2. 登录成功后显示课程列表，点击课程进入详情
3. 章节列表中，蓝色标签的测验可点击"查看题目"
4. 试题页展示所有题目，正确答案以绿色高亮
5. 点击右上角"导出 Word"下载 .docx 文件

## 项目结构

```
CxKitty-Tool/
├── web/                   # Web UI 模块
│   ├── app.py             # Flask 应用入口
│   ├── routes/            # 路由蓝图（auth/courses/exam/export）
│   └── templates/         # Jinja2 页面模板（Tailwind CSS）
├── cxapi/                 # 学习通 API 封装层
│   ├── api.py             # 登录与会话管理
│   ├── chapters.py        # 章节与任务点管理
│   ├── classes.py         # 课程数据模型
│   ├── schema.py          # 数据结构定义
│   └── jobs/              # 任务点处理器
│       ├── exam.py        # 测验（支持回顾页解析）
│       ├── video.py       # 视频
│       └── document.py    # 文档
├── main.py                # 原终端 TUI 入口
├── utils.py               # 会话持久化工具
└── 启动WebUI.bat           # Windows 一键启动
```

## 致谢

- [SocialSisterYi/CxKitty](https://github.com/SocialSisterYi/CxKitty) — 强大的学习通 API 层实现
- [Tailwind CSS](https://tailwindcss.com/) — 页面样式框架

## 免责声明

本项目仅供**学习研究**使用，请勿用于任何商业或违规用途。使用本项目所产生的任何后果由使用者自行承担。
