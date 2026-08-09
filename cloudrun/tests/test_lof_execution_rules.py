from datetime import date, datetime
from pathlib import Path
import sys
import unittest
import zipfile
from io import BytesIO

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import models  # noqa: F401
from models.database import Base
from models.lof_execution import LofExecutionEvidence, LofExecutionFund, LofExecutionRule
from services.lof_execution_rules import (
    resolve_execution_rules,
    run_execution_rules_backfill,
    run_execution_status_refresh,
)


class FakeResponse:
    def __init__(self, text='', payload=None, content=b''):
        self.text = text
        self._payload = payload or {}
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _docx_content(text):
    content = BytesIO()
    with zipfile.ZipFile(content, 'w') as archive:
        archive.writestr(
            'word/document.xml',
            f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>',
        )
    return content.getvalue()


def sse_fetcher(url, *_args, **_kwargs):
    if str(url).endswith('.docx'):
        return FakeResponse(content=_docx_content(
            '第三十九条 投资者通过场内证券经营机构申购、赎回上证LOF份额。申购金额应当为1元的整倍数，且不低于1000元。第四十条 '
            '第四十六条 上证LOF申购业务。投资者通过有资格的场内证券经营机构提交场内申购申请。T+1日，中国结算TA系统将场内申购确认结果发送。第四十七条'
        ))
    return FakeResponse('上海证券交易所上市开放式基金业务指引 现行有效 10779392/files/guide.docx')


class LofExecutionRulesTest(unittest.TestCase):
    def test_backfill_registers_every_fund_and_only_applies_matching_generic_rule(self):
        db = session()
        result = run_execution_rules_backfill(
            db,
            [
                {'f12': '501001', 'f13': '1', 'f14': '上证 LOF'},
                {'f12': '161001', 'f13': '0', 'f14': '深证 LOF'},
            ],
            fetcher=sse_fetcher,
        )

        resolved = resolve_execution_rules(db, ['501001', '161001'])
        self.assertTrue(result['acquired'])
        self.assertEqual(result['fund_count'], 2)
        self.assertEqual(resolved['501001']['settlement_timing']['subscription_confirmation']['timing_text'], 'T+1')
        self.assertEqual(resolved['501001']['minimum_order']['subscription']['display_text'], '1000 元')
        self.assertIsNone(resolved['501001']['subscription_limit'])
        self.assertFalse(resolved['501001']['custody_transfer'])
        self.assertEqual(resolved['161001']['settlement_timing']['subscription_confirmation']['status'], 'unavailable')
        self.assertEqual(
            db.query(LofExecutionFund).filter_by(fund_code='161001').one().discovery_status,
            'unavailable',
        )

    def test_same_priority_conflict_stays_unavailable(self):
        db = session()
        fund = LofExecutionFund(fund_code='501001', exchange='sh', share_class='listed')
        db.add(fund)
        db.flush()
        evidence_a = LofExecutionEvidence(
            source_kind='manager_announcement', source_identifier='a', source_title='公告 A',
            source_url='https://example.test/a', applies_to='fund_code', effective_from=date(2026, 1, 1),
        )
        evidence_b = LofExecutionEvidence(
            source_kind='manager_announcement', source_identifier='b', source_title='公告 B',
            source_url='https://example.test/b', applies_to='fund_code', effective_from=date(2026, 1, 1),
        )
        db.add_all([evidence_a, evidence_b])
        db.flush()
        db.add_all([
            LofExecutionRule(fund_id=fund.id, exchange='sh', share_class='listed', field_key='subscription_confirmation', value_text='T+1', source_priority=100, evidence_id=evidence_a.id),
            LofExecutionRule(fund_id=fund.id, exchange='sh', share_class='listed', field_key='subscription_confirmation', value_text='T+2', source_priority=100, evidence_id=evidence_b.id),
        ])
        db.commit()

        resolved = resolve_execution_rules(db, ['501001'], now=datetime(2026, 8, 9))['501001']
        self.assertEqual(resolved['settlement_timing']['subscription_confirmation']['status'], 'unavailable')
        self.assertEqual(resolved['settlement_timing']['subscription_confirmation']['reason'], '同优先级规则冲突')

    def test_status_refresh_only_requests_ranked_top_funds(self):
        db = session()
        calls = []

        def getter(_url, **kwargs):
            calls.append(kwargs['params']['fundCode'])
            return FakeResponse(payload={'Data': {'LSJZList': [{'SGZT': '开放申购', 'SHZT': '开放赎回'}]}})

        result = run_execution_status_refresh(
            db,
            [
                {'代码': '501001', '交易所': '沪', '报价有效': True, '溢价率': 5.0},
                {'代码': '161001', '交易所': '深', '报价有效': True, '溢价率': 1.0},
            ],
            getter=getter,
            top=1,
        )

        resolved = resolve_execution_rules(db, ['501001'])['501001']
        self.assertTrue(result['acquired'])
        self.assertEqual(calls, ['501001'])
        self.assertTrue(resolved['subscription_open'])
        self.assertEqual(resolved['subscription_status'], '开放申购')
