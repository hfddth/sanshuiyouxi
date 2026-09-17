# 山水有戏项目储存

网站仍由 GitHub Pages 提供。Supabase 负责登录、私有项目表和地图/资料文件。

1. 在 [Supabase Dashboard](https://supabase.com/dashboard) 建立项目，区域选择符合你的客户数据要求的位置。保管好数据库密码。
2. 在 SQL Editor 中执行 `migrations/20260917000000_project_storage.sql`。检查 `projects` 表已启用 RLS，`project-assets` bucket 为私有。
3. 在 Authentication → URL Configuration 设置 Site URL 和 Redirect URL：`https://hfddth.github.io/sanshuiyouxi/`。
4. 把 Project URL 与 **publishable key** 填入网站根目录 `cloud-config.js` 的 `url`、`publishableKey`。不要填写 secret/service_role key，也不要将 DeepSeek 密钥放入前端。
5. 登录网站的“云端账号”，点击“保存方案”或在方案页按 Ctrl+S / ⌘+S。去 Supabase Table Editor 核对写入的数据；换一台设备用同一邮箱登录，打开项目库验证读取。

当前创建页只需填写景区名称。`project-assets` 私有 bucket 为后续地图与资料功能预留，当前页面不提供文件上传。

账号未连接时，快捷保存仍会保存到当前浏览器。清除浏览器数据会删除这份本地副本；云端成功同步后可跨设备读取。

DeepSeek 的调用应放在独立后端或 Supabase Edge Function，密钥仅配置为服务端 secret。这个迁移不包含模型调用。

