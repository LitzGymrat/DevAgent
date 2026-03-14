import ast
from typing import List
from dataclasses import dataclass

#将问题相关的数据封装成类
@dataclass
class code_issue:
    line:int
    issue_type:str
    severity:str
    description:str
    suggestion:str

class code_analyser:
    #静态代码分析器

    """使用AST检测代码中的常见问题
        1. 可变默认参数
        2. 裸 except
        3. 函数过长
        4. 圈复杂度过高
        5. 未使用的 import"""
    
    def __init__(self):
        self.issues : List[code_issue] = []
    def analyse(self,code:str)->List[code_issue]:
        #尝试解析代码
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            self.issues.append(code_issue(
                line = e.lineno or 1,
                issue_type="syntax error",
                severity="error",
                description="语法错误",
                suggestion="请检查代码语法是否正确",

            ))
            return self.issues
        
        #运行各项检查.
        self._check_mutable_default_args(tree)
        self._check_bare_except(tree)
        self._check_function_length(tree)
        self._check_complexity(tree)
        self._check_unused_imports(code, tree)


        return self.issues


    #1.检测默认可变参数
    def _check_mutable_default_args(self,tree:ast.AST):
        """问题：如果函数定义的时候使用了默认可变参数[],{}
        他们会在函数定义时分配内存，多次调用使用相同的字典/列表"""

        for node in ast.walk(tree):
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)): #一个元组：函数/异步函数定义
                for default in node.args.defaults + node.args.kw_defaults:
                    if default is None:
                        continue
                    if isinstance(default,ast.List):
                        self.issues.append(code_issue(
                            line = node.lineno,
                            issue_type="mutable_default_args",
                            severity="error",
                            description=f"函数'{node.name}'使用了默认可变参数 []",
                            suggestion="改为 def (x=None): if x is None: x = []",
                        ))
                    elif isinstance(default,ast.Dict):
                        self.issues.append(code_issue(
                            line = node.lineno,
                            issue_type="mutable_default_args",
                            severity="error",
                            description=f"函数'{node.name}'使用了默认可变参数 {{}}",
                            suggestion="改为 def (x=None): if x is None: x = {}",
                        ))

    #2.检测裸except：会捕获所有异常
    """如果写 except: 而不是 except Exception:，
    它会把系统级别的异常（比如按 Ctrl+C 触发的 KeyboardInterrupt，
    或者系统退出 SystemExit）也给强行拦截下来。关不掉"""
    def _check_bare_except(self,tree:ast.AST):
        for node in ast.walk(tree):
            if isinstance(node,ast.ExceptHandler):
                if node.type is None:
                    self.issues.append(code_issue(
                            line = node.lineno,
                            issue_type="bare_except",
                            severity="warning",
                            description=f"使用了裸except，会捕获所有异常",
                            suggestion="指定具体异常类型，比如except Exception as e:",
                        ))
                    
    #3.检测过长函数
    def _check_function_length(self,tree:ast.AST):
        for node in ast.walk(tree):
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
                #看第一行和最后一行在不在
                if node.lineno and node.end_lineno:
                    #避免覆盖关键字len。采用Length作为变量名。
                    length = node.end_lineno - node.lineno + 1
                    if length > 50:
                        self.issues.append(code_issue(
                            line = node.lineno,
                            issue_type="function_too_long",
                            severity="warning",
                            description=f"函数'{node.name}'有'{length}'行，较长",
                            suggestion="将函数的不同功能拆分成多个小函数",
                        ))


    #5.计算一个节点内圈复杂度的辅助函数
    #区分：这是对一个父节点进行的
    def _calc_complexity(self,node:ast.AST)->int:
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child,(ast.If,ast.ExceptHandler,ast.While,ast.For)):
                complexity += 1
            elif isinstance(child,ast.BoolOp):#每个布尔运算也加一个复杂度
                complexity += len(child.values) - 1
        
        return complexity

    #4.检测函数圈复杂度:
    def _check_complexity(self,tree:ast.AST):
        for node in ast.walk(tree):
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
                complexity = self._calc_complexity(node)
                if complexity > 10:
                    self.issues.append(code_issue(
                            line = node.lineno,
                            issue_type="high_complexity",
                            severity="warning",
                            description=f"函数'{node.name}'圈复杂度为'{complexity}'，超过阈值10",
                            suggestion="简化逻辑，提取子函数，减少嵌套",
                        ))

    #5.检查未使用的Imports

    def _check_unused_imports(self,code:str,tree:ast.AST):
        #简单检查：导入的是否在后续代码中出现(存在局限，没有做复杂字符串，代码解析)
        imports = []

        for node in ast.walk(tree):
            if isinstance(node,(ast.ImportFrom,ast.Import)):
                for alias in node.names:
                    name = alias.asname or alias.name.split('.')[0] #如果引入这种os.path。调用时是os.path，根变量是os.切分取第一个
                    imports.append((name,node.lineno))
        
        #检查每行是否用到
        lines = code.split('\n')#单引号字符'\n'
        for name,lineno in imports:
            used = False
            for i,line in enumerate(lines):
            #跳过import本身所在行
                if i+1 == lineno: 
                    continue
                if name in line and not line.strip().startswith(("import","from")):
                    used = True
                    break
            
            if not used:
                self.issues.append(code_issue(
                    line=lineno,
                    issue_type="unused_import",
                    severity="info",
                    description=f"'{name}' 被导入但未使用",
                    suggestion="删除未使用的 import，保持代码整洁"
                ))


            

    def format_report(self,issues:List[code_issue] = None)->str:
        issues = issues or self.issues

        if not issues:
            return "代码检查完成 未发现问题"
        
        report = f"代码分析：共发现{len(issues)}个问题\n\n"

        #按严重程度分组
        errors = [i for i in issues if i.severity == "error"]
        warnings = [i for i in issues if i.severity == "warning"]
        infos = [i for i in issues if i.severity == "info"]

        if errors:
            report += f"错误：必要修复！\n"
            for issue in errors:
                report += f"第{issue.line}行，问题：{issue.description}\n"
                report += f"建议：{issue.suggestion}\n"
            report += f"\n\n"
        
        if warnings:
            report +=  f"警告：建议修复\n"
            for issue in warnings:
                report += f"第{issue.line}行，问题：{issue.description}\n"
                report += f"建议：{issue.suggestion}\n"
            report += f"\n\n"
        if infos:
            report += f"建议！\n"
            for issue in infos:
                report += f"第{issue.line}行，问题：{issue.description}\n"
                report += f"建议：{issue.suggestion}\n"
            report += f"\n\n"
        return report
    

    #最后一个API接口工具函数供Agent调用
def analyse_code(code:str):
    #建立实例
    analyser = code_analyser()
    issues = analyser.analyse(code)
    return analyser.format_report(issues)


    