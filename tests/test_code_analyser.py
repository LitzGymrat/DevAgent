from src.agent.tools.code_analyser import analyse_code
test_code = """import os
import sys
import json

def process_data(items=[]):
    result = []
    for item in items:
        if item > 0:
            if item % 2 == 0:
                try:
                    result.append(item * 2)
                except:
                    pass
        else:
            result.append(0)
    return result

def helper():
    pass"""

report = analyse_code(test_code)
print(report)