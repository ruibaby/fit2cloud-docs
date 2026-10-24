---
title: 常见问题
---

本页汇总 1Panel 技术交流群中用户咨询频率较高的常见问题及处理方式，内容持续更新。

## 1 安装部署

### 1.1 1Panel 安装脚本不支持 Anolis 系统怎么办？

**问题**：安装 1Panel 时提示安装脚本不支持 Anolis 系统，该怎么处理？

**处理方式**：

1Panel 安装脚本不支持 Anolis 系统，需更换为受支持的操作系统后再安装。1Panel 支持主流 Linux 发行版本（基于 Debian / RedHat，包括国产操作系统），常规 Ubuntu 等系统均支持。

## 2 主机与系统管理

### 2.1 1Panel 服务无法启动，报 GODEBUG "tlskyber" 错误怎么办？

**问题**：1Panel 服务无法启动，直接执行 `/usr/local/bin/1panel-core` 时报错：

```text
fatal error: removed GODEBUG "tlskyber" set to old value "0" in environment (https://go.dev/doc/godebug#go-124)
```

**处理方式**：

启动环境中存在新版 Go 已不支持的 `GODEBUG=tlskyber=0` 配置，按以下步骤处理。

**1. 排查配置来源**

```bash
sudo systemctl show-environment | grep '^GODEBUG='

sudo grep -RnsE 'GODEBUG|tlskyber' \
  /etc/systemd /run/systemd /usr/lib/systemd /lib/systemd \
  /etc/default /etc/sysconfig /etc/profile /etc/profile.d /etc/environment \
  2>/dev/null
```

**2. 修改对应配置文件**

如果 `/etc/systemd/system.conf` 中存在以下配置，删除或注释整行：

```ini
#DefaultEnvironment="GODEBUG=tlskyber=0"
```

如果包含其他环境变量或 GODEBUG 参数，只移除 `tlskyber=0` 对应的配置，保留其余内容。

**3. 重新加载并验证**

```bash
sudo systemctl daemon-reload
sudo systemctl show-environment | grep '^GODEBUG='
```

确认不再包含 `tlskyber=0` 后，重启服务：

```bash
1pctl restart
1pctl status
```

**注意**：修改全局配置会影响之后启动的其他服务；终端执行 `unset GODEBUG` 只影响当前终端，不能代替修改 systemd 配置。若不便改动全局配置，也可只在 `/etc/systemd/system` 下的 `1panel-core.service` 与 `1panel-agent.service` 中，为 `[Service]` 段补充 `UnsetEnvironment=GODEBUG`，使该变量不传入 1Panel 进程。

## 3 应用商店与容器

### 3.1 应用安装拉取镜像失败怎么办？

**问题**：安装应用时一直拉取不到镜像、提示 image pull failed，怎么处理？

**处理方式**：

应用安装失败、镜像拉取超时，可在【容器】-【配置】中配置镜像加速器进行优化，加速地址填写 `https://docker.1panel.live`。若配置后拉取应用镜像仍然失败，可在论坛中进一步讨论。

### 3.2 智能路由为什么没有生效？

**问题**：配置了智能路由，但请求没有走智能路由，是什么原因？

**处理方式**：

只有客户端请求使用 `model=auto` 时才会触发智能路由；请求其他模型名时，仍按普通 AI 网关流程转发。

### 3.3 应用商店安装应用后无法访问怎么办？

**问题**：在 1Panel 应用商店安装应用后，外部访问地址该怎么填、为什么装完进不去？

**处理方式**：

安装时需在参数中填写外部访问地址（主机 IP + 应用端口），并确保该端口已在防火墙中放行；若未放行，可在应用安装页面的高级设置中编辑 compose 文件调整端口配置。

### 3.4 拉取镜像失败提示 image pull failed 怎么办？

**问题**：安装应用或创建环境时一直拉取不到镜像、提示 image pull failed，怎么处理？

**处理方式**：

应用安装失败、镜像拉取超时，可在【容器】-【配置】中配置镜像加速器进行优化，加速地址填写 `https://docker.1panel.live`。若配置后拉取应用镜像仍然失败，可在论坛中进一步讨论。

## 4 网站与数据库管理

## 5 AI 网关与智能路由

### 5.1 AI 门户只有企业版才能对接使用吗？

**问题**：1Panel AI 门户是不是只有企业版才可以对接使用？

**处理方式**：

是的，AI 门户是企业版功能，只有企业版才可对接使用。
