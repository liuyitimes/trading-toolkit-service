Component({
  data: {
    selected: 0,
    isDark: false,
    list: [
      {
        pagePath: "/pages/index/index",
        text: "首页",
        icon: "💰"
      },
      {
        pagePath: "/pages/convertible/index",
        text: "转债",
        icon: "📋"
      },
      {
        pagePath: "/pages/lof/index",
        text: "基金",
        icon: "📈"
      },
      {
        pagePath: "/pages/hkipo/index",
        text: "港股",
        icon: "🎯"
      },
      {
        pagePath: "/pages/setting/index",
        text: "我的",
        icon: "👤"
      }
    ]
  },

  lifetimes: {
    attached() {
      this.checkDarkMode();
    }
  },

  pageLifetimes: {
    show() {
      this.checkDarkMode();
    }
  },

  methods: {
    checkDarkMode() {
      try {
        const theme = wx.getStorageSync('appTheme') || 'light';
        this.setData({ isDark: theme === 'dark' });
      } catch (e) {
        this.setData({ isDark: false });
      }
    },

    switchTab(e) {
      const data = e.currentTarget.dataset;
      const url = data.path;
      console.time('tab-switch');
      wx.switchTab({
        url,
        complete: () => {
          setTimeout(() => console.timeEnd('tab-switch'), 100);
        }
      });
    }
  }
});
