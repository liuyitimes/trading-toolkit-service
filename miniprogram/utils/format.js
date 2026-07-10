function formatNumber(num, digits = 2) {
  if (typeof num !== 'number' || isNaN(num)) return '--'
  return num.toFixed(digits)
}

function formatPercent(num, digits = 2, withSign = true) {
  if (typeof num !== 'number' || isNaN(num)) return '--'
  const sign = withSign && num > 0 ? '+' : ''
  return sign + num.toFixed(digits) + '%'
}

function formatMoney(num, digits = 2) {
  if (typeof num !== 'number' || isNaN(num)) return '--'
  return num.toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

function getTrendClass(num) {
  if (typeof num !== 'number' || isNaN(num)) return ''
  return num > 0 ? 'up' : num < 0 ? 'down' : ''
}

function getPremiumClass(premium) {
  if (typeof premium !== 'number' || isNaN(premium)) return ''
  return premium < 0 ? 'negative' : ''
}

function getExchange(code) {
  if (!code) return ''
  const str = String(code).replace(/^(sh|sz)/, '')
  if (/^[659]/.test(str) || /^1[13]/.test(str)) return '沪'
  if (/^[0123]/.test(str) || /^12/.test(str)) return '深'
  return ''
}

function formatDate(date, format = 'YYYY-MM-DD') {
  const d = date instanceof Date ? date : new Date(date)
  if (isNaN(d.getTime())) return '--'
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hours = String(d.getHours()).padStart(2, '0')
  const minutes = String(d.getMinutes()).padStart(2, '0')
  const seconds = String(d.getSeconds()).padStart(2, '0')
  return format
    .replace('YYYY', year)
    .replace('MM', month)
    .replace('DD', day)
    .replace('HH', hours)
    .replace('mm', minutes)
    .replace('ss', seconds)
}

function getNowString() {
  return new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })
}

module.exports = {
  formatNumber,
  formatPercent,
  formatMoney,
  getTrendClass,
  getPremiumClass,
  getExchange,
  formatDate,
  getNowString
}
