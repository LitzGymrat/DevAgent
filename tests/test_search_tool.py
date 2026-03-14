from src.agent.tools.search_tool import search_codebase


# 简单的本地测试
if __name__ == "__main__":
    
    
    test_result = search_codebase("怎么建立向量数据库的类？")
    print("\n======= 最终喂给大模型的内容 =======")
    print(test_result)