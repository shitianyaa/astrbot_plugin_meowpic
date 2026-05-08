# Changelog

## 1.4.0 - 2026-05-08

- 在喵图姬内置 `hentai` 图片撤回监听，默认查找最近 2 分钟内机器人发出的图片。
- 同一撤回窗口内有多张图时，可重复触发监听词向前递推撤回。
- 新增图片撤回白名单、允许所有人撤回机器人图片开关、成功/超时回复自定义配置。

## 1.3.1 - 2026-05-06

- Pixiv/API 请求超时时返回更明确的用户提示，避免记录为未知异常。
- Pixiv 图片地址支持 `i.pixiv.re` 与 `i.pximg.net` 之间自动兜底尝试，降低反代超时影响。

## 1.3.0 - 2026-05-06

- Pixiv 默认接口切换为 Lolicon v2：`https://api.lolicon.app/setu/v2`。
- 自动将旧内置 Pixiv 默认接口迁移到 Lolicon v2。
- 新增 `/pixiv [标签...]`、`/meowpic pixiv [标签...]` 和 `/meowpic get pixiv [标签...]` 动态标签随机图。
- 新增 Pixiv 专用配置：`pixiv_r18`、`pixiv_size`、`pixiv_proxy`、`pixiv_exclude_ai`、`pixiv_default_tags`、`pixiv_aspect_ratio`。
- 优化空结果与 API 错误提示。

## 1.2.1 - 2026-05-06

- 新增 `CHANGELOG.md`，开始记录版本变更。
- 同步提升插件版本号到 `1.2.1`。

## 1.2.0 - 2026-05-06

- 新增 Pixiv 非 R18 分类，默认使用 `https://api.mossia.top/duckMo?num=1&r18Type=0&proxy=i.pixiv.re`。
- 新增 `/pixiv`、`/p站`、`/px`、`/meowpic pixiv` 指令。
- 新增 `api_pixiv_url` 配置项，支持在插件配置里覆盖 Pixiv 接口地址。
- 为 Pixiv 直链下载增加 `https://www.pixiv.net/` Referer 兜底。

## 1.1.0 - 2026-05-05

- 支持多分类随机图片：随机小姐姐、白丝、黑丝、二次元、JK。
- 支持用户通过 `/meowpic setapi`、`/meowpic setkey` 覆盖个人 API 配置。
- 增加请求限流、图片下载到本地、JSON 图片地址自动提取等能力。
