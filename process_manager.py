from __future__ import annotations

from collections import deque
from enum import Enum
from pathlib import Path
from threading import RLock
from typing import Deque, Dict, List, Optional

from models import PCB, ProcessState


class ScheduleAlgorithm(str, Enum):
    """支持的调度算法"""

    FCFS = "fcfs"               # 先来先服务（非抢占）
    RR = "rr"                   # 轮转调度
    PRIORITY_RR = "priority_rr" # 优先级 + 时间片轮转


class ProcessManager:
    """
    进程管理与单处理器调度器。

    设计目标：
    1. 支持进程创建、撤销（终止）。
    2. 维护 PCB、就绪队列、阻塞队列、运行进程。
    3. 支持 FCFS / RR / 优先级+时间片 三种算法。
    4. 支持动态优先级（运行进程降级、就绪进程老化提升）。
    5. 提供快照、日志、导出等接口，方便 main.py 直接调用。

    时间语义：
    - 1 次 tick() 表示过去了 1 个系统时钟周期（可视为 1 秒）。
    - main.py 可以用一个全局时钟线程/循环每秒调用一次 tick()。
    """

    def __init__(
        self,
        algorithm: ScheduleAlgorithm | str = ScheduleAlgorithm.PRIORITY_RR,
        default_time_slice: int = 1,
        dynamic_priority: bool = True,
        aging_enabled: bool = True,
        aging_interval: int = 3,
        min_priority: int = 0,
        max_priority: int = 31,
        verbose: bool = False,
    ) -> None:
        self.algorithm = self._normalize_algorithm(algorithm)
        self.default_time_slice = max(1, int(default_time_slice))
        self.dynamic_priority = dynamic_priority
        self.aging_enabled = aging_enabled
        self.aging_interval = max(1, int(aging_interval))
        self.min_priority = int(min_priority)
        self.max_priority = int(max_priority)
        self.verbose = verbose

        self.clock: int = 0
        self._next_pid: int = 1
        self._lock = RLock()

        self.process_table: Dict[int, PCB] = {}
        self.ready_queue: Deque[int] = deque()
        self.blocked_queue: Dict[int, PCB] = {}
        self.running_pid: Optional[int] = None
        self.terminated_pids: List[int] = []
        self.logs: List[str] = []

    # =========================
    # 对外公共接口
    # =========================
    def create_process(
        self,
        name: str,
        total_time: int,
        priority: int = 10,
        time_slice: Optional[int] = None,
        parent_pid: Optional[int] = None,
        memory_required: int = 0,
        resource_request: str = "CPU",
        auto_schedule: bool = True,
    ) -> PCB:
        """创建进程并进入就绪队列。"""
        with self._lock:
            if total_time <= 0:
                raise ValueError("total_time 必须大于 0")

            pid = self._alloc_pid()
            pcb = PCB(
                pid=pid,
                name=name,
                total_time=int(total_time),
                remaining_time=int(total_time),
                priority=self._clamp_priority(priority),
                time_slice=max(1, int(time_slice or self.default_time_slice)),
                state=ProcessState.READY,
                parent_pid=parent_pid,
                created_at=self.clock,
                last_ready_at=self.clock,
                memory_required=int(memory_required),
                resource_request=resource_request,
            )
            self.process_table[pid] = pcb
            self._enqueue_ready(pid)

            if parent_pid is not None and parent_pid in self.process_table:
                self.process_table[parent_pid].children.append(pid)

            self._log(
                f"创建进程 PID={pid}, name={name}, total_time={total_time}, "
                f"priority={pcb.priority}, time_slice={pcb.time_slice}, parent={parent_pid}"
            )

            if auto_schedule and self.running_pid is None:
                self._dispatch_next_process()

            return pcb

    def fork_process(
        self,
        parent_pid: int,
        child_name: Optional[str] = None,
        total_time: Optional[int] = None,
        priority: Optional[int] = None,
        time_slice: Optional[int] = None,
        auto_schedule: bool = True,
    ) -> PCB:
        """由父进程派生一个子进程，满足‘运行过程中也可创建进程’的需求。"""
        with self._lock:
            parent = self.get_process(parent_pid)
            return self.create_process(
                name=child_name or f"{parent.name}_child",
                total_time=total_time if total_time is not None else max(1, parent.remaining_time // 2 or 1),
                priority=priority if priority is not None else parent.priority,
                time_slice=time_slice if time_slice is not None else parent.time_slice,
                parent_pid=parent_pid,
                auto_schedule=auto_schedule,
            )

    def kill_process(self, pid: int, purge: bool = False) -> PCB:
        """
        撤销/终止进程。
        purge=False：PCB 仍保留在 process_table，方便展示生命周期。
        purge=True ：从 process_table 中彻底删除。
        """
        with self._lock:
            pcb = self.get_process(pid)
            if pcb.state == ProcessState.TERMINATED:
                return pcb

            if self.running_pid == pid:
                self.running_pid = None
            else:
                self._remove_from_ready(pid)
                self.blocked_queue.pop(pid, None)

            pcb.state = ProcessState.TERMINATED
            pcb.remaining_time = 0
            pcb.slice_used = 0
            pcb.block_remaining = None
            pcb.block_reason = ""

            if pid not in self.terminated_pids:
                self.terminated_pids.append(pid)

            self._log(f"撤销进程 PID={pid}, name={pcb.name}")

            if purge:
                del self.process_table[pid]
                self.terminated_pids = [x for x in self.terminated_pids if x != pid]
                self._log(f"彻底删除 PCB: PID={pid}")

            if self.running_pid is None:
                self._dispatch_next_process()

            return pcb

    delete_process = kill_process

    def block_process(self, pid: int, reason: str = "I/O", duration: Optional[int] = None) -> PCB:
        """将进程阻塞；duration=None 表示无限期阻塞，需要手动唤醒。"""
        with self._lock:
            pcb = self.get_process(pid)
            if pcb.state == ProcessState.TERMINATED:
                raise ValueError(f"进程 PID={pid} 已终止，不能阻塞")

            if self.running_pid == pid:
                self.running_pid = None
            else:
                self._remove_from_ready(pid)

            pcb.state = ProcessState.BLOCKED
            pcb.block_reason = reason
            pcb.block_remaining = None if duration is None else max(0, int(duration))
            pcb.slice_used = 0
            self.blocked_queue[pid] = pcb

            if duration is None:
                self._log(f"阻塞进程 PID={pid}, reason={reason}, duration=manual")
            else:
                self._log(f"阻塞进程 PID={pid}, reason={reason}, duration={duration}")

            if self.running_pid is None:
                self._dispatch_next_process()

            return pcb

    def unblock_process(self, pid: int) -> PCB:
        """手动唤醒阻塞进程，放回就绪队列。"""
        with self._lock:
            if pid not in self.blocked_queue:
                raise ValueError(f"PID={pid} 不在阻塞队列中")

            pcb = self.blocked_queue.pop(pid)
            pcb.state = ProcessState.READY
            pcb.block_reason = ""
            pcb.block_remaining = None
            pcb.last_ready_at = self.clock
            pcb.slice_used = 0
            self._enqueue_ready(pid)
            self._log(f"唤醒进程 PID={pid}, name={pcb.name}")

            self._maybe_preempt_for_higher_priority()
            if self.running_pid is None:
                self._dispatch_next_process()
            return pcb

    wake_process = unblock_process

    def set_algorithm(self, algorithm: ScheduleAlgorithm | str) -> None:
        with self._lock:
            self.algorithm = self._normalize_algorithm(algorithm)
            self._sort_ready_queue()
            self._log(f"切换调度算法 -> {self.algorithm.value}")
            self._maybe_preempt_for_higher_priority()

    def tick(self, steps: int = 1) -> None:
        """推进系统时钟。每 1 step 表示 1 个调度周期。"""
        with self._lock:
            if steps <= 0:
                return
            for _ in range(int(steps)):
                self._tick_once()

    def run_until_all_finished(self, max_ticks: int = 10_000) -> None:
        """持续运行直到所有非终止进程都结束，便于演示/测试。"""
        with self._lock:
            count = 0
            while self.has_alive_process() and count < max_ticks:
                self._tick_once()
                count += 1
            if count >= max_ticks:
                self._log("达到 max_ticks，强制停止 run_until_all_finished")

    def has_alive_process(self) -> bool:
        with self._lock:
            return any(pcb.state != ProcessState.TERMINATED for pcb in self.process_table.values())

    def get_process(self, pid: int) -> PCB:
        pcb = self.process_table.get(pid)
        if pcb is None:
            raise ValueError(f"找不到 PID={pid} 对应的进程")
        return pcb

    def list_processes(self) -> List[PCB]:
        with self._lock:
            return sorted(self.process_table.values(), key=lambda pcb: pcb.pid)

    def get_queue_snapshot(self) -> dict:
        with self._lock:
            return {
                "clock": self.clock,
                "algorithm": self.algorithm.value,
                "running": self._pcb_to_dict(self.process_table[self.running_pid]) if self.running_pid else None,
                "ready": [self._pcb_to_dict(self.process_table[pid]) for pid in self.ready_queue],
                "blocked": [self._pcb_to_dict(pcb) for pcb in self.blocked_queue.values()],
                "terminated": [self._pcb_to_dict(self.process_table[pid]) for pid in self.terminated_pids if pid in self.process_table],
            }

    def format_process_table(self) -> str:
        with self._lock:
            headers = [
                "PID", "Name", "State", "Priority", "Remain", "Slice", "CPU Used", "Parent", "Block",
            ]
            rows: List[List[str]] = []
            for pcb in self.list_processes():
                rows.append([
                    str(pcb.pid),
                    pcb.name,
                    pcb.state.value,
                    str(pcb.priority),
                    str(pcb.remaining_time),
                    f"{pcb.slice_used}/{pcb.time_slice}",
                    str(pcb.cpu_time_used),
                    str(pcb.parent_pid) if pcb.parent_pid is not None else "-",
                    pcb.block_reason or "-",
                ])
            return self._render_table(headers, rows)

    def format_queues(self) -> str:
        with self._lock:
            running = self.process_table[self.running_pid].name if self.running_pid else "None"
            running_pid = self.running_pid if self.running_pid else "-"
            ready = [f"{pid}:{self.process_table[pid].name}(P={self.process_table[pid].priority})" for pid in self.ready_queue]
            blocked = [f"{pid}:{pcb.name}[{pcb.block_reason or 'BLOCK'}]" for pid, pcb in self.blocked_queue.items()]
            terminated = [f"{pid}:{self.process_table[pid].name}" for pid in self.terminated_pids if pid in self.process_table]
            return (
                f"Clock      : {self.clock}\n"
                f"Algorithm  : {self.algorithm.value}\n"
                f"Running    : {running_pid}:{running}\n"
                f"Ready      : {ready if ready else []}\n"
                f"Blocked    : {blocked if blocked else []}\n"
                f"Terminated : {terminated if terminated else []}"
            )

    def export_log(self, file_path: str | Path) -> None:
        with self._lock:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(self.logs), encoding="utf-8")

    def clear_log(self) -> None:
        with self._lock:
            self.logs.clear()

    def reset(self) -> None:
        with self._lock:
            self.clock = 0
            self._next_pid = 1
            self.process_table.clear()
            self.ready_queue.clear()
            self.blocked_queue.clear()
            self.running_pid = None
            self.terminated_pids.clear()
            self.logs.clear()

    # =========================
    # 核心调度逻辑
    # =========================
    def _tick_once(self) -> None:
        self.clock += 1
        self._log(f"===== TICK {self.clock} =====")

        # 1. 更新阻塞队列
        self._update_blocked_processes()

        # 2. 就绪队列老化（提升长期等待进程优先级）
        self._apply_ready_queue_aging()

        # 3. 优先级算法下，如果出现更高优先级进程，则抢占当前运行进程
        self._maybe_preempt_for_higher_priority()

        # 4. 若 CPU 空闲，则调度一个进程上 CPU
        if self.running_pid is None:
            self._dispatch_next_process()

        # 5. 如果依然没有进程可运行，CPU 空闲
        if self.running_pid is None:
            self._log("CPU 空闲")
            return

        # 6. 当前运行进程执行 1 个 tick
        pcb = self.process_table[self.running_pid]
        pcb.state = ProcessState.RUNNING
        pcb.remaining_time -= 1
        pcb.cpu_time_used += 1
        pcb.slice_used += 1
        pcb.waiting_time = 0
        self._log(
            f"运行进程 PID={pcb.pid}, name={pcb.name}, remaining={pcb.remaining_time}, "
            f"slice={pcb.slice_used}/{pcb.time_slice}, priority={pcb.priority}"
        )

        # 7. 执行结束：完成 / 继续 / 时间片到期
        if pcb.remaining_time <= 0:
            self._finish_running_process()
        elif self.algorithm == ScheduleAlgorithm.FCFS:
            # FCFS 非抢占，只要没结束就继续保持运行态
            pass
        elif pcb.slice_used >= pcb.time_slice:
            self._on_time_slice_expired()

        # 8. 若当前 CPU 为空，为下一拍预选一个进程（不执行，只改变状态）
        if self.running_pid is None:
            self._dispatch_next_process()

    def _dispatch_next_process(self) -> Optional[PCB]:
        if self.running_pid is not None:
            return self.process_table[self.running_pid]
        next_pid = self._pop_next_ready()
        if next_pid is None:
            return None
        pcb = self.process_table[next_pid]
        pcb.state = ProcessState.RUNNING
        pcb.last_scheduled_at = self.clock
        pcb.slice_used = 0
        self.running_pid = next_pid
        self._log(f"调度进程上 CPU: PID={pcb.pid}, name={pcb.name}, priority={pcb.priority}")
        return pcb

    def _finish_running_process(self) -> None:
        pid = self.running_pid
        if pid is None:
            return
        pcb = self.process_table[pid]
        pcb.state = ProcessState.TERMINATED
        pcb.remaining_time = 0
        pcb.slice_used = 0
        self.running_pid = None
        if pid not in self.terminated_pids:
            self.terminated_pids.append(pid)
        self._log(f"进程结束 PID={pcb.pid}, name={pcb.name}")

    def _on_time_slice_expired(self) -> None:
        pid = self.running_pid
        if pid is None:
            return
        pcb = self.process_table[pid]

        # 动态优先级：正在运行且时间片耗尽但未完成，则适度降低优先级
        if self.dynamic_priority and self.algorithm == ScheduleAlgorithm.PRIORITY_RR:
            old = pcb.priority
            pcb.priority = self._clamp_priority(pcb.priority - 1)
            if pcb.priority != old:
                self._log(f"动态优先级调整: PID={pcb.pid} {old} -> {pcb.priority}")

        pcb.state = ProcessState.READY
        pcb.last_ready_at = self.clock
        pcb.slice_used = 0
        self.running_pid = None
        self._enqueue_ready(pid)
        self._log(f"时间片到：进程回到就绪队列 PID={pcb.pid}, name={pcb.name}")

    def _maybe_preempt_for_higher_priority(self) -> None:
        if self.algorithm != ScheduleAlgorithm.PRIORITY_RR:
            return
        if self.running_pid is None:
            return
        if not self.ready_queue:
            return

        self._sort_ready_queue()
        current = self.process_table[self.running_pid]
        candidate = self.process_table[self.ready_queue[0]]

        # 候选进程优先级更高时抢占
        if candidate.priority > current.priority:
            current.state = ProcessState.READY
            current.last_ready_at = self.clock
            current.slice_used = 0
            old_pid = self.running_pid
            self.running_pid = None
            self._enqueue_ready(old_pid)
            self._log(
                f"高优先级抢占: PID={candidate.pid}({candidate.priority}) "
                f"抢占 PID={current.pid}({current.priority})"
            )

    def _update_blocked_processes(self) -> None:
        ready_to_wake: List[int] = []
        for pid, pcb in list(self.blocked_queue.items()):
            if pcb.block_remaining is None:
                continue
            if pcb.block_remaining > 0:
                pcb.block_remaining -= 1
            if pcb.block_remaining == 0:
                ready_to_wake.append(pid)

        for pid in ready_to_wake:
            pcb = self.blocked_queue.pop(pid)
            pcb.state = ProcessState.READY
            pcb.block_reason = ""
            pcb.block_remaining = None
            pcb.last_ready_at = self.clock
            self._enqueue_ready(pid)
            self._log(f"阻塞结束，返回就绪队列 PID={pcb.pid}, name={pcb.name}")

    def _apply_ready_queue_aging(self) -> None:
        if not (self.aging_enabled and self.dynamic_priority and self.algorithm == ScheduleAlgorithm.PRIORITY_RR):
            return

        changed = False
        for pid in list(self.ready_queue):
            pcb = self.process_table[pid]
            pcb.waiting_time += 1
            if pcb.waiting_time > 0 and pcb.waiting_time % self.aging_interval == 0:
                old = pcb.priority
                pcb.priority = self._clamp_priority(pcb.priority + 1)
                if pcb.priority != old:
                    changed = True
                    self._log(f"老化提升优先级: PID={pcb.pid} {old} -> {pcb.priority}")

        if changed:
            self._sort_ready_queue()

    # =========================
    # 队列与数据结构辅助函数
    # =========================
    def _alloc_pid(self) -> int:
        pid = self._next_pid
        self._next_pid += 1
        return pid

    def _enqueue_ready(self, pid: int) -> None:
        if pid not in self.process_table:
            return
        if pid in self.ready_queue:
            return
        pcb = self.process_table[pid]
        if pcb.state != ProcessState.TERMINATED:
            pcb.state = ProcessState.READY
        self.ready_queue.append(pid)
        self._sort_ready_queue()

    def _pop_next_ready(self) -> Optional[int]:
        self._sort_ready_queue()
        while self.ready_queue:
            pid = self.ready_queue.popleft()
            pcb = self.process_table.get(pid)
            if pcb is None:
                continue
            if pcb.state == ProcessState.TERMINATED:
                continue
            if pid in self.blocked_queue:
                continue
            return pid
        return None

    def _remove_from_ready(self, pid: int) -> bool:
        try:
            self.ready_queue.remove(pid)
            return True
        except ValueError:
            return False

    def _sort_ready_queue(self) -> None:
        if not self.ready_queue:
            return

        if self.algorithm == ScheduleAlgorithm.PRIORITY_RR:
            ordered = sorted(
                self.ready_queue,
                key=lambda pid: (
                    -self.process_table[pid].priority,
                    self.process_table[pid].last_ready_at,
                    self.process_table[pid].pid,
                ),
            )
            self.ready_queue = deque(ordered)
        # RR / FCFS 保持进入队列的先后顺序，不重排

    # =========================
    # 其他辅助函数
    # =========================
    def _normalize_algorithm(self, algorithm: ScheduleAlgorithm | str) -> ScheduleAlgorithm:
        if isinstance(algorithm, ScheduleAlgorithm):
            return algorithm
        value = str(algorithm).strip().lower()
        for item in ScheduleAlgorithm:
            if item.value == value:
                return item
        raise ValueError(f"不支持的调度算法: {algorithm}")

    def _clamp_priority(self, priority: int) -> int:
        return max(self.min_priority, min(self.max_priority, int(priority)))

    def _pcb_to_dict(self, pcb: PCB) -> dict:
        return {
            "pid": pcb.pid,
            "name": pcb.name,
            "state": pcb.state.value,
            "priority": pcb.priority,
            "total_time": pcb.total_time,
            "remaining_time": pcb.remaining_time,
            "time_slice": pcb.time_slice,
            "slice_used": pcb.slice_used,
            "cpu_time_used": pcb.cpu_time_used,
            "parent_pid": pcb.parent_pid,
            "created_at": pcb.created_at,
            "last_ready_at": pcb.last_ready_at,
            "last_scheduled_at": pcb.last_scheduled_at,
            "block_reason": pcb.block_reason,
            "block_remaining": pcb.block_remaining,
        }

    def _log(self, message: str) -> None:
        line = f"[t={self.clock:04d}] {message}"
        self.logs.append(line)
        if self.verbose:
            print(line)

    @staticmethod
    def _render_table(headers: List[str], rows: List[List[str]]) -> str:
        if not rows:
            return "(暂无进程)"
        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(cell))

        def render_row(row: List[str]) -> str:
            return " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))

        sep = "-+-".join("-" * width for width in widths)
        return "\n".join([
            render_row(headers),
            sep,
            *[render_row(row) for row in rows],
        ])


if __name__ == "__main__":
    # 直接运行本文件时，给出一个最小演示
    pm = ProcessManager(
        algorithm=ScheduleAlgorithm.PRIORITY_RR,
        default_time_slice=1,
        dynamic_priority=True,
        aging_enabled=True,
        verbose=True,
    )

    pm.create_process("P1", total_time=5, priority=3)
    pm.create_process("P2", total_time=3, priority=5)
    pm.create_process("P3", total_time=4, priority=4)

    for _ in range(4):
        pm.tick()

    pm.block_process(1, reason="I/O", duration=2)
    pm.tick(5)

    print("\n=== 队列快照 ===")
    print(pm.format_queues())

    print("\n=== 进程表 ===")
    print(pm.format_process_table())

    print("\n=== 日志 ===")
    print("\n".join(pm.logs))
