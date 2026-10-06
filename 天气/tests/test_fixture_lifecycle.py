import pytest


@pytest.fixture
def resource():
    print("1. 准备资源")

    yield "天气资源"

    print("3. 清理资源")


def test_resource(resource: str):
    print("2. 执行测试")

    assert resource == "天气资源"