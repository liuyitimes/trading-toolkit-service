module.exports = {
  // 云开发环境ID
  // 开发环境：dev-xxx（用于本地测试）
  // 生产环境：prod-xxx（用于线上）
  cloudEnv: {
    development: 'cloudbase-d1gurol40225b603e',  // 开发环境
    production: 'cloudbase-d1gurol40225b603e'    // 生产环境（暂用同一环境，后续可拆分）
  },

  // CloudRun 后端地址
  // 小程序真机调试时，需将 localhost 改为电脑的局域网 IP
  development: {
    baseUrl: 'http://192.168.125.241:8080'
  },
  production: {
    baseUrl: 'https://your-service-id.run.tcloudbase.com'
  },

  // 环境切换配置
  // autoSwitch: true 时根据小程序版本自动切换（推荐）
  // autoSwitch: false 时使用 currentEnv 手动指定
  autoSwitch: true,
  currentEnv: 'development'  // autoSwitch: false 时生效
}