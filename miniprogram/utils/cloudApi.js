// 云函数调用工具类

/**
 * 调用market云函数
 * @param {string} action - 操作类型
 * @param {object} data - 额外参数
 * @returns {Promise<object>}
 */
function callMarket(action, data = {}) {
  return new Promise((resolve, reject) => {
    wx.cloud.callFunction({
      name: 'market',
      data: { action, ...data },
      success: res => {
        if (res.result && res.result.success) {
          resolve(res.result.data)
        } else {
          reject(new Error(res.result ? res.result.error : '云函数返回异常'))
        }
      },
      fail: err => {
        console.error('云函数调用失败:', err)
        reject(err)
      }
    })
  })
}

/**
 * 调用云函数（带容错）
 * @param {string} action - 操作类型
 * @param {object} data - 额外参数
 * @param {*} fallback - 失败时的回退数据
 * @returns {Promise<object>}
 */
async function callMarketSafe(action, data = {}, fallback = null) {
  try {
    const result = await callMarket(action, data)
    return result
  } catch (err) {
    console.error(`云函数[${action}]调用失败，使用回退数据:`, err.message)
    return fallback
  }
}

module.exports = {
  callMarket,
  callMarketSafe
}
