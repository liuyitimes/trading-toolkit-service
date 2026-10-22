# -*- coding: utf-8 -*-
"""数据库连接串规范化。

背景：SQLAlchemy 2.1 起，``postgresql://`` 的默认 DBAPI 由 psycopg2 改为 psycopg（v3）。
本服务镜像只安装 ``psycopg2-binary``，托管平台（Render）注入的 ``DATABASE_URL`` 又是
不带驱动名的 ``postgresql://`` 形式，因此升级依赖后容器启动即报
``ModuleNotFoundError: No module named 'psycopg'``。

解决方式：所有连接串在进入 ``create_engine`` 或 Alembic 之前，统一显式补齐驱动名，
不再依赖 SQLAlchemy 的默认值。这样 SQLAlchemy 主版本升级不会改变运行期驱动。
"""

#: 本项目实际随镜像发布的 PostgreSQL 驱动。
SUPPORTED_POSTGRES_DRIVER = 'psycopg2'

#: 协议别名到规范形式的映射。``postgres`` 是 Render / Heroku 历史别名。
_SCHEME_ALIASES = {
    'postgres': 'postgresql',
}


def normalize_database_url(url):
    """返回带上显式驱动名的连接串。

    - ``postgresql://`` 与 ``postgres://`` 补齐为 ``postgresql+psycopg2://``
    - 已显式声明驱动的连接串原样返回，尊重调用方的选择
    - SQLite 与其他协议原样返回

    参数与返回值都只做字符串替换，不解析账号密码，因此不会破坏特殊字符编码。
    """
    if not url or not isinstance(url, str):
        raise ValueError('DATABASE_URL 不能为空')

    candidate = url.strip()
    scheme, separator, remainder = candidate.partition('://')
    if not separator:
        # 没有协议的相对路径（如 SQLite 文件名），交由调用方原样处理
        return candidate

    scheme = scheme.strip().lower()
    scheme = _SCHEME_ALIASES.get(scheme, scheme)

    if scheme == 'postgresql':
        scheme = f'postgresql+{SUPPORTED_POSTGRES_DRIVER}'

    return f'{scheme}://{remainder}'


def is_postgresql(url):
    """判断连接串是否指向 PostgreSQL（含协议别名与显式驱动形式）。"""
    if not url:
        return False
    scheme = url.strip().partition('://')[0].lower()
    scheme = _SCHEME_ALIASES.get(scheme, scheme)
    return scheme.split('+', 1)[0] == 'postgresql'


def describe_driver(url):
    """返回连接串声明的驱动名，未声明时返回 None。仅用于日志与断言。"""
    scheme = url.strip().partition('://')[0].lower()
    scheme = _SCHEME_ALIASES.get(scheme, scheme)
    parts = scheme.split('+', 1)
    return parts[1] if len(parts) == 2 else None
