# 安全策略

## 报告漏洞

- 涉及凭证处理、越权、注入等**敏感安全问题，请勿提交公开 issue**：请通过 GitHub 的
  Security 标签页 → "Report a vulnerability" 私下报告；无法使用该入口时，issue 里只描述现象、
  不要粘贴凭证或日志原文，维护者会与你联系。
- 一般功能性 bug 走正常 issue 模板，并附 `ark_doctor.py` 与 `selftest.py` 输出。

## 范围

- 属于：仓库内代码、`install.py`、`scripts/` 的网络请求与凭证处理。
- 不属于：森空岛/鹰角接口本身被官方改版、需要游戏内登录态的官方功能缺失。

## 用户自查

- 凭证等同账号钥匙：`~/.arkbox/credentials.json`（权限 600），不要分享内容或截图。
- 疑似泄露：立即运行 `skland_core.py logout`，并在森空岛 App「授权管理」中解除授权。

## 说明

本项目纯标准库零依赖，没有第三方供应链依赖面；全部网络出口集中在
`skill/arkbox/SKILL.md`「网络出口清单」，可自行审计。
