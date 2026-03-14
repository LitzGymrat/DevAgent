from __future__ import annotations #引入未来特性
from langchain_core.documents import Document        #使用lanchain_core框架 RAG数据流，使用标准生态，以免冲突。
import os #os.walk遍历文件所需
from typing import List,Iterable      #类型标注
from pathlib import Path    #路径处理


class RePoLoader:
    """代码仓库加载器：
    输入仓库路径
    自动读取所有代码
    返回List[Document]，每个Document:全文内容+元数据
    
    
    """
    #加载前过滤：支持的文件类型
    SUPPORTED_EXTENSIONS = {
        ".py",".js",".txt","java",".go",".cpp",".md",".rs",".yml",".yaml",".json"
    }



    #加载前过滤：忽略的目录

    IGNORE_DIRS = {
        #.开头：隐藏文件
        ".git",".idea",".venv","venv","__pycache__",".vscode","node_modules", "dist", "build"
    }

    #1.初始化：路径:仓库根目录                 |表示两种类型均可
    def __init__(self,repo_path : str | Path):
        self.repo_path = Path(repo_path).resolve()  #封装为Path类方便路径处理。 
                                                            #.resolve定位到物理绝对路径，防止传入"."这样的情形
    
    #2.文件遍历：返回需要的文件 ！的路径！可迭代对象列表 标注返回类型
    def iter_file(self) -> Iterable[Path]:
        #遍历返回：绝对路径，文件夹列表，文件列表
        for root,dirs,files in os.walk(self.repo_path):
            #原地修改，否则如果做一个新的dirs，根据py指针特性，旧的在遍历的不会被修改。
            #去掉不需要的文件夹
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS]
            #去掉不需要的文件
            for fname in files:
                #先封装成Path类型
                path = Path(root) / fname
                if path.suffix in self.SUPPORTED_EXTENSIONS:
                    yield path
    #3.读取路径列表，读取内容，封装打包

    def load(self) -> List[Document]:
        docs :List[Document] = [] #先构建一个列表
        #1.遍历读取:
        for file_path in self.iter_file():
            try:
                text = file_path.read_text(encoding="utf-8",errors="ignore")#忽略乱码
            #读不到就进入下个文件
            except Exception as e:
                continue

            #获取相对路径：下一台电脑也能用：现在的文件绝对路径-开始的self.repo_path根目录
            rel_path = file_path.relative_to(self.repo_path)
            #2.构建元数据
            metadata = {
                #来源，文件名，后缀
                #rel_path是一个复杂的path类型，但是数据库在读取的时候接受不了，转为str
                "source" : str(rel_path),
                "file_name" : file_path.name, #Path类封装的好处：各种需要调用的数据变为成员变量
                "suffix" : file_path.suffix,

            }

            #将内容和元数据打包成标准生态Document类
            doc = Document(page_content = text,metadata = metadata)
            docs.append(doc)
        return docs

            