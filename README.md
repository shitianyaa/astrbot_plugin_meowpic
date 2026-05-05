# 喵图姬

一个 AstrBot 随机图片插件。开箱即用,默认调用「无情API」抠脚大汉接口,也支持每个用户在聊天里设置自己的 API。

## 默认 API

```
https://free.wqwlkj.cn/wqwlapi/ks_2cy.php?type=image
```

- 请求方式:GET
- 返回格式:IMAGE(直接返回图片二进制)
- 无需 Key

如果想换其它 API 站点,在插件配置里改 `default_api_url` 即可。

## 指令

```text
/mm                         随机来一张
/小姐姐                     随机来一张
/美女                       随机来一张
/meowpic get                随机来一张
/meowpic setapi <API地址>    设置你的图片 API
/meowpic setkey <APIKey>     设置你的 API Key(只在 URL 含 {api_key} 时生效)
/meowpic clearkey            清除你的 API Key
/meowpic clear               清除你的全部个人配置
/meowpic status              查看当前配置
/meowpic help                查看指令
```

## 配置项

| 字段 | 说明 |
|---|---|
| `default_api_url` | 默认图片 API 地址,默认填好无情 API |
| `default_api_key` | 可选 API Key,仅当 URL 含 `{api_key}` 时替换 |
| `request_timeout_seconds` | 请求超时秒数 |
| `rate_limit_enabled` | 是否启用用户限流 |
| `rate_limit_count` | 限流次数 |
| `rate_limit_window_seconds` | 限流窗口秒数 |
| `rate_limit_message` | 限流提示语 |

## 带 Key 的 API

URL 里写 `{api_key}` 占位符即可:

```
https://example.com/random?token={api_key}
```

## 支持的 API 类型

- 直接返回图片(Content-Type: image/*) — 推荐,如默认的无情 API
- 返回纯文本图片链接 — 自动识别
- 返回 JSON — 自动从 `url`/`img`/`image`/`pic`/`data.url` 等常见字段查找图片地址

## 限流

默认同一用户 60 秒内最多 3 次,第 4 次提示 `冲的太快了喵~`。可在配置里关闭或调整。
