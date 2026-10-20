# Skills

## Project Finder · 本地工作经验

把完成过的重复性任务整理成可复用流程，在下次执行时找回、核对并改进。

当前版本：**v0.3**。

- [使用说明](project-finder/README.md)
- [完整架构方案](project-finder/ARCHITECTURE.md)
- [Skill 入口](project-finder/SKILL.md)

### 安装

将本仓库中的整个 `project-finder/` 文件夹放到所用工具支持的 Skill 目录。避免同时启用同名旧版本。用户知识库默认保存在目标工作目录的 `.project-finder/`，与 Skill 分开维护。

### 验证

检查工具和测试需要 Python 3.9+ 与 PyYAML。核心 Markdown 工作流可独立使用。

```sh
python -m pip install -r project-finder/requirements.txt
python -B -X utf8 project-finder/tests/test_memory_check.py
```

已完成结构与工具测试，实际任务复用效果仍需在真实工作中验证。
