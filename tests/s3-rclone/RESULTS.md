# rclone 互操作证据（2026-08-05）

## 环境

- alva S3 服务器（store_server.alva），监听 127.0.0.1:9000
- rclone **v1.75.0**（rclone-current-windows-amd64）
- 配置见 [rclone.conf](rclone.conf)：endpoint 127.0.0.1:9000，AK `test`，SK `testtest`，force_path_style
- SigV4 认证已启用（AWS4-HMAC-SHA256）

## 实测结果

```
rclone copy   fixtures -> localstore:ci        ✓
rclone check  fixtures <-> localstore:ci       ✓ 0 differences found, 3 matching files
rclone cat    localstore:ci/sub/c.txt          ✓ nested gamma
rclone ls     localstore:ci                    ✓ 14 a.txt / 18 b.txt / 13 sub/c.txt
deletefile + check                             ✓ 删除后 check 报 1 differences found
未签名 curl 请求                               ✓ 403 SignatureDoesNotMatch
85MB 大文件上传→下载回环                        ✓ 85160448 == 85160448（字节级一致）
```

## 可复现脚本

`run_rclone_test.sh` 在 CI 中自动执行上述流程（下载固定版本 rclone v1.75.0）。

## 夹具哈希

```
sha256sum tests/s3-rclone/fixtures/*
7372b75dfb24271a231d7c882b0cdbd0df8a1bb075764ca16ec9df0df2582d65  a.txt
bf725937e6a01c7b8429e062f1dc5a77815fbd3ca7e5b69ac423b7001dcc3a18  b.txt
35a572035f8e2a6796c3b3cff8e6805e46dc32176f8d1e28e626e545b65d3752  sub/c.txt
```
