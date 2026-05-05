# 喵图姬

一个 AstrBot 随机图片插件。支持全局默认 API，也支持每个用户在聊天里设置自己的 API 地址和 API Key。

插件不提供独立网页后台；全局参数直接在 AstrBot 的插件配置里填写。

## 功能

- `/mm`、`/小姐姐`、`/美女` 随机返回一张图片
- 用户可自定义 API 地址：`/meowpic setapi <API地址>`
- 用户可自定义 API Key：`/meowpic setkey <APIKey>`
- 支持直接返回图片的 API
- 支持 JSON API，自动从 `url`、`img`、`image`、`pic`、`data.url` 等常见字段里找图片地址
- 同一用户默认 60 秒内最多请求 3 次，第四次提示：`冲的太快了喵~`

## 指令

```text
/mm
/小姐姐
/meowpic get
/meowpic setapi <API地址>
/meowpic setkey <APIKey>
/meowpic clearkey
/meowpic clear
/meowpic status
/meowpic help
```

## API Key 用法

在 AstrBot 插件配置里常用的是这几个字段：

```text
default_api_url
default_api_key
api_key_query_name
api_key_header
api_key_header_prefix
image_url_path
```

如果 API 地址中包含 `{api_key}`，插件会直接替换：

```text
https://example.com/random?token={api_key}
```

如果没有 `{api_key}`，并且 AstrBot 插件配置里没有设置 `api_key_header`，插件会按 `api_key_query_name` 追加查询参数。默认参数名是 `key`。

如果 API 需要请求头，把 `api_key_header` 设置为对应 header，例如 `Authorization` 或 `X-API-Key`。需要 `Bearer` 这类前缀时，再设置 `api_key_header_prefix`。

## JSON 响应

默认会自动查找常见图片字段。如果你的 API 返回格式比较特殊，可以在 AstrBot 插件配置里设置 `image_url_path`：

```text
data.url
data.img
data[0].url
```

## 限流

默认配置：

```text
rate_limit_count = 3
rate_limit_window_seconds = 60
rate_limit_message = 冲的太快了喵~
```

也就是同一用户 60 秒内第 4 次请求会被拦截。
