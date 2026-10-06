from 天气.model_client import ModelConfigurationError, run_agent
from openai.types.chat import ChatCompletionMessageParam
from openai import OpenAIError, RateLimitError




def main():
    history: list[ChatCompletionMessageParam] = []

    while True:
        user_message = input("请输入您的问题：").strip()

        if user_message == "":
            print("Agent：请输入有效的问题")
            continue

        if user_message == "退出":
            print("Agent:再见")
            break
        try:
            response = run_agent(user_message,history)

        except RateLimitError:
            print("Agent:模型额度不足，或者请求过于频繁，请稍后再试")
            continue

        except OpenAIError:
            print("Agent：模型服务暂时不可用，请稍后重试")
            continue

        except ModelConfigurationError as error:
            print(f"Agent：{error}")
            continue


        history.append({
            "role": "user",
            "content": user_message,
        })
        history.append({
            "role": "assistant",
            "content": response,
        })


        print(f"Agent:{response}")

if __name__ == "__main__":
    main()
