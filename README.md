# 天气 Agent

这是一个通过 FastAPI 提供聊天接口、调用天气工具并保存会话历史的练习项目。

## 模型配置

第一次运行时，复制项目根目录的 `.env.example`，将副本命名为 `.env`，再把占位值换成自己的模型平台配置。已有 `.env` 时无需复制。

- `MODEL_API_KEY`：模型平台的密钥。
- `MODEL_BASE_URL`：模型平台的接口地址。
- `MODEL_NAME`：要使用的模型名称；不填写时使用代码中的默认值。
- `CHAT_ACCESS_KEY`：创建会话使用的共用访问口令，在请求头 `X-Chat-Key` 中填写相同的值。聊天和读取历史使用该会话的独立钥匙。
`.env` 含有密钥，不要提交到 Git。

## 创建会话

调用 `POST /sessions` 时提供 `X-Chat-Key`。成功后返回 `session_id` 和 `conversation_key`：前者是随机生成的对话编号，后者由该编号和随机秘密部分组成。

数据库保存对话编号与钥匙的 SHA-256 摘要，并在同一个事务中完成保存；完整钥匙在创建响应中返回，不写入数据库或日志。

完整钥匙是该对话的访问凭证，请妥善保管，不要放到 URL、日志或公开分享中。当前没有账号登录与找回机制，不能凭共用口令取代对话钥匙来访问聊天或历史。

## 聊天

调用 `POST /chat` 时，在请求头 `X-Conversation-Key` 中提供完整的 `conversation_key`，请求正文只需要用户消息：

```json
{"message": "广州未来三天天气如何？"}
```

服务器根据钥匙找到对应的 `session_id`，再读取历史、调用 Agent，并把本次用户消息和回答保存到该对话。无需另外填写编号或共用访问口令；缺少或无效的钥匙返回 `401`，且不会调用模型。

## 读取历史

调用 `GET /history` 时，在请求头 `X-Conversation-Key` 中提供创建会话时返回的完整 `conversation_key`，无需另外填写 `session_id` 或共用访问口令。服务器根据钥匙指纹找到编号，再返回该对话的历史。

缺少或无效的钥匙返回 `401`；新会话返回空消息列表。旧的 `/sessions/{session_id}/history` 地址已移除。升级前没有独立钥匙的旧会话不会自动获得钥匙，请新建会话体验这一步功能。

## 天气请求配置（可选）

- `WEATHER_MAX_ATTEMPTS`：一次天气请求最多尝试几次，默认是 `2`，必须至少为 `1`。
- `WEATHER_RETRY_DELAY_SECONDS`：请求超时后、再次尝试前等待几秒，默认是 `1`，不能小于 `0`。

不配置这两项时，程序使用默认值。

## 数据库位置（可选）

默认使用 `天气/weather_agent.db`。部署时可通过 `WEATHER_DATABASE_PATH` 指定数据库文件的绝对路径，例如 Linux 服务器上的 `/data/weather_agent.db`。上级目录需要已存在且可写。修改配置后要重启服务；改路径不会自动搬迁旧数据。

## 安装依赖

需要 Python 3.14 或更高版本，以及 uv。在包含 `pyproject.toml` 的项目根目录运行：

```powershell
uv sync
```

这会创建项目的 `.venv` 并安装依赖。

## 本地启动

在包含 `pyproject.toml` 的项目根目录运行：

```powershell
.\.venv\Scripts\python.exe -m uvicorn 天气.api:app --host 127.0.0.1 --port 8000
```

启动后打开 http://127.0.0.1:8000/docs。
