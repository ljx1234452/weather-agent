"""从项目根目录运行：python -m 天气.check_model"""

from openai import APIConnectionError, APIStatusError, OpenAIError

from 天气.model_client import ModelConfigurationError, run_agent


def main() -> None:
    print("正在用真实模型查询广州未来 1 天的天气...")
    try:
        answer = run_agent("查询广州未来1天的天气", [], debug=True)
    except ModelConfigurationError as error:
        print(error)
        print("请在项目根目录的 .env 文件中填写原来的模型连接信息。")
    except APIStatusError as error:
        print(f"模型接口返回 HTTP {error.status_code}。")
        if error.status_code in (401, 403):
            print("请检查 MODEL_API_KEY 是否正确、是否仍有权限。")
        elif error.status_code == 404:
            print("请检查 MODEL_BASE_URL 和 MODEL_NAME 是否与原平台一致。")
        else:
            print("请检查模型平台状态及工具调用支持情况。")
    except APIConnectionError:
        print("无法连接模型接口，请检查 MODEL_BASE_URL 和网络连接。")
    except OpenAIError:
        print("模型请求失败，请检查模型平台配置。")
    else:
        print(f"模型回答：{answer}")


if __name__ == "__main__":
    main()
