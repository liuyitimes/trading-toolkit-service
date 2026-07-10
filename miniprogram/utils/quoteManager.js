const { defaultQuotes } = require('../data/defaultQuotes')

const STORAGE_KEY = 'quotes'

const quoteManager = {
  getQuotes() {
    try {
      const savedQuotes = wx.getStorageSync(STORAGE_KEY)
      if (savedQuotes && Array.isArray(savedQuotes) && savedQuotes.length > 0) {
        return savedQuotes
      }
    } catch (err) {
      console.error('Failed to get quotes:', err)
    }
    return this.getDefaultQuotes()
  },

  saveQuotes(quotes) {
    try {
      if (!quotes || !Array.isArray(quotes) || quotes.length === 0) {
        quotes = this.getDefaultQuotes()
      }
      wx.setStorageSync(STORAGE_KEY, quotes)
      return true
    } catch (err) {
      console.error('Failed to save quotes:', err)
      return false
    }
  },

  addQuote(text, author = '佚名') {
    const quotes = this.getQuotes()
    quotes.push({
      text: text.trim(),
      author: author.trim() || '佚名'
    })
    return this.saveQuotes(quotes)
  },

  updateQuote(index, text, author = '佚名') {
    const quotes = this.getQuotes()
    if (index >= 0 && index < quotes.length) {
      quotes[index] = {
        text: text.trim(),
        author: author.trim() || '佚名'
      }
      return this.saveQuotes(quotes)
    }
    return false
  },

  deleteQuote(index) {
    const quotes = this.getQuotes()
    if (index >= 0 && index < quotes.length) {
      quotes.splice(index, 1)
      return this.saveQuotes(quotes)
    }
    return false
  },

  resetToDefault() {
    return this.saveQuotes([...defaultQuotes])
  },

  getDefaultQuotes() {
    return [...defaultQuotes]
  },

  getRandomQuote() {
    const quotes = this.getQuotes()
    const randomIndex = Math.floor(Math.random() * quotes.length)
    return quotes[randomIndex]
  },

  getQuoteByIndex(index) {
    const quotes = this.getQuotes()
    return quotes[index % quotes.length]
  },

  getQuoteCount() {
    return this.getQuotes().length
  }
}

module.exports = quoteManager