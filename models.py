# models.py
from enum import Enum
from typing import List

class ProcessState(str, Enum):
    NEW = "NEW"
    READY = "READY"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    TERMINATED = "TERMINATED"

class PCB:
    """进程控制块"""
    def __init__(self, pid: int, name: str, priority: int, required_time: int):
        self.pid = pid
        self.name = name
        self.priority = priority
        self.required_time = required_time  # 进程总共需要的 CPU 时间
        self.run_time = 0                   # 已运行时间
        self.time_slice = 0                 # 当前时间片
        self.state = ProcessState.READY
        self.memory_pages: List[int] = []   # 占用的物理内存页索引