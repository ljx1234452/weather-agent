# 天气 Agent

这是一个通过 FastAPI 提供聊天接口、调用天气工具并保存会话历史的练习项目。

## 模型配置

第一次运行时，复制项目根目录的 `.env.example`，将副本命名为 `.env`，再把占位值换成自己的模型平台配置。已有 `.env` 时无需复制。

- `MODEL_API_KEY`：模型平台的密钥。
- `MODEL_BASE_URL`：模型平台的接口地址。
- `MODEL_NAME`：要使用的模型名称；不填写时使用代码中的默认值。

`.env` 含有密钥，不要提交到 Git。

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