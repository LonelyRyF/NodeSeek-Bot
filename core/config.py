"""
配置管理 - 使用 pydantic-settings
"""
import logging
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, ValidationError

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """应用配置"""
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore'
    )
    
    # Telegram
    tg_bot_token: str = Field(alias='TG_BOT_TOKEN')
    tg_admin_uid: str = Field(alias='TG_ADMIN_UID')
    
    # NodeSeek
    nodeseek_cookies: str = Field(alias='NODESEEK_COOKIES')
    nodeseek_admin_uid: int = Field(alias='NODESEEK_ADMIN_UID')
    
    # Webhook
    webhook_url: str = Field(default='', alias='WEBHOOK_URL')
    port: int = Field(default=8080, alias='PORT')
    host: str = Field(default='0.0.0.0', alias='HOST')
    
    # 验证设置
    verification_ttl: int = Field(default=60*60*24*30, alias='VERIFICATION_TTL')  # 30天
    code_length: int = Field(default=6, alias='CODE_LENGTH')
    
    # 轮询设置
    poll_interval: int = Field(default=30, alias='POLL_INTERVAL')
    
    # 数据存储
    data_file: str = Field(default='/var/lib/tg-nodeseek-bot/data.json', alias='DATA_FILE')
    
    # 代理设置（可选）
    proxy_host: str = Field(default='', alias='PROXY_HOST')
    proxy_port: int = Field(default=0, alias='PROXY_PORT')
    
    def validate_config(self):
        """验证配置的有效性"""
        errors = []
        
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
        
        # 检查 NodeSeek Admin UID
        if not self.nodeseek_admin_uid or self.nodeseek_admin_uid <= 0:
            errors.append("NODESEEK_ADMIN_UID 未设置或无效")
        
        # 检查轮询间隔
        if self.poll_interval <= 0:
            errors.append("POLL_INTERVAL 必须大于 0")
        
        # 检查验证码长度
        if self.code_length < 4 or self.code_length > 20:
            errors.append("CODE_LENGTH 必须在 4-20 之间")
        
        if errors:
            error_msg = "\n".join(f"  ❌ {e}" for e in errors)
            raise ValueError(f"配置验证失败:\n{error_msg}")
        
        logger.info("✅ 配置验证通过")


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
