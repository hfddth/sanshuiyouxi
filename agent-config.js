// 国内网络优先走自有域名；Railway 原始域名仅作为自动备用。
// 网页部署到自有域名并提供同源 /chat 时，会优先尝试当前站点。
window.SANSHUI_AGENT_URLS = [
  'https://api.hfddth.cn',
  'https://sanshuiyouxi-production.up.railway.app'
];
window.SANSHUI_AGENT_URL = window.SANSHUI_AGENT_URLS[0];
