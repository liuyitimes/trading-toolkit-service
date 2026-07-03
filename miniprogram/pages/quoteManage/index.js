const app = getApp()
const quoteManager = require('../../utils/quoteManager')

Page({
  data: {
    quotes: [],
    isDarkMode: false,
    showEditModal: false,
    isEditing: false,
    editIndex: -1,
    editText: '',
    editAuthor: ''
  },

  onLoad() {
    this.loadQuotes()
  },

  onShow() {
    const theme = app.getTheme()
    this.setData({ isDarkMode: theme === 'dark' })
  },

  loadQuotes() {
    const quotes = quoteManager.getQuotes()
    this.setData({ quotes })
  },

  goBack() {
    wx.navigateBack()
  },

  addQuote() {
    this.setData({
      showEditModal: true,
      isEditing: false,
      editIndex: -1,
      editText: '',
      editAuthor: ''
    })
  },

  editQuote(e) {
    const index = e.currentTarget.dataset.index
    const quote = this.data.quotes[index]
    if (!quote) return

    this.setData({
      showEditModal: true,
      isEditing: true,
      editIndex: index,
      editText: quote.text,
      editAuthor: quote.author
    })
  },

  closeModal() {
    this.setData({
      showEditModal: false,
      editIndex: -1,
      editText: '',
      editAuthor: ''
    })
  },

  onTextInput(e) {
    this.setData({ editText: e.detail.value })
  },

  onAuthorInput(e) {
    this.setData({ editAuthor: e.detail.value })
  },

  saveQuote() {
    const { editText, editAuthor, editIndex, isEditing } = this.data

    if (!editText.trim()) {
      wx.showToast({ title: '请输入名言内容', icon: 'none' })
      return
    }

    let success = false

    if (isEditing && editIndex >= 0) {
      success = quoteManager.updateQuote(editIndex, editText, editAuthor)
    } else {
      success = quoteManager.addQuote(editText, editAuthor)
    }

    if (success) {
      this.loadQuotes()
      this.closeModal()
      wx.showToast({
        title: isEditing ? '修改成功' : '添加成功',
        icon: 'success'
      })
    } else {
      wx.showToast({ title: '保存失败', icon: 'none' })
    }
  },

  deleteQuote(e) {
    const index = e.currentTarget.dataset.index

    wx.showModal({
      title: '确认删除',
      content: '确定要删除这条名言吗？',
      success: (res) => {
        if (res.confirm) {
          const success = quoteManager.deleteQuote(index)
          if (success) {
            this.loadQuotes()
            wx.showToast({ title: '删除成功', icon: 'success' })
          } else {
            wx.showToast({ title: '删除失败', icon: 'none' })
          }
        }
      }
    })
  },

  resetQuotes() {
    wx.showModal({
      title: '恢复默认',
      content: '确定要恢复为默认名言列表吗？所有自定义名言将被覆盖。',
      success: (res) => {
        if (res.confirm) {
          const success = quoteManager.resetToDefault()
          if (success) {
            this.loadQuotes()
            wx.showToast({ title: '已恢复默认', icon: 'success' })
          } else {
            wx.showToast({ title: '恢复失败', icon: 'none' })
          }
        }
      }
    })
  },

  stopPropagation() {}
})
