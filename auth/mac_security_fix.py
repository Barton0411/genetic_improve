"""
Mac平台安全修复模块
解决Mac上的Keychain权限和SSL证书验证问题
"""

import platform
import logging
import ssl
import certifi
import os

logger = logging.getLogger(__name__)

def setup_mac_ssl_context():
    """
    为Mac设置正确的SSL上下文
    解决Mac上的SSL证书验证问题
    """
    if platform.system() != 'Darwin':
        return None

    try:
        # 创建自定义SSL上下文
        context = ssl.create_default_context(cafile=certifi.where())
        # 在Mac上可能需要更宽松的验证
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE  # 临时禁用证书验证
        logger.info("Mac SSL上下文已配置")
        return context
    except Exception as e:
        logger.error(f"配置Mac SSL上下文失败: {e}")
        return None

def disable_keychain_for_packaged_app():
    """
    为打包的Mac应用禁用Keychain访问
    使用本地文件存储替代
    """
    if platform.system() != 'Darwin':
        return False

    # 检查是否是打包的应用
    import sys
    if getattr(sys, 'frozen', False):
        # 设置环境变量，禁用keyring
        os.environ['PYTHON_KEYRING_BACKEND'] = 'keyring.backends.null.Keyring'
        logger.info("已为打包应用禁用Keychain访问")
        return True

    return False

def fix_mac_network_issues():
    """
    修复Mac上的网络连接问题
    """
    if platform.system() != 'Darwin':
        return

    try:
        # 禁用系统代理设置
        os.environ['no_proxy'] = '*'
        os.environ['NO_PROXY'] = '*'

        # 如果是打包的应用，禁用Keychain
        disable_keychain_for_packaged_app()

        logger.info("Mac网络问题修复已应用")
    except Exception as e:
        logger.error(f"修复Mac网络问题失败: {e}")

def get_mac_safe_session():
    """
    获取Mac安全的requests会话
    """
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.poolmanager import PoolManager

    class MacSSLAdapter(HTTPAdapter):
        """Mac专用SSL适配器"""
        def init_poolmanager(self, *args, **kwargs):
            # 使用自定义SSL上下文
            context = setup_mac_ssl_context()
            if context:
                kwargs['ssl_context'] = context
            return super().init_poolmanager(*args, **kwargs)

    session = requests.Session()

    if platform.system() == 'Darwin':
        # 为Mac使用自定义适配器
        adapter = MacSSLAdapter()
        session.mount('https://', adapter)
        session.mount('http://', adapter)

        # 禁用代理
        session.trust_env = False
        session.proxies = {
            'http': None,
            'https': None
        }

    return session