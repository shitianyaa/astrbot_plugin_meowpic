from __future__ import annotations


KV_USER_CONFIGS = "user_configs"
LOG_PREFIX = "[MeowPic]"
DEFAULT_LIMIT_MESSAGE = "冲的太快了喵~"
DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_CATEGORY = "meinv"
PIXIV_LOLICON_API_URL = "https://api.lolicon.app/setu/v2"
PIXIV_LEGACY_MOSSIA_API_URL = (
    "https://api.mossia.top/duckMo?num=1&r18Type=0&proxy=i.pixiv.re"
)
PIXIV_ALLOWED_SIZES = {"original", "regular", "small", "thumb", "mini"}
PIXIV_MAX_TAG_GROUPS = 3
FALSE_STRINGS = {"", "0", "false", "none", "null", "off", "no"}
IMAGE_CATEGORIES = {
    "meinv": {
        "label": "随机小姐姐",
        "config_key": "api_meinv_url",
        "default_url": "https://v2.xxapi.cn/api/meinvpic",
    },
    "baisi": {
        "label": "白丝",
        "config_key": "api_baisi_url",
        "default_url": "https://v2.xxapi.cn/api/baisi",
    },
    "heisi": {
        "label": "黑丝",
        "config_key": "api_heisi_url",
        "default_url": "https://v2.xxapi.cn/api/heisi",
    },
    "acg": {
        "label": "二次元",
        "config_key": "api_acg_url",
        "default_url": "https://v2.xxapi.cn/api/randomAcgPic?type=pc",
    },
    "jk": {
        "label": "JK",
        "config_key": "api_jk_url",
        "default_url": "https://v2.xxapi.cn/api/jk",
    },
    "pixiv": {
        "label": "Pixiv",
        "config_key": "api_pixiv_url",
        "default_url": PIXIV_LOLICON_API_URL,
    },
}
CATEGORY_ALIASES = {
    "meinv": "meinv",
    "mm": "meinv",
    "meizi": "meinv",
    "小姐姐": "meinv",
    "美女": "meinv",
    "随机小姐姐": "meinv",
    "baisi": "baisi",
    "bs": "baisi",
    "白丝": "baisi",
    "heisi": "heisi",
    "hs": "heisi",
    "黑丝": "heisi",
    "acg": "acg",
    "二次元": "acg",
    "动漫": "acg",
    "jk": "jk",
    "pixiv": "pixiv",
    "px": "pixiv",
    "p站": "pixiv",
    "p站图": "pixiv",
    "pixiv非r18": "pixiv",
}
DEFAULT_API_URL = IMAGE_CATEGORIES[DEFAULT_CATEGORY]["default_url"]
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
IMAGE_SUFFIX_BY_CONTENT_TYPE = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
}
PREFERRED_IMAGE_KEYS = {
    "url",
    "urls",
    "img",
    "imgs",
    "image",
    "images",
    "pic",
    "pics",
    "picture",
    "pictures",
    "file",
    "files",
    "data",
    "imgurl",
    "image_url",
    "imageurl",
    "link",
    "result",
    "src",
    "download_url",
}
SECRET_QUERY_KEYS = {"key", "apikey", "api_key", "token", "access_token", "auth"}
