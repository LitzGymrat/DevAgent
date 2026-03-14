import os
import sys





from src.agent.tools.search_tool import analyse_code 

def main():
    print(" [CI/CD] 执行AST 静态代码审查...\n")
    
    
    target_dir = "src"
    total_issues = 0
    scanned_files = 0

    # 遍历 src 目录下的所有 .py 文件
    for root, _, files in os.walk(target_dir):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                scanned_files += 1
                
                
                with open(file_path, "r", encoding="utf-8") as f:
                    source_code = f.read()
                
                # 传分析器，拿到纯文本报告
                report = analyse_code(source_code)
                
                
                if "错误：必要修复" in report or "语法错误" in report:
                    print(f"[拦截] 文件 {file_path} 存在问题：")
                    print("-" * 40)
                    print(report.strip()) 
                    print("-" * 40)
                    total_issues += 1 

    # 给 GitHub Action 发送信号
    print(f"\n [审查总结] 共扫描了 {scanned_files} 个 Python 文件。")
    if total_issues > 0:
        print(f"发现 {total_issues} 个文件存在问题，请修复后再提交！")
        sys.exit(1)  # 返回非 0 状态码，GitHub 亮红灯！
    else:
        print("所有代码均符合规范，允许合并！")
        sys.exit(0)  # 返回 0 状态码，GitHub 亮绿灯！

if __name__ == "__main__":
    main()