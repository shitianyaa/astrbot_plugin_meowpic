# 喵图姬

<div align="center">
  <img src="https://count.getloli.com/@astrbot-plugin-meowpic?name=astrbot-plugin-meowpic&theme=booru-jaypee&padding=6&offset=0&align=top&scale=1&pixelated=1&darkmode=auto" alt="count" />
</div>

AstrBot 随机图片插件，内置多个图片分类，支持 Pixiv 标签、短时限流和图片撤回。

## 默认分类

| 分类 | 默认接口 | 指令 |
|---|---|---|
| 随机小姐姐 | `https://v2.xxapi.cn/api/meinvpic` | `/mm`、`/小姐姐`、`/美女` |
| 白丝 | `https://v2.xxapi.cn/api/baisi` | `/白丝`、`/baisi` |
| 黑丝 | `https://v2.xxapi.cn/api/heisi` | `/黑丝`、`/heisi` |
| 二次元 | `https://v2.xxapi.cn/api/randomAcgPic?type=pc` | `/二次元`、`/acg` |
| JK | `https://v2.xxapi.cn/api/jk` | `/jk` |
| Pixiv | `https://api.lolicon.app/setu/v2` | `/px [标签...]` |

## 指令

```text
/mm                         随机小姐姐
/小姐姐                     随机小姐姐
/美女                       随机小姐姐
/白丝                       白丝
/黑丝                       黑丝
/二次元                     二次元
/jk                         JK
/px [标签1] [标签2] [标签3] Pixiv 随机图，默认非 R18

/meowpic help                查看指令

hentai                      撤回最近 2 分钟内机器人发出的上一张图片
```

## 说明

- `/px` 最多支持 3 组标签；每组之间是 AND，每组内部可用 `|` 表示 OR。
- `hentai` 默认只有管理员或白名单用户可用，且仅支持 `aiocqhttp` / OneBot。
- API、Pixiv 参数、限流和撤回权限都可以在 AstrBot 插件配置里调整。

## 致谢

感谢小小 API 和 [Tsuk1ko/lolicon-api-docs](https://github.com/Tsuk1ko/lolicon-api-docs) 提供的免费 API 接口。
