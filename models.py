from enum import Enum
import time

class ProcessState(Enum):
    READY = "就绪"
    RUNNING = "运行"
    BLOCKED = "阻塞"
    TERMINATED = "撤销"

class PCB:
    """进程控制块"""
    def __init__(self, pid: int, name: str, priority: int, required_time: int):
        self.pid = pid
        self.name = name
        self.priority = priority        # 进程优先级 [cite: 41]
        self.state = ProcessState.READY # 初始状态为就绪 [cite: 45]
        self.required_time = required_time # 总共需要的运行时间
        self.run_time = 0               # 已运行时间
        self.time_slice = 0             # 分配到的时间片 [cite: 41]
        self.memory_pages = []          # 占用的内存页索引
        # 可以扩展: 占用的设备、打开的文件列表等

class FileNode:
    """文件/目录树节点"""
    def __init__(self, name: str, is_dir: bool):
        self.name = name
        self.is_dir = is_dir
        self.children = {}      # 目录下的子节点
        self.content = ""       # 文件内容 (若是文件)
        self.is_readonly = False # 文件属性 [cite: 81]