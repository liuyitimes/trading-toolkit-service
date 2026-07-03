module.exports = {
  // 云开发环境ID
  // 开发环境：dev-xxx（用于本地测试）
  // 生产环境：prod-xxx（用于线上）
  cloudEnv: {
    development: 'cloudbase-d1gurol40225b603e',  // 开发环境
    production: 'cloudbase-d1gurol40225b603e'    // 生产环境（暂用同一环境，后续可拆分）
  },

  // CloudRun 后端地址
  // 开发者工具调试用 localhost；真机调试请在「设置」页配置电脑局域网 IP
  // 注意：此地址为默认回退值，实际优先使用「设置」页配置的 cloudRunUrl
  development: {
    baseUrl: 'http://localhost:8080'
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