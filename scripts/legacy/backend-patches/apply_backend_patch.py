"""应用后端补丁: 在 trading-toolkit-service 仓库添加封闭式基金接口

用法: py apply_backend_patch.py
"""
import os
import re
import shutil
import sys

BACKEND = r'd:\Develop\GitHub\trading-toolkit-service\cloudrun'
PATCH_DIR = os.path.dirname(os.path.abspath(__file__))


def step1_copy_new_file():
    """复制 services/closed_end.py 到后端"""
    src = os.path.join(PATCH_DIR, 'services', 'closed_end.py')
    dst = os.path.join(BACKEND, 'services', 'closed_end.py')
    shutil.copy2(src, dst)
    print(f'[OK] 1/5 复制新文件: services/closed_end.py ({os.path.getsize(dst)} bytes)')


def step2_patch_base():
    """修改 services/base.py: 添加抽象方法"""
    f = os.path.join(BACKEND, 'services', 'base.py')
    with open(f, 'r', encoding='utf-8') as fp:
        content = fp.read()

    if 'get_closed_end_list' in content:
        print('[SKIP] 2/5 base.py 已包含 closed_end 方法')
        return

    new_methods = '''    @abstractmethod
    def get_closed_end_list(self) -> list:
        """获取封闭式基金列表（含价格、净值、折价率）"""

    @abstractmethod
    def get_closed_end_summary(self) -> dict:
        """获取封闭式基金市场概览"""

    @abstractmethod
    def health_check'''
    # 替换原有的 health_check 抽象方法定义
    new_content = re.sub(
        r'    @abstractmethod\n    def health_check',
        new_methods,
        content,
        count=1,
    )
    with open(f, 'w', encoding='utf-8') as fp:
        fp.write(new_content)
    print('[OK] 2/5 修改 base.py: 添加 2 个抽象方法')


def step3_patch_akshare():
    """修改 services/akshare_source.py: 添加 import 和实现"""
    f = os.path.join(BACKEND, 'services', 'akshare_source.py')
    with open(f, 'r', encoding='utf-8') as fp:
        content = fp.read()

    if 'def get_closed_end_list' in content:
        print('[SKIP] 3/5 akshare_source.py 已包含 closed_end 方法')
        return

    # 1. 添加 import (在 from services.hk_ipo import 之前)
    import_block = '''from services.closed_end import (
    get_closed_end_list as _raw_closed_end_list,
    get_closed_end_summary as _raw_closed_end_summary,
)
'''
    if import_block not in content:
        content = re.sub(
            r'(from services\.hk_ipo import \()',
            import_block + r'\1',
            content,
            count=1,
        )

    # 2. 添加方法实现 (在 # ---- 市场情绪 ---- 之前)
    methods_block = '''    # ---- 封闭式基金 ----

    def get_closed_end_list(self) -> list:
        try:
            return _raw_closed_end_list()
        except Exception as e:
            logger.warning(f'[AkshareSource] get_closed_end_list 失败: {e}')
            return []

    def get_closed_end_summary(self) -> dict:
        try:
            return _raw_closed_end_summary()
        except Exception as e:
            logger.warning(f'[AkshareSource] get_closed_end_summary 失败: {e}')
            return {}

'''
    if methods_block not in content:
        content = re.sub(
            r'(    # ---- 市场情绪 ----)',
            methods_block + r'\1',
            content,
            count=1,
        )

    with open(f, 'w', encoding='utf-8') as fp:
        fp.write(content)
    print('[OK] 3/5 修改 akshare_source.py: 添加 import + 2 个方法实现')


def step4_patch_other_sources():
    """修改 efinance/tushare/mock 数据源: 添加空实现"""
    sources = ['efinance_source.py', 'tushare_source.py', 'mock_source.py']
    insert_block = '''    def get_closed_end_list(self) -> list:
        return []

    def get_closed_end_summary(self) -> dict:
        return {}

'''
    for src_name in sources:
        f = os.path.join(BACKEND, 'services', src_name)
        if not os.path.exists(f):
            print(f'[SKIP] {src_name} 不存在')
            continue
        with open(f, 'r', encoding='utf-8') as fp:
            content = fp.read()
        if 'def get_closed_end_list' in content:
            print(f'[SKIP] {src_name} 已包含 closed_end 方法')
            continue
        # 在 def health_check 之前插入
        new_content = re.sub(
            r'(    def health_check)',
            insert_block + r'\1',
            content,
            count=1,
        )
        with open(f, 'w', encoding='utf-8') as fp:
            fp.write(new_content)
        print(f'[OK] 4/5 修改 {src_name}: 添加空实现')


def step5_patch_app():
    """修改 cloudrun/app.py: 添加路由"""
    f = os.path.join(BACKEND, 'app.py')
    with open(f, 'r', encoding='utf-8') as fp:
        content = fp.read()

    if '/api/v1/closed-end/list' in content:
        print('[SKIP] 5/5 app.py 已包含 closed-end 路由')
        return

    route_block = '''# ==================== 封闭式基金 API ====================

@app.route('/api/v1/closed-end/list')
@limit(60)
def closed_end_list():
    """封闭式基金列表"""
    force = request.args.get('refresh', '').lower() == 'true'
    data, source, cached = fetch_with_cache(
        'closed_end_list', 'get_closed_end_list', force_refresh=force)
    if data is None:
        return api_error(*ErrorCode.DATA_SOURCE_ERROR)
    return api_response(data, source=source, cached=cached)


@app.route('/api/v1/closed-end/summary')
@limit(60)
def closed_end_summary():
    """封闭式基金市场概览"""
    force = request.args.get('refresh', '').lower() == 'true'
    data, source, cached = fetch_with_cache(
        'closed_end_summary', 'get_closed_end_summary', force_refresh=force)
    if data is None:
        return api_error(*ErrorCode.DATA_SOURCE_ERROR)
    return api_response(data, source=source, cached=cached)


'''
    # 在 # ==================== 管理接口 之前插入
    new_content = re.sub(
        r'(# ==================== 管理接口)',
        route_block + r'\1',
        content,
        count=1,
    )
    with open(f, 'w', encoding='utf-8') as fp:
        fp.write(new_content)
    print('[OK] 5/5 修改 app.py: 添加 2 个路由')


def main():
    print(f'==> 应用后端补丁到: {BACKEND}')
    print()
    if not os.path.isdir(BACKEND):
        print(f'[ERROR] 后端目录不存在: {BACKEND}')
        sys.exit(1)
    step1_copy_new_file()
    step2_patch_base()
    step3_patch_akshare()
    step4_patch_other_sources()
    step5_patch_app()
    print()
    print('==> 补丁应用完成! 请重启后端 Flask 服务:')
    print('   1. 停止当前后端进程 (Ctrl+C)')
    print('   2. cd d:\\Develop\\GitHub\\trading-toolkit-service')
    print('   3. py cloudrun\\app.py')


if __name__ == '__main__':
    main()
