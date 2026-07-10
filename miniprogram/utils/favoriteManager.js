const config = require('../config')

const STORAGE_KEY = 'favorites'
const OPENID_KEY = 'user_openid'
const _FAV_CACHE = { _list: null, _ts: 0 }
const _CACHE_TTL = 5000 // 5秒内复用内存缓存，避免反复读 Storage

// 开发环境判断
const isDev = typeof __wxConfig !== 'undefined' && __wxConfig.debug
const BASE_URL = isDev ? config.development.baseUrl : config.production.baseUrl

/**
 * 获取 openid（优先从缓存读取）
 */
function getOpenid() {
  try {
    return wx.getStorageSync(OPENID_KEY) || ''
  } catch (e) {
    return ''
  }
}

/**
 * HTTP 请求封装（带鉴权）
 */
function requestApi(method, path, data = {}) {
  return new Promise((resolve, reject) => {
    const openid = getOpenid()
    if (!openid) {
      reject(new Error('未登录'))
      return
    }

    const url = BASE_URL + path
    const options = {
      url,
      method,
      header: {
        'X-Openid': openid,
        'Content-Type': 'application/json'
      },
      timeout: 5000,
      success: (res) => {
        if (res.statusCode === 200 && res.data && res.data.success) {
          resolve(res.data.data)
        } else if (res.statusCode === 401) {
          reject(new Error('未授权，请重新登录'))
        } else {
          reject(new Error(`请求失败: ${res.statusCode}`))
        }
      },
      fail: (err) => {
        reject(new Error(`网络错误: ${err.errMsg || 'unknown'}`))
      }
    }

    // DELETE 请求参数放在 query string
    if (method === 'DELETE' && data) {
      const qs = Object.entries(data)
        .filter(([_, v]) => v !== undefined && v !== null)
        .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
        .join('&')
      if (qs) options.url += (url.includes('?') ? '&' : '?') + qs
    } else if (method !== 'GET') {
      options.data = JSON.stringify(data)
    }

    wx.request(options)
  })
}

const favoriteManager = {
  /**
   * 获取所有自选（优先从后端获取，失败时使用本地缓存）
   */
  async getAllAsync() {
    try {
      const result = await requestApi('GET', '/api/v1/user/favorites')
      if (result && result.items) {
        // 转换后端格式为前端格式
        const list = result.items.map(item => ({
          code: item.code,
          name: item.name,
          type: item.type,
          price: item.price,
          premium_rate: item.premium_rate,
          addedAt: item.added_at ? new Date(item.added_at).getTime() : Date.now()
        }))
        // 同步到本地缓存
        this.saveAll(list)
        return list
      }
    } catch (err) {
      console.warn('[favoriteManager] 后端获取失败，使用本地缓存:', err.message)
    }
    // fallback 到本地缓存
    return this.getAll()
  },

  /**
   * 获取所有自选（同步版本，带内存缓存）
   */
  getAll() {
    const now = Date.now()
    if (_FAV_CACHE._list && now - _FAV_CACHE._ts < _CACHE_TTL) {
      return _FAV_CACHE._list
    }
    try {
      const saved = wx.getStorageSync(STORAGE_KEY)
      if (saved && Array.isArray(saved)) {
        _FAV_CACHE._list = saved
        _FAV_CACHE._ts = now
        return saved
      }
    } catch (err) {
      console.error('Failed to get favorites:', err)
    }
    return []
  },

  /**
   * 失效内存缓存
   */
  _invalidateCache() {
    _FAV_CACHE._list = null
    _FAV_CACHE._ts = 0
  },

  /**
   * 保存到本地缓存
   */
  saveAll(list) {
    try {
      wx.setStorageSync(STORAGE_KEY, list || [])
      this._invalidateCache()
      return true
    } catch (err) {
      console.error('Failed to save favorites:', err)
      return false
    }
  },

  /**
   * 添加自选（调用后端 API + 更新本地缓存）
   */
  async addAsync(item, type = 'bond') {
    try {
      await requestApi('POST', '/api/v1/user/favorites', {
        code: item.code,
        name: item.name || '',
        type,
        price: item.price,
        premium_rate: item.premium_rate
      })
      // 更新本地缓存
      const list = this.getAll()
      const existIndex = list.findIndex(i => i.code === item.code && i.type === type)
      if (existIndex < 0) {
        list.unshift({
          ...item,
          type,
          addedAt: Date.now()
        })
        this.saveAll(list)
      }
      this._incrementVersion()
      return true
    } catch (err) {
      console.error('[favoriteManager] 添加失败:', err.message)
      // 后端失败时仍更新本地缓存
      return this.add(item, type)
    }
  },

  /**
   * 添加自选（同步版本，仅本地缓存）
   */
  add(item, type = 'bond') {
    const list = this.getAll()
    const existIndex = list.findIndex(i => i.code === item.code && i.type === type)
    if (existIndex >= 0) {
      return false
    }
    list.unshift({
      ...item,
      type,
      addedAt: Date.now()
    })
    return this.saveAll(list)
  },

  /**
   * 删除自选（调用后端 API + 更新本地缓存）
   */
  async removeAsync(code, type = 'bond') {
    try {
      await requestApi('DELETE', '/api/v1/user/favorites', { code, type })
      // 更新本地缓存
      const list = this.getAll()
      const newList = list.filter(i => !(i.code === code && i.type === type))
      if (newList.length < list.length) {
        this.saveAll(newList)
      }
      this._incrementVersion()
      return true
    } catch (err) {
      console.error('[favoriteManager] 删除失败:', err.message)
      // 后端失败时仍更新本地缓存
      return this.remove(code, type)
    }
  },

  /**
   * 删除自选（同步版本，仅本地缓存）
   */
  remove(code, type = 'bond') {
    const list = this.getAll()
    const newList = list.filter(i => !(i.code === code && i.type === type))
    if (newList.length === list.length) {
      return false
    }
    const saved = this.saveAll(newList)
    if (saved) {
      this._incrementVersion()
    }
    return saved
  },

  /**
   * 判断是否已收藏（内存缓存加速）
   */
  isFavorite(code, type = 'bond') {
    const list = this.getAll()
    return list.some(i => i.code === code && i.type === type)
  },

  /**
   * 批量判断收藏状态（一次 getAll 查全部，避免反复读 Storage）
   * @param {Array} items - [{ code, type }]
   * @returns {Set<string>} 已收藏的 "code:type" 集合
   */
  batchIsFavorite(items) {
    const list = this.getAll()
    const favSet = new Set(list.map(i => i.code + ':' + i.type))
    const result = new Set()
    items.forEach(item => {
      if (favSet.has(item.code + ':' + item.type)) {
        result.add(item.code + ':' + item.type)
      }
    })
    return result
  },

  /**
   * 获取指定类型的所有收藏代码 Set（用于批量刷新）
   */
  getCodesByType(type) {
    const list = this.getAll()
    return new Set(list.filter(i => i.type === type).map(i => i.code))
  },

  /**
   * 切换收藏状态（异步版本，调用后端 API）
   */
  async toggleAsync(item, type = 'bond') {
    const isFav = this.isFavorite(item.code, type)
    if (isFav) {
      await this.removeAsync(item.code, type)
    } else {
      await this.addAsync(item, type)
    }
    return !isFav
  },

  /**
   * 切换收藏状态（同步版本，仅本地缓存）
   */
  toggle(item, type = 'bond') {
    const result = this.isFavorite(item.code, type)
    if (result) {
      this.remove(item.code, type)
    } else {
      this.add(item, type)
    }
    this._incrementVersion()
    return !result
  },

  /**
   * 按类型获取
   */
  getByType(type) {
    const list = this.getAll()
    return list.filter(i => i.type === type)
  },

  /**
   * 清空所有
   */
  clearAll() {
    return this.saveAll([])
  },

  /**
   * 获取总数
   */
  getCount() {
    return this.getAll().length
  },

  /**
   * 递增版本号（通知其他页面刷新）
   */
  _incrementVersion() {
    try {
      const app = getApp()
      if (app && app.globalData) {
        app.globalData.favoriteVersion = (app.globalData.favoriteVersion || 0) + 1
      }
    } catch (e) {}
  }
}

module.exports = favoriteManager
