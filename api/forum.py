# ███╗   ██╗ ██████╗ ██████╗ ███████╗███████╗███████╗███████╗██╗  ██╗     ██████╗  ██████╗ ████████╗
# ████╗  ██║██╔═══██╗██╔══██╗██╔════╝██╔════╝██╔════╝██╔════╝██║ ██╔╝     ██╔══██╗██╔═══██╗╚══██╔══╝
# ██╔██╗ ██║██║   ██║██║  ██║█████╗  ███████╗█████╗  █████╗  █████╔╝█████╗██████╔╝██║   ██║   ██║
# ██║╚██╗██║██║   ██║██║  ██║██╔══╝  ╚════██║██╔══╝  ██╔══╝  ██╔═██╗╚════╝██╔══██╗██║   ██║   ██║
# ██║ ╚████║╚██████╔╝██████╔╝███████╗███████║███████╗███████╗██║  ██╗     ██████╔╝╚██████╔╝   ██║
# ╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚══════╝╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝     ╚═════╝  ╚═════╝    ╚═╝

import base64
import json
from typing import List, Dict, Any, Optional

from loguru import logger
from curl_cffi import requests

from core.models import ForumMessage


class ForumAPI:
    """通用论坛 API 客户端"""

    def __init__(self, platform: str, base_url: str, cookies: str,
                 proxy_host: str = '', proxy_port: int = 0):
        self.platform = platform
        self.BASE_URL = base_url.rstrip('/')
        self.session = requests.Session()

        self._parse_cookies(cookies)

        self.headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Origin': self.BASE_URL,
            'Referer': self.BASE_URL + '/',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
        }

        self.proxies = None
        if proxy_host and proxy_port:
            self.proxies = {
                'http': f'socks5://{proxy_host}:{proxy_port}',
                'https': f'socks5://{proxy_host}:{proxy_port}',
            }
            logger.info(f"[{platform}] 使用代理: {proxy_host}:{proxy_port}")
        else:
            logger.info(f"[{platform}] 直连")

    def _parse_cookies(self, cookie_str: str):
        self.cookies = {}
        for item in cookie_str.split(';'):
            item = item.strip()
            if '=' in item:
                key, value = item.split('=', 1)
                self.cookies[key.strip()] = value.strip()

    def _request(self, method: str, endpoint: str,
                 override_cookies: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        url = f"{self.BASE_URL}{endpoint}"
        response = None
        try:
            request_kwargs = {
                'headers': self.headers,
                'cookies': override_cookies if override_cookies is not None else self.cookies,
                'impersonate': 'chrome142',
                **kwargs
            }
            if self.proxies:
                request_kwargs['proxies'] = self.proxies

            response = self.session.request(method, url, **request_kwargs)
            try:
                data = response.json()
            except Exception:
                response.raise_for_status()
                raise
            if 'success' in data:
                return data
            response.raise_for_status()
            return data
        except Exception as e:
            logger.error(f"[{self.platform}] 请求失败 {endpoint}: {e}")
            if response is not None:
                try:
                    response_text = response.text[:500]
                except Exception:
                    response_text = str(response.content[:500])
                return {
                    'success': False,
                    'error': str(e),
                    'status_code': response.status_code,
                    'response_text': response_text,
                    'endpoint': endpoint,
                    'method': method,
                }
            return {'success': False, 'error': str(e), 'endpoint': endpoint, 'method': method}

    def get_messages(self) -> List[Dict]:
        result = self._request('GET', '/api/notification/message/list')
        if result.get('success'):
            messages = result.get('msgArray', [])
            logger.info(f"[{self.platform}] 获取到 {len(messages)} 条私信")
            return messages
        logger.error(f"[{self.platform}] 获取私信列表失败: {result.get('error')}")
        return []

    def get_message_detail(self, user_id: int) -> List[ForumMessage]:
        result = self._request('GET', f'/api/notification/message/with/{user_id}')
        if result.get('success'):
            return [ForumMessage(**m) for m in result.get('msgArray', [])]
        return []

    def mark_viewed(self, message_ids: List[int]) -> bool:
        result = self._request('POST', '/api/notification/message/markViewed',
                               json={'messages': message_ids})
        return result.get('success', False)

    def checkin(self, random: bool = False) -> Dict[str, Any]:
        return self._request('POST', f'/api/attendance?random={str(random).lower()}', json={})

    def get_floor_data(self, post_id: str, time: int) -> Dict[str, Any]:
        return self._request('GET', f'/api/content/floor-data?postId={post_id}&time={time}')

    def check_cookies(self) -> bool:
        """验证 cookies 是否有效（USER NOT FOUND 才是真正无效）"""
        result = self._request('GET', '/api/account/telegram')
        # {"message":"USER NOT FOUND","status":404,"success":false} 才是无效
        if result.get('message') == 'USER NOT FOUND':
            logger.warning(f"[{self.platform}] cookies 无效")
            return False
        return True

    def get_self_uid(self) -> Optional[int]:
        """通过解析首页 temp-script 自动获取当前登录账号的 member_id"""
        try:
            # 首页导航用浏览器页面请求头，不能用 API 的 cors 头
            nav_headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Referer': self.BASE_URL + '/',
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'none',
                'sec-fetch-user': '?1',
                'Upgrade-Insecure-Requests': '1',
            }
            resp = self.session.get(
                self.BASE_URL,
                headers=nav_headers,
                cookies=self.cookies,
                impersonate='chrome142',
                proxies=self.proxies or None,
                timeout=15,
            )
            resp.raise_for_status()
            html = resp.text

            start = html.find('id="temp-script"')
            if start == -1:
                logger.warning(f"[{self.platform}] 未找到 temp-script，cookies 可能已失效")
                return None
            start = html.find('>', start) + 1
            end = html.find('</script>', start)
            b64_text = html[start:end].strip()
            # 修正 base64 padding
            b64_text += '=' * (-len(b64_text) % 4)

            data = json.loads(base64.b64decode(b64_text).decode('utf-8'))
            user = data.get('user')
            if not user:
                logger.warning(f"[{self.platform}] temp-script 中 user 为空，cookies 可能未生效。"
                                f"data keys: {list(data.keys())}")
                return None
            uid = user['member_id']
            logger.info(f"[{self.platform}] 自动检测 UID: {uid} ({user['member_name']})")
            return uid
        except Exception as e:
            logger.error(f"[{self.platform}] 自动获取 UID 失败: {e}")
            return None

    def close(self):
        self.session.close()


# 向后兼容别名
NodeSeekAPI = ForumAPI
