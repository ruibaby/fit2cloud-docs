---
title: 数据迁移
---


SQLBot 的迁移工作建议在同版本的情况下进行。如源服务器上的 SQLBot 版本是 v1.4.0，则目标服务器上请先安装好 v1.4.0 版本的 SQLBot。迁移前请先按 [备份还原](./backup) 做好备份。若使用外置数据库，除复制运行目录外，还需单独迁移 PostgreSQL 中的 `sqlbot` 库。


## 停止服务


停止源服务器和目标服务器上的 SQLBot 服务：

```bash
sctl stop
```


## 数据迁移


数据迁移需要将源服务器上 SQLBot 的运行目录复制到目标服务器上。

在复制之前，可以将目标服务器上的 SQLBot 运行目录移除。

此处为了保险起见，我们将目标服务器上的 SQLBot 运行目录进行改名操作，在目标服务器上执行命令（SQLBot 默认运行目录为 /opt/sqlbot，如有修改，请相应的调整下面的命令）
```bash
mv /opt/sqlbot /opt/sqlbot-bak
```


如果之前是在线安装模式运行的 SQLBot（即 docker 命令直接运行），则源服务器运行目录为 docker 命令当前的执行目录，将该目录下的 data 目录复制到 SQLBot 目标服务器的运行目录下。


然后，将源服务器上的 SQLBot 运行目录复制过来。此处假设源服务器 ip 为 192.168.0.1，目标服务器 ip 为 192.168.0.2，在目标服务器上执行命令：
```bash
scp -r root@192.168.0.1:/opt/sqlbot /opt
```


## 参数调整


如果源服务器上为 SQLBot 配置过 MCP 服务的话，需要修改 MCP 相关参数。
```
root@iZf8zg3g62vtajwudlbwgiZ:~# cat /opt/sqlbot/.env | grep SERVER_IMAGE_HOST
SQLBOT_SERVER_IMAGE_HOST=http://192.168.0.2:8001/images/

root@iZf8zg3g62vtajwudlbwgiZ:~# cat /opt/sqlbot/conf/sqlbot.conf | grep SERVER_IMAGE_HOST
SERVER_IMAGE_HOST=http://192.168.0.2:8001/images/
```


## 启动服务


数据迁移工作完成后，启动目标服务器上的 SQLBot：
```bash
sctl start
```

整个迁移工作完成。


## 其他情况


如果之前是在线安装模式运行的 SQLBot（即 docker 命令直接运行），则源服务器运行目录为 docker 命令当前的执行目录，将该目录下的 data 目录复制到 SQLBot 目标服务器的运行目录下，

