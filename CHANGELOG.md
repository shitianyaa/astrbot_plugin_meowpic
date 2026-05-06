# Changelog

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
