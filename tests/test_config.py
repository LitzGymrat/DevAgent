#测试配置文件
#通过src.调用文件
from src.config import settings

#防止被引用调用，只有是主程序的时候才启动
if __name__ == "__main__":
    print("API ket前几位:" , f"{settings.deepseek_api_key[0:5]} + ...")
    print("模型名:",f"{settings.model_name}")
    