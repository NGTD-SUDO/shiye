"""法律文档合页 HTML —— `GET /legal` 的内容源（T12 收尾 / T12-A）

**来源**：`legal/web/index.html`（由 `legal/md_to_legal_html.py` 从 4 份法律 md 生成）。
本文件是该产物的**逐字内联**（由一次性脚本生成、脚本未随交付），请勿手工编辑内容。

**更新步骤**（改完法律 md 后）：
1. 重跑 `legal/md_to_legal_html.py` 生成新的 `legal/web/index.html`；
   T12-A 起该生成器**已内置邮箱实体化**（写出前统一把邮箱里的 `@` 换成 `&#64;`），
   产物天然没有明文邮箱，**不再需要事后手工替换**；
2. 按文本模式读取该文件（CRLF 归一为 LF），把内容整体放进本文件的 `LEGAL_HTML = 三引号字符串`
   （内容里不含连续三个双引号，可直接承载）。

**为什么邮箱必须写成实体**：Cloudflare 免费隧道会把页面里的明文邮箱自动改写成
`[email protected]`，法律页这样就等于没有有效联系方式（合规审核会看）。实体形式
（形如 `contact&#64;example.com`）中间层的正则匹配不到，浏览器渲染仍显示正常邮箱。

**自包含**：无外部 CSS/JS/字体依赖，可离线打开。
**长度**：LF 归一化后 32139 字符。
"""

LEGAL_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>拾页 · 法律条款</title>
<style>
:root {
  --green: #16A085; --green-deep: #0E7A64; --ink: #22312B;
  --ink-2: #5B6B64; --ink-3: #8A9A93; --line: #E3EBE7; --bg: #F7FAF8; --card: #FFFFFF;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font: 15px/1.75 -apple-system, "PingFang SC", "Microsoft YaHei", "Helvetica Neue", sans-serif;
  -webkit-text-size-adjust: 100%;
}
header {
  position: sticky; top: 0; z-index: 10; background: rgba(255,255,255,.92);
  backdrop-filter: blur(12px); border-bottom: 1px solid var(--line);
}
.hd { max-width: 860px; margin: 0 auto; padding: 14px 20px 0; }
.brand { display: flex; align-items: center; gap: 10px; }
.dot { width: 26px; height: 26px; border-radius: 9px; background: var(--green); }
.brand b { font-size: 17px; letter-spacing: .5px; }
.brand span { font-size: 12px; color: var(--ink-3); }
nav { display: flex; gap: 6px; overflow-x: auto; padding: 12px 0 10px; scrollbar-width: none; }
nav::-webkit-scrollbar { display: none; }
nav a {
  flex: 0 0 auto; padding: 6px 13px; border-radius: 999px; font-size: 13px;
  color: var(--ink-2); background: #EFF5F2; text-decoration: none; white-space: nowrap;
}
nav a:hover, nav a:active { background: var(--green); color: #fff; }
main { max-width: 860px; margin: 0 auto; padding: 22px 20px 60px; }
.doc {
  background: var(--card); border: 1px solid var(--line); border-radius: 18px;
  padding: 26px 24px 30px; margin-bottom: 26px; scroll-margin-top: 96px;
  box-shadow: 0 1px 3px rgba(22,49,43,.04);
}
.doc h1 { font-size: 21px; margin: 0 0 4px; color: var(--green-deep); }
.doc h2 {
  font-size: 16.5px; margin: 30px 0 12px; padding-left: 11px;
  border-left: 3px solid var(--green); color: var(--ink);
}
.doc h3 { font-size: 14.5px; margin: 20px 0 8px; color: var(--green-deep); }
.doc h4 { font-size: 14px; margin: 16px 0 6px; color: var(--ink-2); }
.doc p { margin: 9px 0; color: #33443D; }
.doc strong { color: var(--ink); }
.doc a { color: var(--green-deep); word-break: break-all; }
.doc code { background: #EFF5F2; padding: 1px 5px; border-radius: 5px; font-size: .9em; }
.doc hr { border: 0; border-top: 1px solid var(--line); margin: 22px 0; }
.doc ul, .doc ol { padding-left: 22px; margin: 9px 0; }
.doc li { margin: 5px 0; }
.doc li.sub { list-style: circle; margin-left: 14px; font-size: .96em; color: var(--ink-2); }
.tw { overflow-x: auto; margin: 12px 0; -webkit-overflow-scrolling: touch; }
table { border-collapse: collapse; width: 100%; font-size: 13.5px; min-width: 460px; }
th, td { border: 1px solid var(--line); padding: 8px 10px; text-align: left; vertical-align: top; }
th { background: #F1F7F4; font-weight: 600; color: var(--ink); white-space: nowrap; }
tr:nth-child(even) td { background: #FBFDFC; }
footer { text-align: center; color: var(--ink-3); font-size: 12px; padding: 0 20px 40px; }
@media (max-width: 560px) {
  .doc { padding: 20px 16px 24px; border-radius: 14px; }
  main { padding: 16px 12px 40px; }
  table { font-size: 12.5px; min-width: 380px; }
}
</style>
</head>
<body>
<header>
  <div class="hd">
    <div class="brand">
      <div class="dot"></div>
      <div><b>拾页</b> <span>法律条款</span></div>
    </div>
    <nav><a href='#privacy'>隐私政策</a><a href='#agreement'>用户协议</a><a href='#third-party'>第三方信息共享清单</a><a href='#data-collection'>个人信息收集清单</a></nav>
  </div>
</header>
<main>
<section id='privacy' class='doc'><h1>拾页 隐私政策</h1>
<p><strong>版本号：v1.0</strong> <strong>生效日期：2026年9月19日</strong> <strong>更新日期：2026年9月19日</strong></p>
<hr>
<h2>引言</h2>
<p>拾页（以下简称"本 App"或"我们"）是一款手写笔记拍照数字化整理工具。我们深知个人信息对你 的重要性，并将本着合法、正当、必要和诚信的原则处理你的个人信息。</p>
<p><strong>在使用本 App 前，请务必仔细阅读并充分理解本政策全部内容。</strong> 特别提示：本 App 会将你上传的笔记图片发送至第三方 OCR 服务进行文字识别， 并将笔记文本内容发送至第三方 AI 服务。<strong>若你不同意本政策，请点击"拒绝并退出APP"， 我们将不会收集你的任何信息。</strong></p>
<p>本政策适用于本 App 的全部功能。请你注意，本政策不适用于其他第三方向你提供的服务。</p>
<hr>
<h2>一、我们如何收集和使用你的个人信息</h2>
<p>我们仅会出于本政策所述目的，收集和使用你的如下信息。</p>
<h3>1.1 你主动提供的信息</h3>
<div class='tw'><table>
<thead><tr><th>信息项</th><th>收集场景</th><th>收集目的</th><th>是否必要</th></tr></thead>
<tbody>
<tr><td><strong>昵称</strong></td><td>首次登录时由你填写</td><td>用于在 App 内标识你的账号</td><td>必要</td></tr>
<tr><td><strong>笔记图片</strong></td><td>你使用"拍照"或"从相册选择"上传笔记时</td><td>用于识别笔记文字、生成可检索的笔记内容</td><td>必要</td></tr>
<tr><td><strong>笔记标题</strong></td><td>你可选填</td><td>用于组织与管理你的笔记</td><td>非必要</td></tr>
<tr><td><strong>学科名称、章节名称</strong></td><td>你自行创建时</td><td>用于对笔记分类整理</td><td>非必要</td></tr>
</tbody></table></div>
<h3>1.2 我们在你使用服务时收集的信息</h3>
<div class='tw'><table>
<thead><tr><th>信息项</th><th>收集场景</th><th>收集目的</th><th>是否必要</th></tr></thead>
<tbody>
<tr><td><strong>账号标识（设备标识）</strong></td><td>首次登录时自动生成</td><td>用于建立并识别你的账号</td><td>必要</td></tr>
<tr><td><strong>笔记识别文本（OCR 文本）</strong></td><td>笔记图片识别完成后</td><td>用于文字检索、AI 分析与人工校对</td><td>必要</td></tr>
<tr><td><strong>AI 整理结果</strong></td><td>你主动使用"AI 整理"功能时</td><td>用于生成结构化笔记内容</td><td>非必要</td></tr>
<tr><td><strong>笔记统计数据</strong></td><td>你使用"学情分析"功能时</td><td>用于生成学习统计与诊断报告</td><td>非必要</td></tr>
</tbody></table></div>
<h3>1.3 关于账号标识的特别说明</h3>
<p>本 App 的账号标识（形如 <code>dev_</code> 开头的 32 位随机字符）由<strong>你的设备在本地随机生成</strong>， <strong>不是</strong>你的手机硬件标识（非 IMEI、非 Android ID、非 MAC 地址）， 且<strong>卸载本 App 后即永久失效</strong>。我们无法通过该标识定位到你的真实身份。</p>
<h3>1.4 我们不会收集的信息</h3>
<p>本 App <strong>不收集、不访问</strong>以下信息：</p>
<ul>
<li>你的地理位置</li>
<li>你的通讯录、通话记录、短信</li>
<li>你的剪贴板内容</li>
<li>你的相册全量内容（仅在<strong>你主动选择</strong>图片时访问你选中的那一张/那几张）</li>
<li>设备硬件标识（IMEI / Android ID / MAC 地址）</li>
<li>传感器数据、已安装应用列表</li>
</ul>
<h3>1.5 权限使用说明</h3>
<p>本 App 仅申请以下系统权限：</p>
<div class='tw'><table>
<thead><tr><th>权限</th><th>用途</th><th>申请时机</th></tr></thead>
<tbody>
<tr><td><strong>网络访问</strong></td><td>与服务器通信，上传笔记、获取识别结果</td><td>应用启动时（系统自动授予）</td></tr>
<tr><td><strong>相机</strong></td><td>拍摄纸质笔记</td><td>你<strong>点击"拍照"时</strong>才会向你申请</td></tr>
<tr><td><strong>相册（读写）</strong></td><td>选择已有笔记照片</td><td>你<strong>点击"从相册选择"时</strong>才会向你申请</td></tr>
</tbody></table></div>
<p><strong>我们不会在你启动 App 时预申请相机或相册权限。</strong> 如你拒绝授权，仅对应功能不可用， 不影响其他功能。</p>
<hr>
<h2>二、我们如何使用 Cookie 及同类技术</h2>
<p>本 App <strong>不使用</strong> Cookie、像素标签等追踪技术，<strong>不进行</strong>用户行为画像或跨应用追踪。 本 App 在本地存储的信息详见第七节。</p>
<hr>
<h2>三、我们如何共享、转让、公开披露你的个人信息</h2>
<h3>3.1 共享（<strong>请你特别关注本节</strong>）</h3>
<p>为实现核心功能，我们会将必要信息共享给以下第三方。<strong>除以下场景外，我们不会向任何第三方 提供你的个人信息。</strong></p>
<h4>3.1.1 百度智能云（文字识别服务）</h4>
<div class='tw'><table>
<thead><tr><th>项</th><th>内容</th></tr></thead>
<tbody>
<tr><td>第三方名称</td><td>北京百度网讯科技有限公司（百度智能云）</td></tr>
<tr><td>共享的信息</td><td><strong>你上传的笔记图片（完整图片内容）</strong></td></tr>
<tr><td>共享目的</td><td>手写文字识别（OCR），将图片转换为可检索文本</td></tr>
<tr><td>共享方式</td><td>通过加密接口传输至百度服务器</td></tr>
<tr><td>触发条件</td><td><strong>仅在你使用笔记识别功能时</strong></td></tr>
<tr><td>隐私政策链接</td><td><a href="https://cloud.baidu.com/doc/Agreements/s/djwvy2q7n" target="_blank" rel="noopener">https://cloud.baidu.com/doc/Agreements/s/djwvy2q7n</a></td></tr>
</tbody></table></div>
<p>⚠️ <strong>特别提示</strong>：为完成文字识别，<strong>你上传的笔记图片会被发送至百度服务器</strong>。 如果你不希望图片被发送至第三方，请<strong>不要使用拍照/上传识别功能</strong>。</p>
<h4>3.1.2 DeepSeek（人工智能分析服务）</h4>
<div class='tw'><table>
<thead><tr><th>项</th><th>内容</th></tr></thead>
<tbody>
<tr><td>第三方名称</td><td>杭州深度求索人工智能基础技术研究有限公司（DeepSeek）</td></tr>
<tr><td>共享的信息</td><td><strong>你的笔记文本内容</strong>，具体范围因功能而异（见下方说明）&lt;br&gt;<strong>不包含</strong>图片</td></tr>
<tr><td>共享目的</td><td>生成学情分析报告、生成练习题、判分、笔记结构化整理</td></tr>
<tr><td>共享方式</td><td>通过加密接口传输至 DeepSeek 服务器</td></tr>
<tr><td>触发条件</td><td><strong>仅在你主动使用 AI 相关功能时</strong>（学情分析 / 答题测评 / AI 整理）</td></tr>
<tr><td>隐私政策链接</td><td><a href="https://platform.deepseek.com/downloads/DeepSeek%20Privacy%20Policy.html" target="_blank" rel="noopener">https://platform.deepseek.com/downloads/DeepSeek%20Privacy%20Policy.html</a></td></tr>
</tbody></table></div>
<p><strong>不同功能发送的文本范围：</strong></p>
<div class='tw'><table>
<thead><tr><th>功能</th><th>发送的内容</th></tr></thead>
<tbody>
<tr><td><strong>AI 整理笔记（单页）</strong></td><td>该页的<strong>识别文本全文</strong></td></tr>
<tr><td><strong>AI 整理笔记（整章）</strong></td><td>该章下<strong>全部页面的识别文本全文</strong>（拼接后发送）</td></tr>
<tr><td>学情分析</td><td>笔记标题 + 每页正文摘要（每页最多前 120 字，最多 60 页）+ 统计数据</td></tr>
<tr><td>出题 / 判分</td><td>笔记标题 + 每页正文摘要（每页最多前 120 字，最多 60 页）+ 你的作答内容</td></tr>
</tbody></table></div>
<p>⚠️ <strong>特别提示</strong>：使用 <strong>AI 整理</strong>功能时，<strong>该页（或该章）的笔记文本全文</strong>会被发送至 DeepSeek。如果你不希望完整文本被发送至第三方，请<strong>不要使用 AI 整理功能</strong>。 不使用 AI 功能不影响笔记的识别、存储、检索与导出。</p>
<h4>3.1.3 关于"数据不出你自己的服务器"的说明</h4>
<p>本 App 支持私有化部署。<strong>你的笔记图片、识别文本与 AI 整理结果均存储在你自行部署的 服务器上</strong>（详见第五节）。但请注意：<strong>当使用 OCR 与 AI 功能时，相关信息仍会按上述规则 发送至第三方服务商</strong>，这是实现该功能的必要前提。</p>
<h3>3.2 转让</h3>
<p>我们<strong>不会</strong>将你的个人信息转让给任何公司、组织或个人。 如发生合并、收购等情形，我们将要求新的持有方继续受本政策约束。</p>
<h3>3.3 公开披露</h3>
<p>我们<strong>不会</strong>公开披露你的个人信息，法律法规另有规定的除外。</p>
<h3>3.4 例外情形</h3>
<p>根据法律法规，以下情形中共享、转让、公开披露个人信息无需征得你的同意：</p>
<ol>
<li>与我们履行法律法规规定的义务相关的；</li>
<li>与国家安全、国防安全直接相关的；</li>
<li>与公共安全、公共卫生、重大公共利益直接相关的；</li>
<li>与刑事侦查、起诉、审判和判决执行等直接相关的；</li>
<li>出于维护你或其他个人的生命、财产等重大合法权益但又很难得到本人同意的；</li>
<li>你自行向社会公众公开的个人信息；</li>
<li>从合法公开披露的信息中收集个人信息的。</li>
</ol>
<hr>
<h2>四、我们如何保护你的个人信息</h2>
<ol>
<li><strong>传输安全</strong>：客户端与服务器之间的通信使用加密传输（HTTPS）。</li>
<li><strong>访问控制</strong>：所有笔记资源按账号隔离，你<strong>无法访问他人的笔记</strong>。图片访问采用</li>
</ol>
<p>带签名的临时链接（有效期 15 分钟），链接过期后自动失效。</p>
<ol>
<li><strong>服务端安全</strong>：上游服务商的密钥仅存放于服务器环境变量中，<strong>不会写入客户端</strong>。</li>
<li><strong>上传校验</strong>：上传文件会进行格式校验、大小限制与安全检测，防止恶意文件。</li>
<li><strong>日志脱敏</strong>：服务端访问日志不记录图片签名信息。</li>
</ol>
<p><strong>请你理解</strong>：互联网环境并非绝对安全，我们将尽力确保你信息的安全性。</p>
<hr>
<h2>五、我们如何存储你的个人信息</h2>
<h3>5.1 存储位置</h3>
<div class='tw'><table>
<thead><tr><th>数据类型</th><th>存储位置</th></tr></thead>
<tbody>
<tr><td>笔记图片、识别文本、AI 结果</td><td><strong>你自行部署的服务器</strong></td></tr>
<tr><td>账号信息（账号标识、昵称）</td><td>同上</td></tr>
<tr><td>本地登录凭证</td><td><strong>你的设备本地</strong></td></tr>
</tbody></table></div>
<p>本 App 采用私有化部署模式，<strong>你的笔记数据默认存储在你自己的服务器上</strong>， 不由本 App 开发者集中收集。</p>
<h3>5.2 存储期限</h3>
<ul>
<li><strong>笔记数据</strong>：在你主动删除前持续保存。你删除笔记、学科或账号后，数据将被删除。</li>
<li><strong>账号信息</strong>：在你注销账号前持续保存。</li>
<li><strong>图片文件</strong>：你删除笔记时，对应图片文件将被<strong>物理删除</strong>。</li>
<li><strong>服务终止后</strong>：如本 App 的某项服务终止，我们将在服务终止后 <strong>30 日内</strong>删除或匿名化</li>
</ul>
<p>相关个人信息。</p>
<h3>5.3 存储地域</h3>
<p>数据存储于你所部署服务器的所在地。若你使用本 App 开发者提供的演示服务， 数据存储于中华人民共和国境内。</p>
<hr>
<h2>六、你的权利</h2>
<p>根据《中华人民共和国个人信息保护法》，你对自己的个人信息享有以下权利：</p>
<h3>6.1 查阅、复制权</h3>
<p>你可以随时在 App 内查看你的全部笔记内容、识别文本与账号信息。</p>
<h3>6.2 更正、补充权</h3>
<ul>
<li><strong>识别文本</strong>：你可以在笔记详情页<strong>直接编辑</strong>识别结果，修正内容会立即生效并更新搜索索引。</li>
<li><strong>昵称</strong>：你可以在「我的 → 修改昵称」中修改。</li>
<li><strong>笔记标题、学科、章节</strong>：你可以随时重命名或调整。</li>
</ul>
<h3>6.3 删除权</h3>
<p>你可以删除以下内容，删除后<strong>不可恢复</strong>：</p>
<div class='tw'><table>
<thead><tr><th>操作</th><th>路径</th><th>效果</th></tr></thead>
<tbody>
<tr><td>删除单篇笔记</td><td>笔记详情页 → 删除</td><td>笔记记录与图片文件一并物理删除</td></tr>
<tr><td>删除章节</td><td>学科详情页 → 章节管理</td><td>章节删除，章节下笔记保留并归入"未分章"</td></tr>
<tr><td>删除学科</td><td>学科列表 → 长按 → 删除</td><td>该学科及其下全部笔记、图片一并删除</td></tr>
<tr><td><strong>注销账号</strong></td><td>我的 → 注销账号</td><td>删除你的<strong>全部数据</strong>（见 6.4）</td></tr>
</tbody></table></div>
<h3>6.4 注销账号</h3>
<p>你可以通过「我的 → 账号 → 注销账号」永久删除你的账号。注销后：</p>
<ul>
<li>你的账号标识、昵称、全部学科、章节、笔记记录与图片文件将被<strong>永久删除</strong>；</li>
<li>该操作<strong>不可撤销、不可恢复</strong>；</li>
<li>注销后使用同一设备重新登录，将视为<strong>全新账号</strong>，无法找回原有数据。</li>
</ul>
<h3>6.5 撤回同意</h3>
<p>你可以通过「我的 → 隐私政策 → 撤回同意」撤回你的授权。撤回后：</p>
<ul>
<li>我们将<strong>停止基于该授权对你信息的处理</strong>；</li>
<li>相关功能将<strong>不可用</strong>，你需要<strong>重新同意</strong>后才能继续使用本 App；</li>
<li><strong>请注意</strong>：撤回同意不影响撤回前基于你的同意已进行的处理活动的效力。</li>
</ul>
<h3>6.6 解释说明权</h3>
<p>如你对本政策有任何疑问，可通过第十节的方式联系我们。</p>
<hr>
<h2>七、本 App 在本地存储的信息</h2>
<p>为正常提供服务，本 App 会在你的设备本地保存以下信息。<strong>这些信息不会自动上传</strong>， 你可以通过"清除应用数据"或卸载本 App 予以删除：</p>
<div class='tw'><table>
<thead><tr><th>本地存储项</th><th>用途</th><th>卸载后</th></tr></thead>
<tbody>
<tr><td>登录凭证（Token）</td><td>保持登录状态</td><td>清除</td></tr>
<tr><td>账号标识</td><td>识别你的账号</td><td><strong>永久失效，不可恢复</strong></td></tr>
<tr><td>隐私政策同意状态</td><td>避免重复弹窗</td><td>清除</td></tr>
<tr><td>笔记整理结果缓存</td><td>减少重复请求、节省流量</td><td>清除</td></tr>
<tr><td>导出的文件</td><td>你导出的笔记文件</td><td>需你自行删除</td></tr>
</tbody></table></div>
<p>⚠️ <strong>特别提示</strong>：<strong>卸载重装本 App 会导致账号标识变化，你将无法看到原账号下的笔记数据。</strong> 如需保留数据，请在卸载前确认数据已妥善处理，或联系服务提供方。</p>
<hr>
<h2>八、未成年人保护</h2>
<ol>
<li>我们<strong>特别重视未成年人个人信息的保护</strong>。</li>
<li>若你是<strong>未满 14 周岁的儿童</strong>，请务必在<strong>你的父母或其他监护人</strong>的指导下阅读本政策，</li>
</ol>
<p>并在取得监护人同意后使用本 App。<strong>我们不会主动收集未满 14 周岁儿童的任何信息</strong>； 若你未经监护人同意使用本 App 并上传了信息，请监护人通过第十节方式联系我们， 我们将尽快删除相关信息。</p>
<ol>
<li>若你是<strong>已满 14 周岁、未满 18 周岁的未成年人</strong>，请在监护人指导下使用本 App，</li>
</ol>
<p>并请监护人关注你的使用情况。</p>
<ol>
<li>我们不会将未成年人信息用于任何商业目的。</li>
<li>若我们发现在未事先获得可证实的监护人同意的情况下收集了儿童个人信息，</li>
</ol>
<p>将设法尽快删除相关数据。</p>
<hr>
<h2>九、本政策的更新</h2>
<ol>
<li>我们可能适时修订本政策内容。</li>
<li>对于<strong>重大变更</strong>（如收集范围变化、共享对象变化、你的权利行使方式变化等），</li>
</ol>
<p>我们将在 App 内以<strong>弹窗方式</strong>再次征求你的同意。</p>
<ol>
<li>对于<strong>非重大变更</strong>（如文字表述优化、联系方式更新等），我们将在本政策页面更新版本号与</li>
</ol>
<p>更新日期，不再重复征求同意。</p>
<ol>
<li>你可以在「我的 → 隐私政策」中随时查看本政策的最新版本与版本号。</li>
</ol>
<hr>
<h2>十、如何联系我们</h2>
<p>如你对本政策有任何疑问、意见或建议，或需要行使上述权利，请通过以下方式联系我们：</p>
<ul>
<li><strong>联系邮箱</strong>：contact&#64;example.com</li>
<li><strong>响应时限</strong>：我们将在收到你的请求后 <strong>15 个工作日内</strong>予以答复</li>
</ul>
<p>如你对我们个人信息处理行为有异议，且无法通过上述方式解决， 你还可以向<strong>网信部门、电信管理机构、公安部门、市场监管部门</strong>等监管机关投诉举报。</p>
<hr>
<h2>十一、附则</h2>
<ol>
<li>本政策自 2026 年 9 月 19 日起生效。</li>
<li>本政策的解释与争议解决适用中华人民共和国法律。</li>
<li>本政策不构成对任何第三方服务的承诺，你使用第三方服务时应遵守其各自的政策。</li>
</ol>
<hr>
<p>*本政策版本：v1.0 ｜ 生效日期：2026年9月19日*</p></section><section id='agreement' class='doc'><h1>拾页 用户协议（服务条款）</h1>
<p><strong>版本号：v1.0</strong> <strong>生效日期：2026年9月19日</strong></p>
<hr>
<h2>引言</h2>
<p>欢迎使用拾页（以下简称"本 App"）。</p>
<p><strong>本协议是你与本 App 之间就使用本 App 服务所订立的协议。</strong> 请你务必审慎阅读、充分理解各条款内容。</p>
<p><strong>你点击"同意"或开始使用本 App，即表示你已阅读并同意本协议全部内容。</strong> <strong>若你不同意本协议任何内容，请停止使用本 App。</strong></p>
<hr>
<h2>一、服务说明</h2>
<h3>1.1 服务内容</h3>
<p>本 App 是一款面向学生的手写笔记数字化整理工具，提供以下功能：</p>
<ol>
<li><strong>笔记数字化</strong>：拍摄或上传纸质手写笔记，通过文字识别（OCR）转换为可编辑文本；</li>
<li><strong>人工校对</strong>：你可手动修正识别结果，修正后内容会更新检索索引；</li>
<li><strong>笔记管理</strong>：按学科、章节组织笔记，支持全文检索；</li>
<li><strong>AI 辅助</strong>：生成学习诊断报告、生成练习题、判分、笔记结构化整理；</li>
<li><strong>导出</strong>：将笔记导出为 Markdown / 纯文本文件。</li>
</ol>
<h3>1.2 ⚠️ 服务阶段与能力边界（<strong>请务必阅读</strong>）</h3>
<ol>
<li><strong>本 App 目前处于内测阶段</strong>，功能可能不完善、可能变更、可能中断，且**不承诺数据</li>
</ol>
<p>永久保存<strong>。内测期间请</strong>不要将本 App 作为你笔记的唯一存储方式**， 重要笔记请自行另行备份。</p>
<ol>
<li><strong>AI 与 OCR 的输出结果可能存在错误</strong>。文字识别可能识别错误，AI 分析结论仅供参考，</li>
</ol>
<p><strong>不构成任何学习建议、专业意见或对成绩的承诺</strong>。请你务必自行核对重要内容。</p>
<ol>
<li><strong>本 App 提供的练习题与判分由 AI 生成，可能存在错误</strong>，仅可作为自测参考。</li>
<li>本 App <strong>不提供云端托管服务</strong>。当前版本采用私有化部署模式，服务可用性取决于</li>
</ol>
<p>你所连接的服务器状态。</p>
<h3>1.3 关于服务器与数据可用性</h3>
<p>本 App 的连接地址由你或服务提供方配置。<strong>当服务器关闭、网络中断或地址变更时， 你可能无法访问你的笔记数据。</strong> 因服务器状态导致的服务不可用，本 App 不承担赔偿责任。</p>
<hr>
<h2>二、账号与安全</h2>
<h3>2.1 账号的建立</h3>
<ol>
<li>本 App 目前采用<strong>邀请码 + 设备标识</strong>的方式建立账号。</li>
<li><strong>你的账号标识由设备本地随机生成，不是手机号，也不是硬件标识。</strong></li>
<li>你需要填写昵称以完成账号创建。</li>
</ol>
<h3>2.2 ⚠️ 账号的重要特性（<strong>请特别注意</strong>）</h3>
<ol>
<li><strong>账号与设备绑定</strong>：账号标识与你的设备本地存储绑定。</li>
<li><strong>卸载重装即变新账号</strong>：**如果你卸载本 App 或清除应用数据，账号标识将永久丢失，</li>
</ol>
<p>你将无法访问原账号下的全部笔记数据。此操作不可恢复。**</p>
<ol>
<li><strong>请勿卸载</strong>：如需更新版本，请使用<strong>覆盖安装</strong>方式，不要卸载后重装。</li>
<li>本 App <strong>无法通过手机号、邮箱等方式找回账号</strong>。请妥善保管你的设备与数据。</li>
</ol>
<h3>2.3 账号安全</h3>
<ol>
<li>你应妥善保管你的设备与邀请码。<strong>邀请码请勿对外泄露</strong>，拿到邀请码的人可以使用</li>
</ol>
<p>本 App。</p>
<ol>
<li>你应对通过你的账号进行的所有活动负责。</li>
<li>如你发现账号被他人使用，请立即通过第九节方式联系我们。</li>
</ol>
<hr>
<h2>三、用户行为规范</h2>
<h3>3.1 你承诺不得利用本 App 从事以下行为</h3>
<ol>
<li>上传、存储、传播任何违反中华人民共和国法律法规的内容，包括但不限于：</li>
<li class='sub'>反对宪法确定的基本原则的；</li>
<li class='sub'>危害国家安全、泄露国家秘密、颠覆国家政权、破坏国家统一的；</li>
<li class='sub'>煽动民族仇恨、民族歧视，破坏民族团结的；</li>
<li class='sub'>宣扬邪教和封建迷信的；</li>
<li class='sub'>散布淫秽、色情、赌博、暴力、凶杀、恐怖或者教唆犯罪的；</li>
<li class='sub'>侮辱或者诽谤他人，侵害他人合法权益的。</li>
<li>上传包含他人隐私或个人信息的内容，<strong>除非你已获得合法授权</strong>；</li>
<li>上传包含商业机密、试卷原题等受保护内容；</li>
<li>使用自动化程序批量请求、恶意消耗服务器资源、攻击或试图攻击本 App 服务；</li>
<li>绕过或试图绕过本 App 的安全机制、权限控制；</li>
<li>对本 App 进行反向工程、反编译、破解；</li>
<li>其他违反法律法规、公序良俗或损害他人合法权益的行为。</li>
</ol>
<h3>3.2 违规处理</h3>
<p>如你违反上述规范，我们有权采取以下措施：</p>
<ol>
<li>删除相关内容；</li>
<li>暂停或终止向你提供服务；</li>
<li>向有关监管部门报告；</li>
<li>追究你的法律责任。</li>
</ol>
<p><strong>因你的违规行为导致的一切后果由你自行承担。</strong></p>
<hr>
<h2>四、知识产权</h2>
<h3>4.1 你的内容归你所有</h3>
<ol>
<li><strong>你上传的笔记图片、笔记文本等内容的著作权归你（或原始权利人）所有。</strong></li>
</ol>
<p>我们不会因你使用本 App 而获得你内容的所有权。</p>
<ol>
<li>为实现服务功能，你<strong>授权我们</strong>对你的内容进行必要的处理（如识别、存储、传输至</li>
</ol>
<p>第三方 OCR/AI 服务、生成索引等）。该授权仅限于提供本 App 服务所必需的范围。</p>
<ol>
<li><strong>你有责任确保你上传的内容不侵犯他人权利。</strong> 因你的内容引发的知识产权纠纷，</li>
</ol>
<p>由你自行承担。</p>
<h3>4.2 本 App 的知识产权</h3>
<ol>
<li>本 App 的软件、界面设计、图标、文档等内容的著作权、商标权及其他知识产权</li>
</ol>
<p><strong>归本 App 开发者所有</strong>。</p>
<ol>
<li>未经书面许可，你不得复制、修改、传播、出售本 App 或其任何部分。</li>
</ol>
<h3>4.3 AI 生成内容</h3>
<ol>
<li>通过本 App 的 AI 功能生成的内容（如学情报告、练习题、整理稿），</li>
</ol>
<p><strong>仅供你个人学习使用</strong>。</p>
<ol>
<li>你理解并同意：AI 生成内容可能存在错误或不准确之处，</li>
</ol>
<p><strong>我们不对其准确性、适用性作任何保证</strong>。</p>
<hr>
<h2>五、免责声明</h2>
<h3>5.1 服务"按现状"提供</h3>
<p>本 App 服务按<strong>"现状"</strong>和<strong>"现有"</strong>基础提供。我们<strong>不作任何明示或默示的保证</strong>， 包括但不限于适销性、特定用途适用性、不侵权的保证。</p>
<h3>5.2 我们不承担以下责任</h3>
<p>在法律允许的最大范围内，我们对以下情形不承担责任：</p>
<ol>
<li><strong>数据丢失</strong>：因你卸载 App、清除数据、设备损坏、误操作等导致的数据丢失；</li>
<li><strong>服务中断</strong>：因服务器故障、网络问题、第三方服务（百度、DeepSeek）不可用、</li>
</ol>
<p>不可抗力等导致的服务中断或数据不可访问；</p>
<ol>
<li><strong>AI/OCR 结果错误</strong>：因识别或 AI 生成结果不准确造成的任何损失</li>
</ol>
<p>（<strong>请你务必自行核对重要内容</strong>）；</p>
<ol>
<li><strong>第三方服务问题</strong>：因百度智能云、DeepSeek 等第三方服务的故障、变更、停止运营</li>
</ol>
<p>导致的功能不可用；</p>
<ol>
<li><strong>间接损失</strong>：任何间接的、附带的、特殊的、惩罚性的损失或利润损失。</li>
</ol>
<h3>5.3 关于内测阶段的特别声明</h3>
<p><strong>本 App 处于内测阶段，可能存在未知缺陷。</strong> 我们不对内测期间的数据安全、 服务连续性做任何承诺。<strong>请不要将本 App 作为重要笔记的唯一保存方式。</strong></p>
<hr>
<h2>六、服务的变更、中断与终止</h2>
<ol>
<li>我们有权根据实际情况<strong>变更、暂停或终止</strong>本 App 的全部或部分服务，</li>
</ol>
<p>并将尽可能提前通知。</p>
<ol>
<li>我们有权<strong>更新本 App 版本</strong>。部分更新可能要求你安装新版本才能继续使用。</li>
<li>你可以随时通过<strong>注销账号</strong>或<strong>卸载本 App</strong>终止使用本服务。</li>
<li>服务终止后，我们将按《隐私政策》第五节的约定处理你的个人信息。</li>
</ol>
<hr>
<h2>七、协议的更新</h2>
<ol>
<li>我们可能适时修订本协议。</li>
<li>协议修订后，我们将在本页面更新版本号与更新日期。</li>
<li><strong>重大变更</strong>我们将在 App 内以显著方式提示。</li>
<li>你继续使用本 App 即表示接受修订后的协议；如你不同意，请停止使用。</li>
</ol>
<hr>
<h2>八、法律适用与争议解决</h2>
<ol>
<li>本协议的订立、执行、解释及争议解决均适用<strong>中华人民共和国法律</strong>。</li>
<li>因本协议产生的争议，双方应友好协商解决；协商不成的，</li>
</ol>
<p>可向<strong>有管辖权的人民法院</strong>提起诉讼。</p>
<hr>
<h2>九、联系我们</h2>
<ul>
<li><strong>联系邮箱</strong>：contact&#64;example.com</li>
<li><strong>响应时限</strong>：我们将在收到你的问题后 <strong>15 个工作日内</strong>予以答复</li>
</ul>
<hr>
<h2>十、其他</h2>
<ol>
<li>本协议自 2026 年 9 月 19 日起生效。</li>
<li>如本协议任何条款被认定无效或不可执行，其余条款仍然有效。</li>
<li>本协议的标题仅为方便阅读，不影响条款的含义或解释。</li>
</ol>
<hr>
<p>*本协议版本：v1.0 ｜ 生效日期：2026年9月19日*</p></section><section id='third-party' class='doc'><h1>拾页 第三方信息共享清单</h1>
<p><strong>版本号：v1.0</strong> <strong>生效日期：2026年9月19日</strong></p>
<hr>
<h2>说明</h2>
<p>为实现本 App 的核心功能，我们需要将部分信息共享给第三方服务商。 本清单列明所有涉及个人信息共享的第三方，以及共享的具体内容。</p>
<p><strong>重要提示</strong>：除本清单列明的第三方外，本 App <strong>不会</strong>向任何其他第三方提供你的个人信息。</p>
<hr>
<h2>一、第三方共享一览表</h2>
<div class='tw'><table>
<thead><tr><th>序号</th><th>第三方名称</th><th>共享信息</th><th>共享目的</th><th>触发场景</th></tr></thead>
<tbody>
<tr><td>1</td><td><strong>北京百度网讯科技有限公司</strong>（百度智能云）</td><td>你上传的<strong>笔记图片（完整图片）</strong></td><td>手写文字识别（OCR）</td><td>使用笔记识别功能时</td></tr>
<tr><td>2</td><td><strong>杭州深度求索人工智能基础技术研究有限公司</strong>（DeepSeek）</td><td>你的<strong>笔记文本内容</strong>（标题、正文摘要、统计数据、作答内容）</td><td>学情分析、出题、判分、笔记整理</td><td>使用 AI 功能时</td></tr>
</tbody></table></div>
<hr>
<h2>二、第三方详情</h2>
<h3>2.1 百度智能云（文字识别服务）</h3>
<div class='tw'><table>
<thead><tr><th>项</th><th>内容</th></tr></thead>
<tbody>
<tr><td><strong>第三方名称</strong></td><td>北京百度网讯科技有限公司</td></tr>
<tr><td><strong>产品/服务名</strong></td><td>百度智能云 · 手写文字识别</td></tr>
<tr><td><strong>共享的信息类型</strong></td><td>你上传的笔记图片（图片完整内容，Base64 编码后传输）</td></tr>
<tr><td><strong>共享的信息范围</strong></td><td>仅你在本 App 内主动上传的那张/那几张图片</td></tr>
<tr><td><strong>共享目的</strong></td><td>将手写笔记图片转换为可检索的文本内容</td></tr>
<tr><td><strong>共享方式</strong></td><td>通过加密网络接口（HTTPS）传输至百度服务器处理</td></tr>
<tr><td><strong>触发条件</strong></td><td><strong>仅当你使用拍照/上传笔记识别功能时</strong></td></tr>
<tr><td><strong>是否包含敏感个人信息</strong></td><td>可能包含（取决于你上传的笔记内容）</td></tr>
<tr><td><strong>所涉权限</strong></td><td>相机、相册（用于获取图片）</td></tr>
<tr><td><strong>第三方隐私政策</strong></td><td><a href="https://cloud.baidu.com/doc/Agreements/s/djwvy2q7n" target="_blank" rel="noopener">https://cloud.baidu.com/doc/Agreements/s/djwvy2q7n</a></td></tr>
</tbody></table></div>
<p><strong>你的选择</strong>：如果你不希望笔记图片被发送至百度，请<strong>不要使用拍照/上传识别功能</strong>。 此时你可以手动录入笔记文字（如产品支持），但无法使用自动识别。</p>
<hr>
<h3>2.2 DeepSeek（AI 分析服务）</h3>
<div class='tw'><table>
<thead><tr><th>项</th><th>内容</th></tr></thead>
<tbody>
<tr><td><strong>第三方名称</strong></td><td>杭州深度求索人工智能基础技术研究有限公司</td></tr>
<tr><td><strong>产品/服务名</strong></td><td>DeepSeek 大语言模型 API</td></tr>
<tr><td><strong>共享的信息类型</strong></td><td>笔记文本内容，具体范围<strong>因功能而异</strong>：&lt;br&gt;· <strong>AI 整理笔记</strong> → 该页 / 该章的<strong>识别文本全文</strong>&lt;br&gt;· 学情分析 / 出题 / 判分 → 笔记标题 + 每页正文摘要（<strong>每页最多前 120 字，最多 60 页</strong>）+ 统计数据 + 你的作答内容</td></tr>
<tr><td><strong>共享的信息范围</strong></td><td>仅涵盖你已上传笔记的<strong>文本</strong>部分，<strong>不包含图片</strong></td></tr>
<tr><td><strong>共享目的</strong></td><td>① 生成学情分析报告&lt;br&gt;② 生成练习题&lt;br&gt;③ 判分与诊断&lt;br&gt;④ 笔记结构化整理</td></tr>
<tr><td><strong>共享方式</strong></td><td>通过加密网络接口（HTTPS）传输至 DeepSeek 服务器处理</td></tr>
<tr><td><strong>触发条件</strong></td><td><strong>仅当你主动使用 AI 功能时</strong>（学情分析 / 答题测评 / AI 整理）</td></tr>
<tr><td><strong>是否包含敏感个人信息</strong></td><td>可能包含（取决于你的笔记内容）</td></tr>
<tr><td><strong>所涉权限</strong></td><td>无（仅使用已存储的文本数据）</td></tr>
<tr><td><strong>第三方隐私政策</strong></td><td><a href="https://platform.deepseek.com/downloads/DeepSeek%20Privacy%20Policy.html" target="_blank" rel="noopener">https://platform.deepseek.com/downloads/DeepSeek%20Privacy%20Policy.html</a></td></tr>
</tbody></table></div>
<p><strong>你的选择</strong>：如果你不希望笔记文本被发送至 DeepSeek，请<strong>不要使用 AI 相关功能</strong>。 不使用 AI 功能不影响笔记的识别、存储、检索与导出。</p>
<hr>
<h2>三、本 App 未使用的第三方服务</h2>
<p>为避免误解，特此声明，本 App <strong>未集成</strong>以下类型的第三方服务：</p>
<div class='tw'><table>
<thead><tr><th>服务类型</th><th>是否使用</th></tr></thead>
<tbody>
<tr><td>广告联盟 / 广告 SDK</td><td>❌ 未使用</td></tr>
<tr><td>用户行为统计分析 SDK（如友盟、神策等）</td><td>❌ 未使用</td></tr>
<tr><td>崩溃收集 SDK（如 Bugly、Firebase Crashlytics）</td><td>❌ 未使用</td></tr>
<tr><td>推送通知 SDK（如极光、个推）</td><td>❌ 未使用</td></tr>
<tr><td>社交分享 SDK</td><td>❌ 未使用</td></tr>
<tr><td>地图 / 定位 SDK</td><td>❌ 未使用</td></tr>
<tr><td>支付 SDK</td><td>❌ 未使用</td></tr>
</tbody></table></div>
<p><strong>本 App 不包含任何广告，不进行用户行为追踪。</strong></p>
<hr>
<h2>四、关于私有化部署的说明</h2>
<p>本 App 采用私有化部署模式，你的笔记数据存储在你自行部署的服务器上。 但请注意：</p>
<ul>
<li><strong>OCR 与 AI 功能依赖第三方云服务</strong>（百度、DeepSeek），这是实现该功能的必要前提；</li>
<li>若你希望完全避免数据外发，可以选择不使用 AI 相关功能，或选择本地 OCR 引擎</li>
</ul>
<p>（如部署方配置了本地识别方案，此时图片不外发，识别效果可能有所不同）。</p>
<hr>
<h2>五、清单的更新</h2>
<ol>
<li>如本 App 新增或变更第三方合作方，我们将在本页面更新本清单，</li>
</ol>
<p>并在<strong>涉及个人信息共享的重大变更</strong>时通过弹窗方式重新征求你的同意。</p>
<ol>
<li>你可以随时在「我的 → 第三方信息共享清单」查看本清单的最新版本。</li>
</ol>
<hr>
<h2>六、联系我们</h2>
<p>如你对本清单有疑问，请联系：</p>
<ul>
<li><strong>联系邮箱</strong>：contact&#64;example.com</li>
<li><strong>响应时限</strong>：15 个工作日内答复</li>
</ul>
<hr>
<p>*本清单版本：v1.0 ｜ 生效日期：2026年9月19日*</p></section><section id='data-collection' class='doc'><h1>拾页 个人信息收集清单</h1>
<p><strong>版本号：v1.0</strong> <strong>生效日期：2026年9月19日</strong></p>
<hr>
<h2>说明</h2>
<p>根据《中华人民共和国个人信息保护法》及相关监管要求，本清单逐项列明本 App 收集的 全部个人信息，以及收集的目的、方式和范围。</p>
<p><strong>本 App 仅收集实现功能所必需的最少信息。</strong></p>
<hr>
<h2>一、收集清单一览表</h2>
<div class='tw'><table>
<thead><tr><th>序号</th><th>信息项</th><th>收集方式</th><th>收集目的</th><th>必要性</th><th>拒绝的后果</th></tr></thead>
<tbody>
<tr><td>1</td><td><strong>账号标识</strong></td><td>设备本地自动生成</td><td>建立并识别账号</td><td><strong>必要</strong></td><td>无法使用本 App</td></tr>
<tr><td>2</td><td><strong>昵称</strong></td><td>你主动填写</td><td>App 内标识你的账号</td><td><strong>必要</strong></td><td>无法完成账号创建</td></tr>
<tr><td>3</td><td><strong>笔记图片</strong></td><td>你主动拍照/选择</td><td>文字识别、数字化存储</td><td><strong>必要</strong></td><td>无法使用识别功能</td></tr>
<tr><td>4</td><td><strong>笔记识别文本</strong></td><td>识别后自动生成</td><td>检索、校对、AI 分析</td><td><strong>必要</strong></td><td>无法使用检索功能</td></tr>
<tr><td>5</td><td><strong>笔记标题</strong></td><td>你主动填写（可选）</td><td>组织笔记</td><td>非必要</td><td>仅影响笔记管理便利性</td></tr>
<tr><td>6</td><td><strong>学科/章节名称</strong></td><td>你主动创建</td><td>分类整理</td><td>非必要</td><td>仅影响分类便利性</td></tr>
<tr><td>7</td><td><strong>AI 整理结果</strong></td><td>你主动使用功能后生成</td><td>结构化笔记</td><td>非必要</td><td>无影响</td></tr>
<tr><td>8</td><td><strong>学习统计数据</strong></td><td>使用学情功能时计算</td><td>生成诊断报告</td><td>非必要</td><td>无法使用学情功能</td></tr>
<tr><td>9</td><td><strong>答题作答内容</strong></td><td>你主动填写</td><td>判分与诊断</td><td>非必要</td><td>无法使用测评功能</td></tr>
</tbody></table></div>
<hr>
<h2>二、逐项详细说明</h2>
<h3>2.1 账号标识</h3>
<div class='tw'><table>
<thead><tr><th>项</th><th>内容</th></tr></thead>
<tbody>
<tr><td><strong>信息内容</strong></td><td><code>dev_</code> 开头的 32 位随机十六进制字符串，例如 <code>dev_a3f8...</code></td></tr>
<tr><td><strong>收集方式</strong></td><td>由<strong>你的设备在本地</strong>使用安全随机数生成器生成</td></tr>
<tr><td><strong>收集时机</strong></td><td>首次登录时</td></tr>
<tr><td><strong>存储位置</strong></td><td>设备本地 + 服务器（作为账号唯一标识）</td></tr>
<tr><td><strong>收集目的</strong></td><td>建立账号、关联你的笔记数据、实现数据隔离</td></tr>
<tr><td><strong>必要性</strong></td><td><strong>必要</strong>（没有它无法识别账号）</td></tr>
<tr><td><strong>是否属于敏感个人信息</strong></td><td>否</td></tr>
<tr><td><strong>特别说明</strong></td><td><strong>这不是手机硬件标识</strong>（非 IMEI / Android ID / MAC 地址）。&lt;br&gt;<strong>卸载本 App 后永久失效且不可恢复。</strong></td></tr>
</tbody></table></div>
<h3>2.2 昵称</h3>
<div class='tw'><table>
<thead><tr><th>项</th><th>内容</th></tr></thead>
<tbody>
<tr><td><strong>信息内容</strong></td><td>你填写的文本（最多 100 字符）</td></tr>
<tr><td><strong>收集方式</strong></td><td>你在登录时或「我的 → 修改昵称」主动填写</td></tr>
<tr><td><strong>收集目的</strong></td><td>在 App 内标识你的账号</td></tr>
<tr><td><strong>必要性</strong></td><td>必要（账号创建所需）</td></tr>
<tr><td><strong>是否属于敏感个人信息</strong></td><td>否</td></tr>
<tr><td><strong>你的控制</strong></td><td>可随时修改；可注销账号删除</td></tr>
</tbody></table></div>
<h3>2.3 笔记图片</h3>
<div class='tw'><table>
<thead><tr><th>项</th><th>内容</th></tr></thead>
<tbody>
<tr><td><strong>信息内容</strong></td><td>你拍摄或选择的笔记照片</td></tr>
<tr><td><strong>收集方式</strong></td><td>你主动点击"拍照"或"从相册选择"</td></tr>
<tr><td><strong>收集时机</strong></td><td><strong>仅在你主动操作时</strong>（不会后台自动获取）</td></tr>
<tr><td><strong>存储位置</strong></td><td><strong>你自行部署的服务器</strong></td></tr>
<tr><td><strong>收集目的</strong></td><td>① 文字识别（OCR）② 供你随时查看原始笔记</td></tr>
<tr><td><strong>必要性</strong></td><td>必要（本 App 核心功能）</td></tr>
<tr><td><strong>是否属于敏感个人信息</strong></td><td>可能涉及（取决于笔记内容）</td></tr>
<tr><td><strong>是否会外发</strong></td><td><strong>会</strong> —— 使用识别功能时发送至百度智能云（见《第三方信息共享清单》）</td></tr>
<tr><td><strong>你的控制</strong></td><td>可删除单篇笔记（图片文件一并物理删除）</td></tr>
</tbody></table></div>
<h3>2.4 笔记识别文本（OCR 文本）</h3>
<div class='tw'><table>
<thead><tr><th>项</th><th>内容</th></tr></thead>
<tbody>
<tr><td><strong>信息内容</strong></td><td>由图片识别出的文字内容</td></tr>
<tr><td><strong>收集方式</strong></td><td>识别完成后自动生成</td></tr>
<tr><td><strong>收集目的</strong></td><td>① 文字检索 ② 供你人工校对 ③ 作为 AI 分析的输入</td></tr>
<tr><td><strong>必要性</strong></td><td>必要</td></tr>
<tr><td><strong>是否会外发</strong></td><td><strong>会</strong> —— 使用 AI 功能时，其摘要部分发送至 DeepSeek</td></tr>
<tr><td><strong>你的控制</strong></td><td>可在笔记详情页<strong>直接编辑修正</strong>；可删除笔记</td></tr>
</tbody></table></div>
<h3>2.5 笔记标题 / 学科名称 / 章节名称</h3>
<div class='tw'><table>
<thead><tr><th>项</th><th>内容</th></tr></thead>
<tbody>
<tr><td><strong>收集方式</strong></td><td>你主动输入或修改</td></tr>
<tr><td><strong>收集目的</strong></td><td>笔记的组织与分类</td></tr>
<tr><td><strong>必要性</strong></td><td>非必要（不填不影响核心功能）</td></tr>
<tr><td><strong>是否外发</strong></td><td>笔记标题会随 AI 分析发送至 DeepSeek；学科/章节名称不外发</td></tr>
</tbody></table></div>
<h3>2.6 AI 整理结果</h3>
<div class='tw'><table>
<thead><tr><th>项</th><th>内容</th></tr></thead>
<tbody>
<tr><td><strong>信息内容</strong></td><td>AI 生成的笔记结构化文本</td></tr>
<tr><td><strong>收集方式</strong></td><td>你主动点击"AI 整理"后生成</td></tr>
<tr><td><strong>收集目的</strong></td><td>供你查看与导出结构化的笔记内容</td></tr>
<tr><td><strong>必要性</strong></td><td>非必要</td></tr>
<tr><td><strong>是否会外发</strong></td><td><strong>会</strong> —— 使用 AI 整理时，<strong>该页/该章的识别文本全文</strong>会发送至 DeepSeek</td></tr>
<tr><td><strong>你的控制</strong></td><td>可编辑；可删除笔记</td></tr>
</tbody></table></div>
<h3>2.7 学习统计数据</h3>
<div class='tw'><table>
<thead><tr><th>项</th><th>内容</th></tr></thead>
<tbody>
<tr><td><strong>信息内容</strong></td><td>笔记页数、记录趋势等<strong>由你的笔记自动计算</strong>的统计值</td></tr>
<tr><td><strong>收集方式</strong></td><td>使用学情功能时在服务器端计算</td></tr>
<tr><td><strong>收集目的</strong></td><td>生成学习诊断报告</td></tr>
<tr><td><strong>必要性</strong></td><td>非必要</td></tr>
<tr><td><strong>是否外发</strong></td><td>会（作为 AI 分析的输入发送至 DeepSeek）</td></tr>
</tbody></table></div>
<h3>2.8 答题作答内容</h3>
<div class='tw'><table>
<thead><tr><th>项</th><th>内容</th></tr></thead>
<tbody>
<tr><td><strong>信息内容</strong></td><td>你在答题测评中填写的答案文本</td></tr>
<tr><td><strong>收集方式</strong></td><td>你主动填写并提交</td></tr>
<tr><td><strong>收集目的</strong></td><td>判分与生成针对性建议</td></tr>
<tr><td><strong>必要性</strong></td><td>非必要</td></tr>
<tr><td><strong>是否外发</strong></td><td>会（发送至 DeepSeek 判分）</td></tr>
<tr><td><strong>长度限制</strong></td><td>每题最多 2000 字</td></tr>
</tbody></table></div>
<hr>
<h2>三、本 App 不收集的信息</h2>
<p><strong>本 App 明确不收集、不访问以下信息：</strong></p>
<div class='tw'><table>
<thead><tr><th>信息类型</th><th>状态</th></tr></thead>
<tbody>
<tr><td>地理位置 / GPS 定位</td><td>❌ 不收集</td></tr>
<tr><td>通讯录、通话记录、短信</td><td>❌ 不收集</td></tr>
<tr><td>剪贴板内容</td><td>❌ 不收集</td></tr>
<tr><td>相册全量内容</td><td>❌ 不访问（仅在你选择时访问你选中的图片）</td></tr>
<tr><td>设备硬件标识（IMEI / Android ID / MAC）</td><td>❌ 不收集</td></tr>
<tr><td>手机号码</td><td>❌ 不收集</td></tr>
<tr><td>身份证件信息</td><td>❌ 不收集</td></tr>
<tr><td>银行卡 / 支付信息</td><td>❌ 不收集</td></tr>
<tr><td>已安装应用列表</td><td>❌ 不收集</td></tr>
<tr><td>传感器数据</td><td>❌ 不收集</td></tr>
<tr><td>生物识别信息（指纹 / 人脸）</td><td>❌ 不收集</td></tr>
<tr><td>用户行为轨迹 / 跨应用追踪</td><td>❌ 不进行</td></tr>
</tbody></table></div>
<hr>
<h2>四、权限申请清单</h2>
<div class='tw'><table>
<thead><tr><th>权限名称</th><th>申请时机</th><th>用途</th><th>拒绝的后果</th></tr></thead>
<tbody>
<tr><td><strong>网络访问</strong></td><td>应用启动（系统自动）</td><td>与服务器通信</td><td>无法使用本 App</td></tr>
<tr><td><strong>相机</strong></td><td>你点击"拍照"时</td><td>拍摄纸质笔记</td><td>仅无法拍照，可改用相册</td></tr>
<tr><td><strong>相册/存储</strong></td><td>你点击"从相册选择"时</td><td>选择笔记照片</td><td>仅无法从相册选图，可改用拍照</td></tr>
</tbody></table></div>
<p><strong>本 App 不会在启动时预申请相机或相册权限。</strong></p>
<hr>
<h2>五、本地存储清单</h2>
<p>以下信息保存在<strong>你的设备本地</strong>，不上传至服务器：</p>
<div class='tw'><table>
<thead><tr><th>存储项</th><th>用途</th><th>卸载后</th></tr></thead>
<tbody>
<tr><td>登录凭证（Token）</td><td>保持登录状态</td><td>清除</td></tr>
<tr><td>账号标识</td><td>识别账号</td><td><strong>永久失效</strong></td></tr>
<tr><td>隐私政策同意状态</td><td>避免重复弹窗</td><td>清除</td></tr>
<tr><td>笔记整理结果缓存</td><td>减少重复请求</td><td>清除</td></tr>
</tbody></table></div>
<hr>
<h2>六、你对个人信息的控制</h2>
<div class='tw'><table>
<thead><tr><th>权利</th><th>操作路径</th></tr></thead>
<tbody>
<tr><td>查看</td><td>App 内各页面直接查看</td></tr>
<tr><td>更正识别文本</td><td>笔记详情页 → 编辑</td></tr>
<tr><td>更正昵称</td><td>我的 → 修改昵称</td></tr>
<tr><td>删除单篇笔记</td><td>笔记详情页 → 删除</td></tr>
<tr><td>删除学科（含其下全部笔记）</td><td>学科列表 → 长按 → 删除</td></tr>
<tr><td><strong>注销账号（删除全部数据）</strong></td><td>我的 → 账号 → 注销账号</td></tr>
<tr><td>撤回同意</td><td>我的 → 隐私政策 → 撤回同意</td></tr>
</tbody></table></div>
<hr>
<h2>七、联系我们</h2>
<p>如你对本清单有疑问，或需要行使上述权利，请联系：</p>
<ul>
<li><strong>联系邮箱</strong>：contact&#64;example.com</li>
<li><strong>响应时限</strong>：15 个工作日内答复</li>
</ul>
<hr>
<p>*本清单版本：v1.0 ｜ 生效日期：2026年9月19日*</p></section>
</main>
<footer>拾页 · 手写笔记整理 App<br>生效日期：2026年9月19日 ｜ 联系邮箱：contact&#64;example.com</footer>
</body>
</html>
"""
