# 折腾了一个 YouTube Shorts 自动互动插件，记录一下踩坑过程

上回搞完公众号自动留言的脚本后，想着能不能把 YouTube Shorts 也自动化一下。每天刷视频的时候，看到有意思的就想点个赞、留个言，但一个个手动操作太费时间了。

正好最近在学 Chrome 扩展开发，就想着做个插件，让它自动帮我判断视频值不值得互动，然后自动执行操作。

结果这一趟下来，踩的坑比之前公众号那个还多。写篇文章记录一下，也给想搞类似东西的朋友避个雷。

## 从想法到第一版

最开始的想法很简单：检测视频切换 → 提取标题和描述 → 发给 LLM 判断 → 自动点赞/订阅/评论。

我让 AI 帮我写了个开发计划，把功能拆解成几个模块：
- Content Script：在 YouTube 页面上跑，负责提取信息和执行操作
- Service Worker：后台服务，负责调用 LLM API
- Popup：简单的开关界面
- Options：配置页面

框架搭起来倒是挺快，AI 写代码确实比我自己手敲快多了。但真正跑起来，问题就一个接一个地来了。

## 第一个坑：选择器失效

YouTube 的页面结构经常变，这是最头疼的。

刚开始，AI 给的选择器是这样的：
```javascript
title: 'ytd-reel-video-renderer[is-active] #title'
```

结果一运行，啥也提取不到。打开控制台一看，`title` 是空的。

我截图给 AI 看，它说 YouTube 的 UI 更新了，选择器得改。然后给了新的：
```javascript
title: 'ytd-reel-video-renderer[is-active] .ytReelMultiFormatLinkViewModelTitle span'
```

这次能提取到标题了，但有时候还是不行。后来 AI 干脆给了个数组，把可能的选择器都列出来，按顺序试，哪个能取到用哪个。这招挺管用，至少不会因为一个选择器失效就完全抓瞎了。

这就好比我们做工程，不能只依赖一个测量点，得多设几个控制点，互相校核。

## 第二个坑：CORS 限制

这个坑最隐蔽，也最让人抓狂。

我用的本地 Ollama 跑 LLM，地址是 `http://localhost:11434/v1`。插件里调用的时候，直接报 403 错误。

一开始我以为 Ollama 没启动，检查了一下，服务是正常的。用 curl 测试也能连上。

然后我怀疑是 API 路径不对，试了 `/v1/chat/completions`、`/api/chat`，都不行。

折腾了半天，AI 提醒我：Chrome 扩展跨域请求需要配置 CORS。Ollama 默认不允许浏览器插件访问。

解决方法是启动 Ollama 的时候加个环境变量：
```bash
OLLAMA_ORIGINS="*" ollama serve
```

加了这个之后，403 错误就消失了。

但问题是，这个错误提示太不友好了。403 就是 403，谁知道是 CORS 的问题？后来我在测试连接的代码里加了专门的错误提示，如果检测到 403，就明确告诉用户要设置 `OLLAMA_ORIGINS`。

## 第三个坑：描述提取不稳定

最开始的设计里，是要提取视频标题、描述和频道名的。描述用来给 LLM 做判断依据。

但实际跑起来发现，描述的提取特别不稳定。有时候能提取到，有时候提取不到，有时候提取到的是频道名。

我试了好几种选择器，都不太理想。YouTube 的页面结构太复杂了，描述可能在不同的地方，而且有些视频根本没有描述。

后来我想，标题其实已经包含足够的信息了。一个视频的标题通常就能说明它是讲什么的。而且很多 Shorts 视频的描述就是标题的重复，或者就是一堆标签。

跟 AI 商量了一下，决定把描述提取给砍了，只保留标题。这样代码更简单，也更稳定。

这个决定后来证明是对的。LLM 只根据标题判断，准确率也不低。而且代码少了很多，维护起来也轻松。

## 第四个坑：LLM 返回格式不一致

这个坑是慢慢发现的。

LLM 返回的 JSON 里，有个 `actions` 字段，用来指定要执行哪些操作。理论上应该是这样的：
```json
{
  "actions": {
    "subscribe": true,
    "like": true,
    "comment": true
  }
}
```

但实际运行中，有时候 LLM 返回的是：
```json
{
  "actions": "comment"
}
```

或者：
```json
{
  "actions": ["like", "comment"]
}
```

这就导致代码解析失败，或者执行出错。

一开始我以为是 Prompt 写得不够清楚，让 AI 改了几次。但 LLM 有时候就是会"自由发挥"，你让它输出 JSON，它可能给你来个字符串，或者数组。

后来干脆在代码里加了个格式归一化的逻辑：不管 LLM 返回什么格式，都统一转换成对象格式。这样即使 LLM "不听话"，代码也能正常跑。

```javascript
// 如果 actions 是字符串，转成对象
if (typeof actions === 'string') {
    const act = {};
    if (actions.includes('subscribe')) act.subscribe = true;
    if (actions.includes('like')) act.like = true;
    if (actions.includes('comment')) act.comment = true;
    actions = act;
}
// 如果 actions 是数组，也转成对象
else if (Array.isArray(actions)) {
    const act = {};
    if (actions.includes('subscribe')) act.subscribe = true;
    // ...
}
```

这就像我们做工程验收，不能指望施工方完全按图纸来，得有个容错机制。

## 第五个坑：评论输入框找不到

评论功能是最难搞的。

YouTube 的评论输入框不是普通的 `<input>`，而是个 `contenteditable` 的 div。而且有时候页面加载慢，输入框还没渲染出来，代码就去点了，结果找不到元素。

一开始的代码是这样的：
```javascript
const input = document.querySelector('#contenteditable-root');
input.focus();
```

但经常报错：`Cannot read property 'focus' of null`。

后来加了等待和重试：
```javascript
let input = null;
for (let i = 0; i < 3; i++) {
    input = document.querySelector('#contenteditable-root');
    if (input) break;
    await sleep(1000);
}
```

但还是有时候找不到。我发现有些情况下，需要先点一下 placeholder 区域，输入框才会激活。

所以又加了个逻辑：如果找不到输入框，就先找 placeholder，点一下，再等一会儿，再找输入框。

这样折腾了几轮，评论功能才算稳定下来。

## 第六个坑：自动划走功能

互动完成后，需要自动划到下一个视频。

YouTube Shorts 的切换是通过键盘事件实现的，按 `ArrowDown` 键就能切换到下一个。

代码很简单：
```javascript
const event = new KeyboardEvent('keydown', {
    key: 'ArrowDown',
    code: 'ArrowDown',
    keyCode: 40,
    bubbles: true
});
document.body.dispatchEvent(event);
```

但问题是，什么时候触发？

如果互动完立即划走，显得太假了。得等一会儿，模拟真人看完视频的反应时间。

我设置了两个延时：
- 如果 LLM 决定互动：互动完成后等 5-25 秒（随机），再划走
- 如果 LLM 决定跳过：等 3-6 秒（随机），再划走

这样看起来更自然一些。

## 最后的清理工作

功能都跑通后，代码已经有点乱了。有些注释掉的代码，有些临时调试的日志，有些已经不用但还没删的函数。

我让 AI 帮我整体梳理了一遍，把冗余的代码清理掉，把文档更新一下。

AI 建议把开发计划文档里的代码片段都改成文件路径引用，这样文档更简洁，代码和文档也不会不同步。

这个建议挺好的，我照做了。现在文档看起来清爽多了。

## 一些感想

这次开发下来，最大的感受是：**细节决定成败**。

看起来简单的功能，真正实现起来，到处都是细节。选择器失效、CORS 限制、格式不一致、元素找不到……每一个小问题都可能让整个功能瘫痪。

但反过来，把这些问题一个个解决掉，看着插件能稳定运行，那种成就感还是挺强的。

另外，AI 写代码确实快，但它也会犯错。比如选择器给错了、格式理解偏了，这些都需要人工去发现和纠正。

所以我现在用 AI 的方式是：让它写第一版，我来测试和调试。发现问题了，我再告诉它，让它改。这样迭代几轮，代码质量就上来了。

这就像我们做工程，不能完全依赖设计院，现场施工的时候，监理得盯着，发现问题及时反馈，设计院再调整。这样出来的工程才靠谱。

## 后续计划

现在插件基本能用了，但还有一些可以优化的地方：

1. 订阅状态的检测还不够准确，有时候会重复订阅。这个得再调调。
2. 评论内容有时候还是有点生硬，Prompt 还得再优化。
3. 选择器失效的问题，得定期维护。YouTube 一更新 UI，可能就得改。

不过总的来说，这个插件已经能帮我省不少时间了。每天打开 YouTube Shorts，让它自动跑，我该干嘛干嘛，过一会儿回来看看统计，还是挺爽的。

---

*代码已经整理好了，放在 `auto_helper/extension` 目录下。有兴趣的朋友可以看看，有问题欢迎交流。*
