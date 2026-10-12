# 主一 v1.1.0

每天读完一份有尽头的材料，再留下自己的判断。

这一版重做了整个界面，功能和数据与 v1.0.0 兼容：直接替换程序即可，档案、批注和设置都保留在原来的数据目录里。

## 下载

- [Windows 10 / 11 · x64](https://github.com/xyxxxx06221/attention/releases/download/v1.1.0-desktop/Zhuyi-v1.1.0-Windows-x64.zip)：解压完整文件夹，双击 Zhuyi.exe。
- [Mac · Apple 芯片](https://github.com/xyxxxx06221/attention/releases/download/v1.1.0-desktop/Zhuyi-v1.1.0-macOS-arm64.zip)：解压，将 Zhuyi.app 拖入应用程序后打开。
- [Mac · Intel 芯片](https://github.com/xyxxxx06221/attention/releases/download/v1.1.0-desktop/Zhuyi-v1.1.0-macOS-x64.zip)：解压，将 Zhuyi.app 拖入应用程序后打开。

无需安装 Python 或 Node.js。启动后自动在默认浏览器打开完整工作台，保留控制窗即可使用。初次启动为空档案，不附带用户数据或模型密钥。

## 本版变化

- **全新界面**：暖白纸面、墨色文字、单一青色强调与细线分隔；文章标题使用衬线体，正文限制在适合阅读的栏宽内。
- **深色主题**：浅色、深色或跟随系统，在侧栏底部或设置页切换。
- **手机尺寸**：导航改为底部标签栏，阅读器全屏展开。
- **批注面板**：阅读器够宽时与正文并排，不再遮挡原文。
- **采集提示更准确**：只有来源失败、单篇抓取失败或日期无法确认时才提示「采集有缺项」，提示可以关闭。来源首页超过扫描上限、快讯正文过短，改为只在来源报告里记录。
- 优先使用系统字体，内置中文字体只在系统缺少时加载。

本机 `/api/*` 接口的请求与响应没有变化。

[完整介绍、截图与使用说明](https://github.com/xyxxxx06221/attention#readme)

三个安装包分别在对应平台构建，通过业务测试、前端检查，以及实际打包程序的启动、静态资源、中文写入、重启持久化和退出验证。下载附件同时提供 SHA-256 校验文件。

桌面包无商业代码签名，Mac 未经 Apple 公证。系统可能要求确认开发者与来源，请按系统安全设置处理。Apple 芯片包在 macOS 14 构建，Intel 包在 macOS 15 构建；更低系统版本未验证。

采用 PolyForm Noncommercial 1.0.0 许可；品牌、字体与第三方内容说明见仓库 LICENSE、NOTICE 及 dist/vendor/THIRD-PARTY.md。
