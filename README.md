<div align="center">
    <h1>超星学习通课程导出工具</h1>
    <h2>CxKitty</h2>
    <img alt="Github License" src="https://img.shields.io/github/license/SocialSisterYi/CxKitty">
</div>

基于 [SocialSisterYi/CxKitty](https://github.com/SocialSisterYi/CxKitty) 二次开发，将"自动答题"改造为"课程试题爬取与导出"工具。

- Web 可视化界面，浏览器操作
- 支持已批阅试题回顾页解析，自动提取正确答案
- 浏览课程章节、查看题目详情
- 一键导出 Word 文档（.docx），含题目、选项、正确答案
- 携带进度条的导出体验

## 启动方式

```bash
# 安装依赖
pip install -r requirements.txt

# 启动 Web UI
python -m web.app
```

Windows 用户可直接双击 `启动WebUI.bat`

## 界面预览

启动后浏览器自动打开，支持手机号密码或二维码登录，之后即可浏览课程、查看试题、导出 Word。

## 免责声明

- 本项目基于 [GPL-3.0 License](LICENSE)
- 仅供学习研究使用，请勿用于盈利
- 使用本项目造成的任何后果与本人无关

## 原项目

[SocialSisterYi/CxKitty](https://github.com/SocialSisterYi/CxKitty) — 超星学习通自动完成任务点工具
