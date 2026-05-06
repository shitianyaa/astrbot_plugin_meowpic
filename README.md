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
| Pixiv 非 R18 | `https://api.mossia.top/duckMo?num=1&r18Type=0&proxy=i.pixiv.re` | `/pixiv`、`/p站`、`/px` |

## 指令

```text
/mm                         随机小姐姐
/小姐姐                     随机小姐姐
/美女                       随机小姐姐
/白丝                       白丝
/黑丝                       黑丝
/二次元                     二次元
/jk                         JK
/pixiv                      Pixiv 非 R18

/meowpic get [分类]          指定分类来一张，不填分类默认随机小姐姐
/meowpic baisi              白丝
/meowpic heisi              黑丝
/meowpic acg                二次元
/meowpic jk                 JK
/meowpic pixiv              Pixiv 非 R18

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
| `api_pixiv_url` | Pixiv 非 R18 API，默认带 `r18Type=0` |
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

Pixiv 默认接口来自 `https://api.mossia.top/duckMo`，使用 `r18Type=0` 过滤非 R18，并通过 `i.pixiv.re` 反代返回图片地址。

## 限流

默认同一用户 60 秒内最多 3 次，第 4 次提示 `冲的太快了喵~`。可在配置里关闭或调整。
