"""
微信公众号 API 客户端
用于获取公众号关注用户信息
https://developers.weixin.qq.com/console/product/mp/wx1b21efa4bc1097a1?tab1=basicInfo&tab2=dev
"""
import os
import requests
from typing import Dict, List, Optional
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class WeChatAPI:
    """微信公众号 API 客户端类"""
    
    BASE_URL = "https://api.weixin.qq.com/cgi-bin"
    
    def __init__(self, app_id: Optional[str] = None, app_secret: Optional[str] = None):
        """
        初始化微信 API 客户端
        
        Args:
            app_id: 微信公众号 AppID，如果不提供则从环境变量读取
            app_secret: 微信公众号 AppSecret，如果不提供则从环境变量读取
        """
        self.app_id = app_id or os.getenv("WX_APP_ID")
        self.app_secret = app_secret or os.getenv("WX_APP_SECRET")
        
        if not self.app_id or not self.app_secret:
            raise ValueError("请设置 WX_APP_ID 和 WX_APP_SECRET 环境变量")
        
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[float] = None
    
    def get_access_token(self) -> str:
        """
        获取 access_token
        
        Returns:
            access_token 字符串
            
        Raises:
            Exception: 当获取 token 失败时抛出异常
        """
        url = f"{self.BASE_URL}/token"
        params = {
            "grant_type": "client_credential",
            "appid": self.app_id,
            "secret": self.app_secret
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if "access_token" in data:
            self._access_token = data["access_token"]
            # access_token 有效期为 7200 秒，这里设置提前 5 分钟过期
            self._token_expires_at = data.get("expires_in", 7200) - 300
            return self._access_token
        else:
            error_msg = data.get("errmsg", "未知错误")
            error_code = data.get("errcode", -1)
            error_hint = self._get_error_hint(error_code)
            raise Exception(f"获取 access_token 失败: {error_code} - {error_msg}\n{error_hint}")
    
    def get_user_list(self, next_openid: Optional[str] = None) -> Dict:
        """
        获取用户列表
        
        Args:
            next_openid: 第一个拉取的 OPENID，不填默认从头开始拉取
            
        Returns:
            包含用户列表的字典，格式：
            {
                "total": 总用户数,
                "count": 本次拉取的用户数,
                "data": {"openid": [...]},
                "next_openid": 下一个拉取的 OPENID
            }
        """
        if not self._access_token:
            self.get_access_token()
        
        url = f"{self.BASE_URL}/user/get"
        params = {
            "access_token": self._access_token
        }
        
        if next_openid:
            params["next_openid"] = next_openid
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if "errcode" in data and data["errcode"] != 0:
            error_msg = data.get("errmsg", "未知错误")
            error_code = data.get("errcode", -1)
            error_hint = self._get_error_hint(error_code)
            raise Exception(f"获取用户列表失败: {error_code} - {error_msg}\n{error_hint}")
        
        return data
    
    def get_user_info(self, openid: str, lang: str = "zh_CN") -> Dict:
        """
        获取单个用户信息
        
        Args:
            openid: 用户的 openid
            lang: 返回国家地区语言版本，zh_CN 简体，zh_TW 繁体，en 英语
            
        Returns:
            用户信息字典
        """
        if not self._access_token:
            self.get_access_token()
        
        url = f"{self.BASE_URL}/user/info"
        params = {
            "access_token": self._access_token,
            "openid": openid,
            "lang": lang
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if "errcode" in data and data["errcode"] != 0:
            error_msg = data.get("errmsg", "未知错误")
            error_code = data.get("errcode", -1)
            error_hint = self._get_error_hint(error_code)
            raise Exception(f"获取用户信息失败: {error_code} - {error_msg}\n{error_hint}")
        
        return data
    
    def batch_get_user_info(self, openids: List[str], lang: str = "zh_CN") -> List[Dict]:
        """
        批量获取用户信息（最多 100 个）
        
        Args:
            openids: 用户 openid 列表，最多 100 个
            lang: 返回国家地区语言版本，zh_CN 简体，zh_TW 繁体，en 英语
            
        Returns:
            用户信息列表
        """
        if not self._access_token:
            self.get_access_token()
        
        if len(openids) > 100:
            raise ValueError("一次最多只能获取 100 个用户信息")
        
        url = f"{self.BASE_URL}/user/info/batchget"
        params = {
            "access_token": self._access_token
        }
        
        user_list = [{"openid": openid, "lang": lang} for openid in openids]
        payload = {
            "user_list": user_list
        }
        
        response = requests.post(url, params=params, json=payload)
        data = response.json()
        
        if "errcode" in data and data["errcode"] != 0:
            error_msg = data.get("errmsg", "未知错误")
            error_code = data.get("errcode", -1)
            error_hint = self._get_error_hint(error_code)
            raise Exception(f"批量获取用户信息失败: {error_code} - {error_msg}\n{error_hint}")
        
        return data.get("user_info_list", [])
    
    def get_all_users(self) -> List[str]:
        """
        获取所有用户的 openid 列表
        
        Returns:
            所有用户的 openid 列表
        """
        all_openids = []
        next_openid = None
        
        while True:
            result = self.get_user_list(next_openid)
            openids = result.get("data", {}).get("openid", [])
            all_openids.extend(openids)
            
            next_openid = result.get("next_openid")
            # 如果没有 next_openid 或数量为 0，说明已经获取完所有用户
            if not next_openid or len(openids) == 0:
                break
        
        return all_openids
    
    def get_all_user_info(self, lang: str = "zh_CN") -> List[Dict]:
        """
        获取所有用户的详细信息
        
        Args:
            lang: 返回国家地区语言版本，zh_CN 简体，zh_TW 繁体，en 英语
            
        Returns:
            所有用户的详细信息列表
        """
        all_openids = self.get_all_users()
        all_user_info = []
        
        # 批量获取，每次最多 100 个
        batch_size = 100
        for i in range(0, len(all_openids), batch_size):
            batch_openids = all_openids[i:i + batch_size]
            batch_info = self.batch_get_user_info(batch_openids, lang)
            all_user_info.extend(batch_info)
        
        return all_user_info
    
    @staticmethod
    def _get_error_hint(error_code: int) -> str:
        """
        根据错误码返回错误提示信息
        
        Args:
            error_code: 微信 API 错误码
            
        Returns:
            错误提示信息
        """
        error_hints = {
            40001: "access_token 无效或已过期，请检查 AppID 和 AppSecret 是否正确",
            40014: "不合法的 access_token，请重新获取",
            40164: "IP 地址不在白名单中，请在微信公众平台后台添加服务器 IP 地址到白名单",
            48001: "API 未授权，可能的原因：\n"
                   "  1. 公众号类型不支持该接口（订阅号不支持获取用户列表，需要服务号）\n"
                   "  2. 需要在微信公众平台后台开启相关接口权限\n"
                   "  3. 请确认公众号已通过微信认证（认证服务号）\n"
                   "  4. 检查是否在微信公众平台后台 -> 开发 -> 接口权限中开启了'用户管理'相关权限",
            50001: "用户未授权该 API",
            61024: "API 接口被封禁，请检查公众号状态",
        }
        
        hint = error_hints.get(error_code, "")
        if hint:
            return f"提示: {hint}"
        return ""
