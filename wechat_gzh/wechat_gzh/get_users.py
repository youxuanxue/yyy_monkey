"""
获取微信公众号关注用户信息

使用方法：
    uv run python -m wechat_gzh.get_users
"""
import json
import os
import sys

from .api import WeChatAPI


def main():
    """主函数"""
    try:
        # 初始化微信 API 客户端
        print("正在初始化微信 API 客户端...")
        api = WeChatAPI()
        
        # 获取所有用户信息
        print("正在获取所有关注用户信息...")
        user_info_list = api.get_all_user_info()
        
        # 打印统计信息
        print(f"\n共获取到 {len(user_info_list)} 个关注用户\n")
        
        # 打印用户信息
        print("=" * 80)
        print("用户信息列表：")
        print("=" * 80)
        
        for idx, user in enumerate(user_info_list, 1):
            print(f"\n用户 {idx}:")
            print(f"  昵称: {user.get('nickname', '未知')}")
            print(f"  OpenID: {user.get('openid', '未知')}")
            print(f"  性别: {['未知', '男', '女'][user.get('sex', 0)]}")
            print(f"  城市: {user.get('city', '未知')}")
            print(f"  省份: {user.get('province', '未知')}")
            print(f"  国家: {user.get('country', '未知')}")
            print(f"  头像: {user.get('headimgurl', '未知')}")
            print(f"  关注时间: {user.get('subscribe_time', '未知')}")
            if user.get('subscribe_time'):
                from datetime import datetime
                subscribe_time = datetime.fromtimestamp(user.get('subscribe_time'))
                print(f"  关注时间（格式化）: {subscribe_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 确保输出目录存在
        output_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 保存到 JSON 文件
        output_file = os.path.join(output_dir, "users_info.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(user_info_list, f, ensure_ascii=False, indent=2)
        
        print(f"\n\n用户信息已保存到文件: {output_file}")
        
        # 保存用户 openid 列表到文本文件
        openid_file = os.path.join(output_dir, "users_openid.txt")
        with open(openid_file, "w", encoding="utf-8") as f:
            for user in user_info_list:
                f.write(f"{user.get('openid', '')}\n")
        
        print(f"用户 OpenID 列表已保存到文件: {openid_file}")
        
    except Exception as e:
        print(f"错误: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
