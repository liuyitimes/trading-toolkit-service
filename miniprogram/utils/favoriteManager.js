const STORAGE_KEY = 'favorites'

const favoriteManager = {
  getAll() {
    try {
      const saved = wx.getStorageSync(STORAGE_KEY)
      if (saved && Array.isArray(saved)) {
        return saved
      }
    } catch (err) {
      console.error('Failed to get favorites:', err)
    }
    return []
  },

  saveAll(list) {
    try {
      wx.setStorageSync(STORAGE_KEY, list || [])
      return true
    } catch (err) {
      console.error('Failed to save favorites:', err)
      return false
    }
  },

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

  remove(code, type = 'bond') {
    const list = this.getAll()
    const newList = list.filter(i => !(i.code === code && i.type === type))
    if (newList.length === list.length) {
      return false
    }
    return this.saveAll(newList)
  },

  isFavorite(code, type = 'bond') {
    const list = this.getAll()
    return list.some(i => i.code === code && i.type === type)
  },

  toggle(item, type = 'bond') {
    if (this.isFavorite(item.code, type)) {
      this.remove(item.code, type)
      return false
    } else {
      this.add(item, type)
      return true
    }
  },

  getByType(type) {
    const list = this.getAll()
    return list.filter(i => i.type === type)
  },

  clearAll() {
    return this.saveAll([])
  },

  getCount() {
    return this.getAll().length
  }
}

module.exports = favoriteManager
