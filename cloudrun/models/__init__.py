# -*- coding: utf-8 -*-
"""数据模型注册入口。

导入所有模型模块，确保 Base.metadata 在 create_all 与 Alembic 自动生成时
包含全部表定义。
"""

import models.convertible_timeline  # noqa: F401
import models.database  # noqa: F401
import models.lof_premium  # noqa: F401
import models.placement  # noqa: F401
import models.user  # noqa: F401
