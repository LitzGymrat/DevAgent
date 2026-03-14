from src.agent.core import DevAgent

if __name__ == "__main__":
    agent = DevAgent()
    query = r"请讲讲vectorstore类的定义是如何实现的"
    res = agent.chat(query)
    print(res)