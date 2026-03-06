"""
从微信公众号后台抓取所有用户信息（使用浏览器 session cookies）

凭证通过环境变量传入，勿提交到仓库：
  WX_MP_TOKEN   - 公众号后台 token（从 URL 或接口获取）
  WX_MP_COOKIES - 浏览器复制的 Cookie 字符串
"""
import json
import os
import time
import random
import requests

# 配置：从环境变量读取，避免泄露
TOKEN = os.environ.get("WX_MP_TOKEN", "")
COOKIES = os.environ.get("WX_MP_COOKIES", "")

HEADERS = {
    "accept": "application/json, text/javascript, */*; q=0.01",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    "referer": f"https://mp.weixin.qq.com/cgi-bin/user_tag?action=get_all_data&lang=zh_CN&token={TOKEN}",
    "sec-ch-ua": '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    "x-requested-with": "XMLHttpRequest",
}

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.environ.get("WX_MP_OUTPUT_FILE", os.path.join(_SCRIPT_DIR, "config", "followees.json"))
PAGE_SIZE = 20


def parse_cookies(cookie_str: str) -> dict:
    """将 cookie 字符串解析为字典"""
    cookies = {}
    for item in cookie_str.split("; "):
        if "=" in item:
            key, value = item.split("=", 1)
            cookies[key.strip()] = value.strip()
    return cookies


def fetch_user_page(offset: int, cookies: dict) -> dict:
    """获取一页用户数据"""
    url = "https://mp.weixin.qq.com/cgi-bin/user_tag"
    params = {
        "action": "get_user_list",
        "groupid": -2,
        "begin_openid": -1,
        "begin_create_time": -1,
        "limit": PAGE_SIZE,
        "offset": offset,
        "backfoward": 1,
        "token": TOKEN,
        "lang": "zh_CN",
        "f": "json",
        "ajax": 1,
        "fingerprint": "f5d77e709676f239b9a26070274dec32",
        "random": str(random.random()),
    }
    response = requests.get(url, params=params, headers=HEADERS, cookies=cookies)
    response.raise_for_status()
    return response.json()


def transform_user(user: dict) -> dict:
    """将 API 返回的用户信息转换为模版格式"""
    return {
        "user_name": user.get("user_name", ""),
        "user_openid": user.get("user_openid", ""),
        "identity_type": user.get("identity_type", 0),
        "identity_open_id": user.get("identity_open_id", ""),
        "followed": False,
        "handled": False,
    }


def main():
    if not TOKEN or not COOKIES:
        print("请设置环境变量: WX_MP_TOKEN, WX_MP_COOKIES")
        print("  export WX_MP_TOKEN='你的token'")
        print("  export WX_MP_COOKIES='从浏览器复制的 Cookie 字符串'")
        return
    cookies = parse_cookies(COOKIES)
    all_users = []
    offset = 0

    print("开始抓取用户信息...")

    while True:
        print(f"  正在抓取 offset={offset} ...")
        data = fetch_user_page(offset, cookies)

        ret = data.get("base_resp", {}).get("ret", -1)
        if ret != 0:
            err_msg = data.get("base_resp", {}).get("err_msg", "未知错误")
            print(f"  API 返回错误: ret={ret}, err_msg={err_msg}")
            break

        user_list = data.get("user_list", {}).get("user_info_list", [])
        if not user_list:
            print("  没有更多用户了，抓取完成。")
            break

        for user in user_list:
            all_users.append(transform_user(user))

        print(f"  本页获取 {len(user_list)} 个用户，累计 {len(all_users)} 个")

        if len(user_list) < PAGE_SIZE:
            print("  最后一页，抓取完成。")
            break

        offset += PAGE_SIZE
        # 随机延迟 0.5~1.5 秒，避免触发频率限制
        delay = 0.5 + random.random()
        time.sleep(delay)

    print(f"\n共获取 {len(all_users)} 个用户")

    # 保存为 JSON
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_users, f, ensure_ascii=False, indent=2)

    print(f"已保存到: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
