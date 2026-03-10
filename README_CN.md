# AI 议会

基于 [OpenClaw](https://docs.openclaw.ai) 的 AI 多智能体议会投票系统。

多个 AI 智能体——各自使用不同的大语言模型——对每个任务进行集体审议：独立提出方案、投票选出最优解，然后执行获胜方案。

## 工作原理

```
用户发送任务
       |
议长 (Speaker) 通过 sessions_spawn 并行分发给所有议员
       |
+--------+--------+--------+--------+--------+
Claude   GPT     Grok    Kimi   DeepSeek  ...    <-- 各自提出方案
+--------+--------+--------+--------+--------+
       |
所有方案匿名化 (A, B, C, D...) 后分发给所有议员
       |
+--------+--------+--------+--------+--------+
Claude   GPT     Grok    Kimi   DeepSeek  ...    <-- 各自投票
+--------+--------+--------+--------+--------+
       |
议长统计票数 --> 获胜方案被执行或展示
```

## 支持的模型提供商

| 提供商 | 模型 | 认证方式 | 环境变量 |
|--------|------|----------|----------|
| Anthropic | Claude Sonnet 4.5 | API Key | `ANTHROPIC_API_KEY` |
| OpenAI | GPT-5.4 | API Key | `OPENAI_API_KEY` |
| OpenAI Codex | GPT-5.4 (ChatGPT) | OAuth | _(自动检测)_ |
| DeepSeek | DeepSeek Chat | API Key | `DEEPSEEK_API_KEY` |
| xAI | Grok 3 | API Key | `XAI_API_KEY` |
| Moonshot | Kimi K2.5 | API Key | `MOONSHOT_API_KEY` |
| 通义千问 | Qwen3 Coder | API Key | `QWEN_API_KEY` |
| 智谱 Z.AI | GLM-5 | API Key | `ZAI_API_KEY` |
| 火山引擎/Ark | 豆包 (endpoint) | API Key + Endpoint ID | `ARK_API_KEY` + `ARK_ENDPOINT_ID` |

至少需要 2 个提供商。添加更多提供商可以获得更丰富的讨论。

## 前置条件

- [OpenClaw](https://docs.openclaw.ai)（`npm install -g openclaw`）
- Python 3
- 至少 2 个提供商的 API Key

## 安装

```bash
./setup.sh
```

安装脚本会：
1. 自动检测已有凭证（环境变量、历史配置、默认 profile 的 OAuth）
2. 仅提示输入缺失的提供商密钥
3. 创建隔离的 OpenClaw profile（`parliament`），位于 `~/.openclaw-parliament/`
4. 配置一个议长智能体 + 每个提供商一个议员智能体
5. 将工作区文件复制到每个智能体的私有目录中

重复运行 `setup.sh` 是安全的——它会同步工作区文件、跳过已存在的智能体、更新身份配置。

### 环境变量

预设 API Key 可跳过交互式提示：

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
export DEEPSEEK_API_KEY="sk-..."
./setup.sh
```

火山引擎/Ark 还需要设置 Endpoint ID：

```bash
export ARK_API_KEY="..."
export ARK_ENDPOINT_ID="ep-2024xxxx"
```

## 使用方法

启动网关：
```bash
openclaw --profile parliament gateway start
```

发送任务：
```bash
openclaw --profile parliament agent --message "写一个查找最长回文子串的函数"
```

列出智能体：
```bash
openclaw --profile parliament agents list
```

验证配置：
```bash
openclaw --profile parliament config validate
```

## 设计理念

- **议长只协调，不提案** —— 确保中立性
- **方案匿名化**（标记为 A/B/C）—— 投票时防止品牌偏见
- **平票裁决** —— 议长投出决定性一票
- **并行执行** —— 提案和投票阶段通过 `sessions_spawn` 并行运行所有智能体
- **容错机制** —— 某个议员出错或超时时，使用剩余议员继续完成流程
- **执行** —— 代码/命令在投票后执行；纯文本答案直接展示
- **隔离工作区** —— 每个智能体在 `~/.openclaw-parliament/workspaces/<agent-id>/` 下拥有独立的工作区副本

## 项目结构

```
ai-parl/
├── setup.sh                  # 安装脚本（兼容 bash 3.2+）
├── _collect_creds.py         # 凭证检测与交互式收集
├── _apply_config.py          # 提供商配置与 auth-profiles 写入
├── workspace/                # 工作区模板（唯一数据源）
│   ├── SOUL.md               # 议会行为规则与响应格式
│   ├── AGENTS.md             # 角色定义与协调流程
│   └── USER.md               # 用户上下文
└── skills/
    └── parliament/
        └── SKILL.md           # 议长的流程编排指令
```

### 运行时状态

```
~/.openclaw-parliament/
├── openclaw.json              # OpenClaw 配置（智能体、模型、认证）
├── workspaces/                # 每个智能体的工作区副本
│   ├── main/                  # 议长
│   │   ├── SOUL.md, AGENTS.md, USER.md
│   │   ├── skills/parliament/SKILL.md
│   │   └── memory/
│   ├── member-anthropic/      # 每个活跃提供商一个
│   ├── member-openai/
│   └── ...
└── agents/                    # 每个智能体的状态（会话、认证）
    ├── main/agent/auth-profiles.json
    ├── member-anthropic/agent/auth-profiles.json
    └── ...
```

## 添加新提供商

编辑 `_collect_creds.py`，在 `PROVIDERS` 列表中添加一个元组：

```python
("provider-id", "ENV_VAR_NAME", "显示名称", "议员名称", "emoji",
 "provider-id/model-name", is_builtin, "api_key", custom_json_or_None),
```

- **内置**（`True`）：提供商在 OpenClaw 目录中——只需认证配置
- **自定义**（`False`）：需要 `models.providers` 条目——在最后一个字段提供 JSON 配置
