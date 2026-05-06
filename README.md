# 喵图姬

AstrBot 随机图片插件。支持多个默认 API 分类，也支持用户在聊天里覆盖自己的分类 API 和 API Key。

## 默认分类

| 分类 | 默认接口 | 指令 |
|---|---|---|
| 随机小姐姐 | `https://v2.xxapi.cn/api/meinvpic` | `/mm`、`/小姐姐`、`/美女` |
| 白丝 | `https://v2.xxapi.cn/api/baisi` | `/白丝`、`/baisi` |
| 黑丝 | `https://v2.xxapi.cn/api/heisi` | `/黑丝`、`/heisi` |
| 二次元 | `https://v2.xxapi.cn/api/randomAcgPic?type=pc` | `/二次元`、`/acg` |
| JK | `https://v2.xxapi.cn/api/jk` | `/jk` |
| Pixiv | `https://api.lolicon.app/setu/v2` | `/pixiv [标签...]`、`/p站 [标签...]`、`/px [标签...]` |

## 指令

```text
/mm                         随机小姐姐
/小姐姐                     随机小姐姐
/美女                       随机小姐姐
/白丝                       白丝
/黑丝                       黑丝
/二次元                     二次元
/jk                         JK
/pixiv [标签1] [标签2] [标签3] Pixiv 随机图，默认非 R18

/meowpic get [分类] [标签...] 指定分类来一张，不填分类默认随机小姐姐
/meowpic baisi              白丝
/meowpic heisi              黑丝
/meowpic acg                二次元
/meowpic jk                 JK
/meowpic pixiv [标签...]      Pixiv 按标签随机

/meowpic setapi [分类] <URL> 设置你的个人分类 API
/meowpic setkey [分类] <Key> 设置 API Key
/meowpic clearkey [分类]     清除 API Key
/meowpic clear [分类]        清除个人配置
/meowpic status [分类]       查看当前配置
/meowpic help                查看指令
```

分类可写：

```text
meinv / 小姐姐 / 美女
baisi / 白丝
heisi / 黑丝
acg / 二次元 / 动漫
jk
pixiv / px / p站 / p站图 / pixiv非r18
```

## 配置项

| 字段 | 说明 |
|---|---|
| `api_meinv_url` | 随机小姐姐 API |
| `api_baisi_url` | 白丝 API |
| `api_heisi_url` | 黑丝 API |
| `api_acg_url` | 二次元 API |
| `api_jk_url` | JK API |
| `api_pixiv_url` | Pixiv API，默认使用 Lolicon v2 |
| `pixiv_r18` | Lolicon v2 的 `r18` 参数，默认 `0` 非 R18 |
| `pixiv_size` | Lolicon v2 的 `size` 参数，默认 `regular` |
| `pixiv_proxy` | Lolicon v2 的 `proxy` 参数，默认 `i.pixiv.re` |
| `pixiv_exclude_ai` | Lolicon v2 的 `excludeAI` 参数，默认开启 |
| `pixiv_default_tags` | `/pixiv` 不带标签时使用的默认标签 |
| `pixiv_aspect_ratio` | Lolicon v2 的 `aspectRatio` 参数 |
| `default_api_key` | 通用 API Key，仅当 URL 含 `{api_key}` 时替换 |
| `image_referer` | 图片下载 Referer，遇到 HTTP 403 时可填固定来源地址 |
| `request_timeout_seconds` | 请求超时秒数 |
| `rate_limit_enabled` | 是否启用用户限流 |
| `rate_limit_count` | 限流次数 |
| `rate_limit_window_seconds` | 限流窗口秒数 |
| `rate_limit_message` | 限流提示语 |

## 个人覆盖

覆盖白丝分类 API：

```text
/meowpic setapi 白丝 https://example.com/baisi
```

不写分类时覆盖随机小姐姐：

```text
/meowpic setapi https://example.com/meinv
```

带 Key 的 API 可以在 URL 里写 `{api_key}`：

```text
https://example.com/random?token={api_key}
```

然后设置 Key：

```text
/meowpic setkey 白丝 your_key
```

## 支持的 API 类型

- 直接返回图片：`Content-Type: image/*`
- 返回纯文本图片链接
- 返回 JSON，自动从 `url`、`img`、`image`、`pic`、`data`、`result` 等常见字段查找图片地址

Pixiv 默认接口来自 `https://api.lolicon.app/setu/v2`，使用 `r18=0` 过滤非 R18，并通过 `i.pixiv.re` 反代返回图片地址。

## Pixiv 标签

Pixiv 分类默认使用 Lolicon v2。直接发送：

```text
/pixiv
```

带标签发送：

```text
/pixiv 白丝
/pixiv 白丝|黑丝 初音ミク
/meowpic pixiv 初音ミク
/meowpic get pixiv 原神
```

最多支持 3 组标签；每组之间是 AND，每组内部可用 `|` 表示 OR。插件会自动拼成 Lolicon v2 的重复 `tag` 参数，并默认使用 `r18=0&num=1&size=regular&proxy=i.pixiv.re&excludeAI=true`。

如果 Pixiv 图片下载超时，可以把 `request_timeout_seconds` 调到 `30` 或 `60`，或在 `pixiv_proxy` 里换一个可用的 Pixiv 图片反代。插件会在 `i.pixiv.re` 与原始 `i.pximg.net` 地址之间自动兜底尝试。

## 限流

默认同一用户 60 秒内最多 3 次，第 4 次提示 `冲的太快了喵~`。可在配置里关闭或调整。
