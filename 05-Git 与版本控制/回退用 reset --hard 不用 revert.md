# 回退用 reset --hard 不用 revert

**结论**：回退到历史版本用 `git reset --hard <commit>`，绝不用 `git revert`。

## 为什么

`git revert` 会新建一个反向提交，历史里多一个 `Revert "..."` 记录，不干净。用户原话："以后回退直接版本控制就好了，你不要再新建一个 commit 了。"

## 怎么做

本地回退：

```bash
git reset --hard <commit>
```

已推送远程、需要同步回退（**必须先拿到用户 push 授权**）：

```bash
git push --force
```

用户明确要求：强制推送就用裸 `git push --force`，不要加 `--force-with-lease`，不要加 `origin main`。分支已配上游时裸命令就够。

## 恢复单个文件

```bash
git checkout <commit> -- <file>
```

不要 Read + Write 重写文件内容。

## 前置条件

执行前必须拿到用户明确授权，见 [撤销改动必须用户授权](../01-AI 协作/撤销改动必须用户授权.md)。
