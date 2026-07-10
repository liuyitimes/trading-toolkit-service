// 港股IPO数据 - 使用mock数据
const mock = require('./mock')

function getHkIpoSummary() {
  const list = mock.HK_IPO_LIST
  const upcomingCount = list.filter(item => item.status === '申购中').length
  const recentCount = list.filter(item => item.status === '已上市').length
  const listed = list.filter(item => item.status === '已上市')
  const avgReturn = listed.length > 0
    ? Math.round((listed.reduce((sum, item) => sum + (item.change_pct || 0), 0) / recentCount) * 10) / 10
    : 0

  return {
    upcoming_count: upcomingCount,
    recent_count: recentCount,
    avg_return: avgReturn
  }
}

function getHkIpoList() {
  return mock.HK_IPO_LIST
}

function getHkIpoUpcoming() {
  return mock.HK_IPO_LIST.filter(item => item.status === '申购中').slice(0, 10)
}

module.exports = {
  getHkIpoSummary,
  getHkIpoList,
  getHkIpoUpcoming
}
