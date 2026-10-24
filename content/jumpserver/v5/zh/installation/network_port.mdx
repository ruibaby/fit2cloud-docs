---
title: 网络端口说明
---

## 1 网络端口列表

- JumpServer 作为符合 4A 规范的专业运维安全审计系统，其正常运行需要开放如下网络端口，管理员可根据实际环境中 JumpServer 组件部署的方案，在网络和主机侧开放相关端口。

<div style={{textAlign:"center",color:"#8a8f99",fontSize:"13px",margin:"16px 0 8px"}}>表 1  网络端口列表</div>

| 端口 | 作用 | 说明 |
| --- | --- | --- |
| 22 | SSH | 安装、升级及管理使用 |
| 80 | Web HTTP 服务 | 通过 HTTP 协议访问 JumpServer 前端页面 |
| 443 | Web HTTPS 服务 | 通过 HTTPS 协议访问 JumpServer 前端页面 |
| 3306 | 数据库服务 | MySQL 服务使用 |
| 6379 | 数据库服务 | Redis 服务使用 |
| 3389 | Razor 服务端口 | RDP Client 方式连接 Windows 资产 |
| 3390 | XRDP 服务端口 | XRDP 为企业版可选组件，默认关闭；启用后用于通过 JumpServer Client 方式访问 Windows 2000、XP 等系统的资产 |
| 2222 | SSH Client | SSH Client 方式使用终端工具连接 JumpServer，比如 Xshell、PuTTY、MobaXterm 等终端工具 |
| 5001 | Koko Web Proxy 服务端口 | 使用内置浏览器方式访问 Web 资产时使用 |
| 5525 | Magnus 服务端口 | DB Client 方式连接数据库资产，系统会根据所连接资产的类型自动分配对应端口 |
| 15900 | NEC 服务端口 |  VNC 服务使用 |
| 9898 | JDMC 服务端口 | 企业版 JDMC（设备管理控制台）服务使用，采用 HTTPS 协议 |


- Magnus 服务端口为 **5525**，连接数据库资产时，系统会根据所连接资产的类型（MySQL、MariaDB、PostgreSQL、Redis、Oracle 等）自动分配对应的连接端口。

## 2 防火墙常用命令

- 确认 firewall 的状态为 running
```sh
firewall-cmd --state
```
```sh
running
```


- 临时开放端口（规则立即生效，重启失效）
```sh
firewall-cmd --zone=public --add-port=80/tcp
firewall-cmd --zone=public --add-port=2222/tcp
firewall-cmd --add-rich-rule="rule family="ipv4" source address="172.17.0.1/16" port protocol="tcp" port="8080" accept"
```


- 临时删除端口（规则立即生效，重启失效）
```sh
firewall-cmd --zone=public --remove-port=80/tcp
firewall-cmd --zone=public --remove-port=2222/tcp
firewall-cmd --remove-rich-rule="rule family="ipv4" source address="172.17.0.1/16" port protocol="tcp" port="8080" accept"
```


- 永久放行端口（需要 reload 才能生效）
```sh
firewall-cmd --zone=public --add-port=80/tcp --permanent
firewall-cmd --zone=public --add-port=2222/tcp --permanent
firewall-cmd --add-rich-rule="rule family="ipv4" source address="172.17.0.1/16" port protocol="tcp" port="8080" accept" --permanent
firewall-cmd --reload
```


- 永久删除端口（需要 reload 才能生效）
```sh
firewall-cmd --zone=public --remove-port=80/tcp --permanent
firewall-cmd --zone=public --remove-port=2222/tcp --permanent
firewall-cmd --remove-rich-rule="rule family="ipv4" source address="172.17.0.1/16" port protocol="tcp" port="8080" accept" --permanent
firewall-cmd --reload
```


- 查看端口生效规则
```sh
firewall-cmd --list-all
```
```sh
public (active)
  target: default
  icmp-block-inversion: no
  interfaces: ens32
  sources:
  services: dhcpv6-client ssh
  ports: 80/tcp 2222/tcp
  protocols:
  masquerade: no
  forward-ports:
  source-ports:
  icmp-blocks:
  rich rules:
    rule family="ipv4" source address="172.17.0.1/16" port port="8080" protocol="tcp" accept
```
