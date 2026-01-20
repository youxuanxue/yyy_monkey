# 记录一次YouTube发布失败的排查过程

上周测试YouTube发布功能的时候遇到了网络问题，折腾了大半天才解决。把排查过程记录一下，遇到类似问题的朋友可以参考。

## 问题现象

点击发布按钮后，程序一直转圈，最后报错：

```
[ERROR] 网络错误: [Errno 60] Operation timed out
```

当时的环境：
- macOS系统
- 代理软件已开启（平时看YouTube视频没问题）
- WiFi正常，其他网站都能访问

## 排查过程

### 第一步：确认是不是代码问题

把报错信息发给AI，它说这个错误是连接YouTube服务器超时，可能是网络问题或者代理没生效。

我想代理明明开着啊，浏览器能正常访问YouTube。

AI建议设置环境变量：

```bash
export HTTP_PROXY="http://127.0.0.1:7890"
export HTTPS_PROXY="http://127.0.0.1:7890"
```

设置后再运行，还是超时。

### 第二步：测试代理本身有没有问题

AI让我用curl测试：

```bash
curl -x http://127.0.0.1:7890 -I https://www.googleapis.com/youtube/v3/
```

返回了`200 Connection established`，说明代理是通的。

又用Python测试：

```python
import urllib.request
import os
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7890'
urllib.request.urlopen('https://www.googleapis.com/youtube/v3/')
```

也能连上（返回404是正常的，说明请求到了服务器）。

所以代理没问题，Python也能走代理，那问题出在哪？

### 第三步：定位到具体的库

继续排查，发现问题出在Google的API库（google-api-python-client）上。

这个库底层用的是`httplib2`来发HTTP请求。而httplib2有个特点：它不读环境变量里的代理设置。

也就是说，你设置了`HTTP_PROXY`、`HTTPS_PROXY`，httplib2完全忽略，直接走直连。

试了几种方法让httplib2走代理：

- 用`httplib2.ProxyInfo`设置 → 不行
- Monkey-patch `httplib2.Http` → 不行
- 用`proxy_info_from_url` → 还是不行

从下午3点搞到6点，都没成功。

### 最终解决方案

最后AI提了个方案：不用httplib2，换成requests库。

requests会正常读取环境变量里的代理设置。

具体做法是写一个适配器，对外接口和httplib2一样，但内部用requests发请求：

```python
class RequestsHttpAdapter:
    def __init__(self, credentials=None, timeout=1800):
        self.session = requests.Session()
        proxy_url = os.environ.get('HTTPS_PROXY', '')
        if proxy_url:
            self.session.proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
```

换上这个适配器后，上传成功了。

## 总结一下踩的坑

1、代理软件开着不代表所有程序都走代理。很多代理软件默认只代理浏览器流量，终端程序需要单独设置环境变量。

2、就算设置了环境变量，也要看程序愿不愿意读。httplib2就是个不读环境变量的库。

3、遇到这种库，要么找它自己的代理配置方式，要么换一个库。

## 实操checklist

如果你也要做YouTube发布，检查以下几点：

### 测试代理是否可用

```bash
curl -x http://127.0.0.1:7890 -I https://www.googleapis.com/youtube/v3/
```

看到`200 Connection established`说明代理通了。端口号换成你自己的。

### 设置环境变量

在`~/.zshrc`或`~/.bashrc`里加上：

```bash
export HTTP_PROXY="http://127.0.0.1:7890"
export HTTPS_PROXY="http://127.0.0.1:7890"
export http_proxy="http://127.0.0.1:7890"
export https_proxy="http://127.0.0.1:7890"
```

大写小写都设上，不同程序读的变量名不一样。

### 常见报错

| 报错 | 原因 | 解决 |
|------|------|------|
| Operation timed out | 代理没生效 | 检查代理是否开启、环境变量是否设置 |
| Connection refused | 代理端口错误 | 确认代理软件的端口号 |
| 407 Proxy Authentication | 代理需要密码 | 用格式`http://user:pass@host:port` |

## 关于代理服务

既然提到代理，说一下我自己用的。

做YouTube、用ChatGPT这些都需要代理。我的要求就是稳定，不想每次用的时候还要折腾半天连不上。

目前用的是Shadowsocks，一年多了，基本没断过。速度够用，YouTube 1080p没问题。

链接：https://secure.shadowsocks.au/aff.php?aff=83130

市面上选择很多，找个稳定的就行。主要是别为了省几十块钱结果每次都折腾半天，时间成本更高。

---

这次排查花了大半天时间，主要卡在httplib2这个库上。虽然过程有点烦，但也学到了不少东西：环境变量怎么工作的、不同库对代理的处理方式、怎么用适配器模式解决兼容问题。

把过程记下来，希望能帮到遇到同样问题的人。

---

工具获取：后台回复「火箭」

懿起成长
