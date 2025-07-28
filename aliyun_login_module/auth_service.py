# auth_service.py
# 用户认证服务模块

import logging
import pymysql
from sqlalchemy import create_engine, text
from database_config import (
    get_encrypted_db_config, 
    get_sqlalchemy_url,
    get_encrypted_sqlalchemy_url
)

class AuthService:
    """用户认证服务类"""
    
    def __init__(self, use_encryption=True):
        """
        初始化认证服务
        
        Args:
            use_encryption (bool): 是否使用加密的数据库配置
        """
        self.use_encryption = use_encryption
        
    def authenticate_user(self, username, password):
        """
        验证用户登录凭据
        
        Args:
            username (str): 用户名
            password (str): 密码
            
        Returns:
            bool: 验证成功返回True，失败返回False
            
        Raises:
            Exception: 数据库连接或查询错误
        """
        if not username or not password:
            logging.warning("用户名或密码为空")
            return False
            
        try:
            if self.use_encryption:
                return self._authenticate_with_pymysql(username, password)
            else:
                return self._authenticate_with_sqlalchemy(username, password)
        except Exception as e:
            logging.error(f"用户认证失败: {e}")
            raise
    
    def _authenticate_with_pymysql(self, username, password):
        """
        使用PyMySQL和加密配置进行认证
        
        Args:
            username (str): 用户名
            password (str): 密码
            
        Returns:
            bool: 认证结果
        """
        config = get_encrypted_db_config()
        
        connection = pymysql.connect(
            host=config['host'],
            port=config['port'],
            user=config['user'],
            password=config['password'],
            database=config['database'],
            charset=config['charset'],
            cursorclass=pymysql.cursors.DictCursor
        )
        
        try:
            with connection.cursor() as cursor:
                sql = "SELECT * FROM `id-pw` WHERE ID=%s AND PW=%s"
                cursor.execute(sql, (username, password))
                result = cursor.fetchone()
                
                if result:
                    logging.info(f"用户 {username} 登录成功")
                    return True
                else:
                    logging.warning(f"用户 {username} 登录失败：账号或密码错误")
                    return False
        finally:
            connection.close()
    
    def _authenticate_with_sqlalchemy(self, username, password):
        """
        使用SQLAlchemy进行认证
        
        Args:
            username (str): 用户名
            password (str): 密码
            
        Returns:
            bool: 认证结果
        """
        engine = create_engine(get_sqlalchemy_url())
        
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT * FROM `id-pw` WHERE ID=:username AND PW=:password"),
                {"username": username, "password": password}
            ).fetchone()
            
            if result:
                logging.info(f"用户 {username} 登录成功")
                return True
            else:
                logging.warning(f"用户 {username} 登录失败：账号或密码错误")
                return False
    
    def get_user_info(self, username):
        """
        获取用户信息
        
        Args:
            username (str): 用户名
            
        Returns:
            dict: 用户信息字典，如果用户不存在返回None
        """
        try:
            config = get_encrypted_db_config()
            
            connection = pymysql.connect(
                host=config['host'],
                port=config['port'],
                user=config['user'],
                password=config['password'],
                database=config['database'],
                charset=config['charset'],
                cursorclass=pymysql.cursors.DictCursor
            )
            
            try:
                with connection.cursor() as cursor:
                    sql = "SELECT * FROM `id-pw` WHERE ID=%s"
                    cursor.execute(sql, (username,))
                    result = cursor.fetchone()
                    return result
            finally:
                connection.close()
                
        except Exception as e:
            logging.error(f"获取用户信息失败: {e}")
            return None 