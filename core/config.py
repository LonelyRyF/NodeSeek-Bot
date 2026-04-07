# ███╗   ██╗ ██████╗ ██████╗ ███████╗███████╗███████╗███████╗██╗  ██╗     ██████╗  ██████╗ ████████╗
# ████╗  ██║██╔═══██╗██╔══██╗██╔════╝██╔════╝██╔════╝██╔════╝██║ ██╔╝     ██╔══██╗██╔═══██╗╚══██╔══╝
# ██╔██╗ ██║██║   ██║██║  ██║█████╗  ███████╗█████╗  █████╗  █████╔╝█████╗██████╔╝██║   ██║   ██║
# ██║╚██╗██║██║   ██║██║  ██║██╔══╝  ╚════██║██╔══╝  ██╔══╝  ██╔═██╗╚════╝██╔══██╗██║   ██║   ██║
# ██║ ╚████║╚██████╔╝██████╔╝███████╗███████║███████╗███████╗██║  ██╗     ██████╔╝╚██████╔╝   ██║
# ╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚══════╝╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝     ╚═════╝  ╚═════╝    ╚═╝

from loguru import logger
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, ValidationError


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
        frozen=False  # 允许运行时修改（用于自动检测 UID）
    )

    # Telegram
    tg_bot_token: str = Field(alias='TG_BOT_TOKEN')
    tg_admin_uid: str = Field(alias='TG_ADMIN_UID')

    # NodeSeek
    nodeseek_cookies: str = Field(alias='NODESEEK_COOKIES')

    # DeepFlood（可选，留空则不启用）
    deepflood_cookies: str = Field(default='', alias='DEEPFLOOD_COOKIES')
    
    # Webhook
    webhook_url: str = Field(default='', alias='WEBHOOK_URL')
    port: int = Field(default=8080, alias='PORT')
    host: str = Field(default='0.0.0.0', alias='HOST')
    
    # 验证设置
    code_length: int = Field(default=6, alias='CODE_LENGTH')
    
    # 轮询设置
    poll_interval: int = Field(default=30, alias='POLL_INTERVAL')

    # RSS 设置
    rss_url: str = 'https://rss.nodeseek.com'
    rss_poll_interval: int = Field(default=60, alias='RSS_POLL_INTERVAL')
    rss_http_timeout: int = Field(default=15, alias='RSS_HTTP_TIMEOUT')
    rss_max_entries: int = Field(default=50, alias='RSS_MAX_ENTRIES')
    rss_disable_web_page_preview: bool = Field(default=True, alias='RSS_DISABLE_WEB_PAGE_PREVIEW')
    rss_history_limit: int = Field(default=200, alias='RSS_HISTORY_LIMIT')
    
    # 代理设置（可选）
    proxy_host: str = Field(default='', alias='PROXY_HOST')
    proxy_port: int = Field(default=0, alias='PROXY_PORT')

    # 日志设置
    log_level: str = Field(default='INFO', alias='LOG_LEVEL')

    # 抽奖 Webhook 认证密钥
    lucky_auth_key: str = Field(default='', alias='LUCKY_AUTH_KEY')
    
    def validate_config(self):
        """验证配置的有效性"""
        errors = []
        valid_log_levels = {'TRACE', 'DEBUG', 'INFO', 'SUCCESS', 'WARNING', 'ERROR', 'CRITICAL'}
        
        # 检查 Telegram Token
        if not self.tg_bot_token or self.tg_bot_token.startswith('your_'):
            errors.append("TG_BOT_TOKEN 未设置或为占位符")
        
        # 检查 Admin UID
        if not self.tg_admin_uid or self.tg_admin_uid.startswith('your_'):
            errors.append("TG_ADMIN_UID 未设置或为占位符")
        else:
            try:
                int(self.tg_admin_uid)
            except ValueError:
                errors.append("TG_ADMIN_UID 必须是数字")
        
        # 检查 NodeSeek Cookies
        if not self.nodeseek_cookies or self.nodeseek_cookies.startswith('your_'):
            errors.append("NODESEEK_COOKIES 未设置或为占位符")
        
        # 检查轮询间隔
        if self.poll_interval <= 0:
            errors.append("POLL_INTERVAL 必须大于 0")

        if self.rss_poll_interval <= 0:
            errors.append("RSS_POLL_INTERVAL 必须大于 0")

        if self.rss_http_timeout <= 0:
            errors.append("RSS_HTTP_TIMEOUT 必须大于 0")

        if self.rss_max_entries <= 0:
            errors.append("RSS_MAX_ENTRIES 必须大于 0")

        if self.rss_history_limit <= 0:
            errors.append("RSS_HISTORY_LIMIT 必须大于 0")

        if self.log_level.upper() not in valid_log_levels:
            errors.append("LOG_LEVEL 必须是 TRACE/DEBUG/INFO/SUCCESS/WARNING/ERROR/CRITICAL 之一")
        
        # 检查验证码长度
        if self.code_length < 4 or self.code_length > 20:
            errors.append("CODE_LENGTH 必须在 4-20 之间")
        
        if errors:
            error_msg = "\n".join(f"  ❌ {e}" for e in errors)
            raise ValueError(f"配置验证失败:\n{error_msg}")



def load_settings() -> Settings:
    """加载并验证配置"""
    try:
        config = Settings()
        config.validate_config()
        return config
    except ValidationError as e:
        logger.error("配置验证失败:")
        for error in e.errors():
            field = error['loc'][0]
            msg = error['msg']
            logger.error(f"  ❌ {field}: {msg}")
        raise
    except ValueError as e:
        logger.error(str(e))
        raise
    except Exception as e:
        logger.error(f"配置加载失败: {e}")
        raise


# 全局配置实例
try:
    settings = load_settings()
except Exception as e:
    logger.error(f"无法启动 Bot: {e}")
    raise
