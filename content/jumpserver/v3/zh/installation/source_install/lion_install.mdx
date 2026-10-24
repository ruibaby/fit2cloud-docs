---
title: Lion 环境部署
---

## 1 Lion 组件简述

[Lion][lion] 使用了 [Apache][apache] 软件基金会的开源项目 [Guacamole][guacamole]，JumpServer 使用 Golang 和 Vue 重构了 Guacamole 实现 RDP/VNC 协议跳板机功能。

### 1.1 环境要求

| Name    | JumpServer               | Guacd                  |  Lion                    |
| :------ | :----------------------- | :--------------------- | :----------------------- |
| Version | v3.10.21     | [1.4.0][guacd-1.4.0]   | v3.10.21 |

- 可以从 [Github][guacamole-server] 网站上获取对应的 guacd 副本。这些版本是最新代码的稳定快照，从项目网站下载 Source code.tar.gz 源代码，通过命令行中提取该存档：

```bash
mkdir /opt/guacamole-v3.10.21
cd /opt/guacamole-v3.10.21
wget http://download.jumpserver.org/public/guacamole-server-1.4.0.tar.gz
tar -xzf guacamole-server-1.4.0.tar.gz
cd guacamole-server-1.4.0/
```

- 参考 [building-guacamole-server][building-guacamole-server] 官方文档，安装对应操作系统的依赖包。

### Ubuntu 20.04

```bash
apt-get install -y libcairo2-dev libjpeg-turbo8-dev libpng-dev libtool-bin libossp-uuid-dev
apt-get install -y libavcodec-dev libavformat-dev libavutil-dev libswscale-dev freerdp2-dev libpango1.0-dev libssh2-1-dev libtelnet-dev libvncserver-dev libwebsockets-dev     libpulse-dev libssl-dev libvorbis-dev libwebp-dev
```
### 1.2 构建 Guacd

```bash
./configure --with-init-dir=/etc/init.d
make
make install
ldconfig
```

- 如果希望使用 systemd 管理, 可以使用 ./configure --with-systemd-dir=/etc/systemd/system/

### 1.3 下载 Lion

- 可以从 [Github][lion] 网站上获取最新的 [Release][lion_release] 副本。

| OS      | Arch    | Name                                                                                              |
| :------ | :------ | :------------------------------------------------------------------------------------------------ |
| Linux   | amd64   | [lion-v3.10.21-linux-amd64.tar.gz][lion-v3.10.21-linux-amd64]     |
| Linux   | arm64   | [lion-v3.10.21-linux-arm64.tar.gz][lion-v3.10.21-linux-arm64]     |
| Linux   | loong64 | [lion-v3.10.21-linux-loong64.tar.gz][lion-v3.10.21-linux-loong64] |
| Darwin  | amd64   | [lion-v3.10.21-darwin-amd64.tar.gz][lion-v3.10.21-darwin-amd64]   |
| Windows | amd64   | [lion-v3.10.21-windows-amd64.tar.gz][lion-v3.10.21-windows-amd64] |


### Linux/amd64

```bash
cd /opt
wget https://github.com/jumpserver/lion-release/releases/download/v3.10.21/lion-v3.10.21-linux-amd64.tar.gz
tar -xf lion-v3.10.21-linux-amd64.tar.gz
cd lion-v3.10.21-linux-amd64
```
    ### Linux/arm64

```bash
cd /opt
wget https://github.com/jumpserver/lion-release/releases/download/v3.10.21/lion-v3.10.21-linux-arm64.tar.gz
tar -xf lion-v3.10.21-linux-arm64.tar.gz
cd lion-v3.10.21-linux-arm64
```
### 1.4 修改配置文件

```bash
cp config_example.yml config.yml
vi config.yml
```
```yaml
# 项目名称, 会用来向Jumpserver注册, 识别而已, 不能重复
# NAME: {{ Hostname }}

# Jumpserver项目的url, api请求注册会使用
CORE_HOST: http://127.0.0.1:8080   # Core 的地址

# Bootstrap Token, 预共享秘钥, 用来注册使用的service account和terminal
# 请和jumpserver 配置文件中保持一致，注册完成后可以删除
BOOTSTRAP_TOKEN: ********  # 和 Core config.yml 的值保持一致

# 启动时绑定的ip, 默认 0.0.0.0
BIND_HOST: 0.0.0.0

# 监听的HTTP/WS端口号，默认8081
HTTPD_PORT: 8081

# 设置日志级别 [DEBUG, INFO, WARN, ERROR, FATAL, CRITICAL]
LOG_LEVEL: DEBUG           # 开发建议设置 DEBUG, 生产环境推荐使用 ERROR

# Guacamole Server ip，默认127.0.0.1
# GUA_HOST: 127.0.0.1

# Guacamole Server 端口号，默认4822
# GUA_PORT: 4822

# 会话共享使用的类型 [local, redis], 默认local
# SHARE_ROOM_TYPE: local

# Redis配置
# REDIS_HOST: 127.0.0.1
# REDIS_PORT: 6379
# REDIS_PASSWORD:
# REDIS_DB_ROOM:
```

### 1.5 启动 Guacd

```bash
/etc/init.d/guacd start
```

### 1.6 启动 Lion

```bash
./lion
```

[nginx]: http://nginx.org/
[lina]: https://github.com/jumpserver/lina/
[vue]: https://cn.vuejs.org/
[element_ui]: https://element.eleme.cn/
[luna]: https://github.com/jumpserver/luna/
[angular_cli]: https://github.com/angular/angular-cli
[core]: https://github.com/jumpserver/jumpserver/
[django]: https://docs.djangoproject.com/
[gunicorn]: https://gunicorn.org/
[celery]: https://docs.celeryproject.org/
[flower]: https://github.com/mher/flower/
[daphne]: https://github.com/django/daphne/
[github]: https://github.com/
[core_release]: https://github.com/jumpserver/jumpserver/releases/tag/v3.10.21
[python]: https://www.python.org/downloads/
[linux_packages]: http://nginx.org/en/linux_packages.html
[lina_release]: https://github.com/jumpserver/lina/releases/tag/v3.10.21
[node]: https://nodejs.org/
[luna_release]: https://github.com/jumpserver/luna/releases/tag/v3.10.21
[koko_release]: https://github.com/jumpserver/koko/releases/tag/v3.10.21
[go]: https://golang.google.cn/
[koko]: https://github.com/jumpserver/koko
[koko_release]: https://github.com/jumpserver/koko/releases/tag/v3.10.21
[lion]: https://github.com/jumpserver/lion-release
[lion_release]: https://github.com/jumpserver/lion-release/releases/tag/v3.10.21
[guacamole]: http://guacamole.apache.org/
[apache]: http://www.apache.org/
[guacamole-server]: https://github.com/apache/guacamole-server
[building-guacamole-server]: http://guacamole.apache.org/doc/gug/installing-guacamole.html#building-guacamole-server
[guacd-1.4.0]: http://download.jumpserver.org/public/guacamole-server-1.4.0.tar.gz
[wisp]: https://github.com/jumpserver/wisp
[wisp_release]: https://github.com/jumpserver/wisp/releases/tag/v0.1.16
[magnus]: https://github.com/jumpserver/magnus-release
[magnus_release]: https://github.com/jumpserver/magnus-release/releases/tag/v3.10.21
[lina-v3.10.21]: https://github.com/jumpserver/lina/releases/download/v3.10.21/lina-v3.10.21.tar.gz
[luna-v3.10.21]: https://github.com/jumpserver/luna/releases/download/v3.10.21/luna-v3.10.21.tar.gz
[koko-v3.10.21-linux-amd64]: https://github.com/jumpserver/koko/releases/download/v3.10.21/koko-v3.10.21-linux-amd64.tar.gz
[koko-v3.10.21-linux-arm64]: https://github.com/jumpserver/koko/releases/download/v3.10.21/koko-v3.10.21-linux-arm64.tar.gz
[koko-v3.10.21-linux-loong64]: https://github.com/jumpserver/koko/releases/download/v3.10.21/koko-v3.10.21-linux-loong64.tar.gz
[koko-v3.10.21-darwin-amd64]: https://github.com/jumpserver/koko/releases/download/v3.10.21/koko-v3.10.21-darwin-amd64.tar.gz
[koko-v3.10.21-darwin-arm64]: https://github.com/jumpserver/koko/releases/download/v3.10.21/koko-v3.10.21-darwin-arm64.tar.gz
[lion-v3.10.21-linux-amd64]: https://github.com/jumpserver/lion-release/releases/download/v3.10.21/lion-v3.10.21-linux-amd64.tar.gz
[lion-v3.10.21-linux-arm64]: https://github.com/jumpserver/lion-release/releases/download/v3.10.21/lion-v3.10.21-linux-arm64.tar.gz
[lion-v3.10.21-linux-loong64]: https://github.com/jumpserver/lion-release/releases/download/v3.10.21/lion-v3.10.21-linux-loong64.tar.gz
[lion-v3.10.21-darwin-amd64]: https://github.com/jumpserver/lion-release/releases/download/v3.10.21/lion-v3.10.21-darwin-amd64.tar.gz
[lion-v3.10.21-windows-amd64]: https://github.com/jumpserver/lion-release/releases/download/v3.10.21/lion-v3.10.21-windows-amd64.tar.gz
[magnus-v3.10.21-linux-amd64]: https://github.com/jumpserver/magnus-release/releases/download/v3.10.21/magnus-v3.10.21-linux-amd64.tar.gz
[magnus-v3.10.21-linux-arm64]: https://github.com/jumpserver/magnus-release/releases/download/v3.10.21/magnus-v3.10.21-linux-arm64.tar.gz
[magnus-v3.10.21-linux-loong64]: https://github.com/jumpserver/magnus-release/releases/download/v3.10.21/magnus-v3.10.21-linux-loong64.tar.gz
[magnus-v3.10.21-darwin-amd64]: https://github.com/jumpserver/magnus-release/releases/download/v3.10.21/magnus-v3.10.21-darwin-amd64.tar.gz
[magnus-v3.10.21-darwin-arm64]: https://github.com/jumpserver/magnus-release/releases/download/v3.10.21/magnus-v3.10.21-darwin-arm64.tar.gz
[wisp-v0.1.16-linux-amd64]: https://github.com/jumpserver/wisp/releases/download/v0.1.16/wisp-v0.1.16-linux-amd64.tar.gz
[wisp-v0.1.16-linux-arm64]: https://github.com/jumpserver/wisp/releases/download/v0.1.16/wisp-v0.1.16-linux-arm64.tar.gz
[wisp-v0.1.16-linux-loong64]: https://github.com/jumpserver/wisp/releases/download/v0.1.16/wisp-v0.1.16-linux-loong64.tar.gz
[wisp-v0.1.16-darwin-amd64]: https://github.com/jumpserver/wisp/releases/download/v0.1.16/wisp-v0.1.16-darwin-amd64.tar.gz
[wisp-v0.1.16-darwin-arm64]: https://github.com/jumpserver/wisp/releases/download/v0.1.16/wisp-v0.1.16-darwin-arm64.tar.gz
[wisp-v0.1.16-windows-amd64]: https://github.com/jumpserver/wisp/releases/download/v0.1.16/wisp-v0.1.16-windows-amd64.tar.gz
