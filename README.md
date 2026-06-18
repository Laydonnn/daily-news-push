# 每日新闻推送系统

每天北京时间 09:30，通过 GitHub Actions 自动抓取 ALAPI 早报和 Hacker News RSS，并发送到飞书机器人 Webhook。

## 配置步骤

1. 获取 ALAPI token

   打开 [ALAPI](https://www.alapi.cn)，注册并登录，找到“早报”接口，复制你的 token。

2. 创建飞书机器人 Webhook

   在飞书里打开目标群聊，进入“设置”或“群机器人”，添加“自定义机器人”，复制生成的 Webhook 地址。

3. 设置 GitHub Secrets

   进入你的 GitHub 仓库：`Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`，新增两个 Secret：

   - `ALAPI_TOKEN`：填写 ALAPI token
   - `FEISHU_WEBHOOK`：填写飞书机器人 Webhook 地址

4. 上传代码到 GitHub

   ```bash
   git init
   git add main.py .github/workflows/schedule.yml README.md
   git commit -m "Add daily news push bot"
   git branch -M main
   git remote add origin https://github.com/你的用户名/你的仓库名.git
   git push -u origin main
   ```

5. 启用 GitHub Actions

   打开仓库的 `Actions` 页面，确认 workflow 已启用。之后系统会每天北京时间 09:30 自动运行，也可以在 `Actions` 页面手动点击 `Run workflow` 测试。
