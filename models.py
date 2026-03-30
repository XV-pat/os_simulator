from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class ProcessState(str, Enum):
    NEW = "NEW"
    READY = "READY"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    TERMINATED = "TERMINATED"


@dataclass
class PCB:
    """进程控制块（建议与你们小组的 models.py 保持一致）"""

    pid: int
    name: str
    total_time: int                     # 进程总共需要的 CPU 时间（tick）
    remaining_time: int                 # 剩余 CPU 时间
    priority: int = 10                  # 数值越大，优先级越高
    time_slice: int = 1                 # 时间片，默认 1 tick
    state: ProcessState = ProcessState.NEW
    parent_pid: Optional[int] = None

    created_at: int = 0                 # 创建时刻
    last_ready_at: int = 0              # 最近一次进入就绪队列的时刻
    last_scheduled_at: int = -1         # 最近一次被调度的时刻

    cpu_time_used: int = 0              # 已使用 CPU 时间
    waiting_time: int = 0               # 在就绪队列中的累计等待时间
    slice_used: int = 0                 # 当前这次被调度后已使用的时间片

    block_reason: str = ""
    block_remaining: Optional[int] = None   # None 表示无限期阻塞，直到手动唤醒

    memory_required: int = 0            # 预留给内存管理模块使用
    resource_request: str = "CPU"      # 预留给资源竞争展示使用

    children: List[int] = field(default_factory=list)

    def is_finished(self) -> bool:
        return self.remaining_time <= 0 or self.state == ProcessState.TERMINATED
