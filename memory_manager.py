import threading
import time

class MemoryManager:
    def __init__(
        self,
        total_pages: int = 32,
        monitor_interval: int = 5,
        allocation_policy: str = "first_fit",
        print_on_change_only: bool = True,
    ):
        self.page_size = 1024  # 页面大小为1K [cite: 73]
        # 用户内存容量要求为 4 到 32 页，这里做边界保护避免异常输入。
        self.total_pages = max(4, min(32, int(total_pages)))
        self.memory_bitmap = [0] * self.total_pages  # 0 表示空闲，1 表示占用
        self.page_owner = [None] * self.total_pages  # 记录每页属于哪个 pid
        self.allocations = {}  # pid -> 已分配页列表
        self.lock = threading.Lock()  # 两个线程保持同步 [cite: 68]
        self.monitor_interval = max(1, int(monitor_interval))
        self.allocation_policy = allocation_policy
        self.print_on_change_only = print_on_change_only
        self._last_report_key = None

        # 启动后台监控线程
        self.monitor_thread = threading.Thread(target=self._tracker_thread, daemon=True)
        self.monitor_thread.start()

    def set_allocation_policy(self, policy: str) -> bool:
        """设置分配策略，支持 first_fit / best_fit / worst_fit。"""
        normalized = str(policy).strip().lower()
        if normalized not in {"first_fit", "best_fit", "worst_fit"}:
            return False
        with self.lock:
            self.allocation_policy = normalized
        return True

    def _find_free_segments(self) -> list:
        """返回当前空闲段列表: [(start, length), ...]"""
        segments = []
        start = None

        for idx, used in enumerate(self.memory_bitmap):
            if used == 0 and start is None:
                start = idx
            elif used == 1 and start is not None:
                segments.append((start, idx - start))
                start = None

        if start is not None:
            segments.append((start, self.total_pages - start))

        return segments

    def _choose_segment(self, segments: list, pages_needed: int):
        """根据策略挑选可用空闲段，返回 (start, length) 或 None。"""
        candidates = [seg for seg in segments if seg[1] >= pages_needed]
        if not candidates:
            return None

        if self.allocation_policy == "best_fit":
            return min(candidates, key=lambda seg: seg[1])
        if self.allocation_policy == "worst_fit":
            return max(candidates, key=lambda seg: seg[1])

        # 默认 first_fit
        return candidates[0]

    def allocate(self, pid: int, pages_needed: int) -> list:
        """用于内存分配的接口 [cite: 66]"""
        with self.lock:
            if pages_needed <= 0:
                return []

            if pid <= 0:
                return []

            segments = self._find_free_segments()
            total_free_pages = sum(length for _, length in segments)
            if total_free_pages < pages_needed:
                return []

            selected_pages = []
            chosen_seg = self._choose_segment(segments, pages_needed)
            if chosen_seg:
                start, _ = chosen_seg
                selected_pages = list(range(start, start + pages_needed))

            # 连续段不足时退化为非连续分配，保证可用内存能够被利用。
            if not selected_pages:
                for seg_start, seg_len in segments:
                    for page in range(seg_start, seg_start + seg_len):
                        selected_pages.append(page)
                        if len(selected_pages) == pages_needed:
                            break
                    if len(selected_pages) == pages_needed:
                        break

            for page in selected_pages:
                self.memory_bitmap[page] = 1
                self.page_owner[page] = pid

            if pid in self.allocations:
                self.allocations[pid].extend(selected_pages)
            else:
                self.allocations[pid] = selected_pages

            return selected_pages
            
    def free(self, pid: int, pages: list = None) -> int:
        """释放内存页"""
        with self.lock:
            owned_pages = self.allocations.get(pid, [])
            if pages is None:
                target_pages = owned_pages[:]
            else:
                # 仅释放该进程已占有的页，避免错误释放其他进程页。
                target_pages = [page for page in pages if page in owned_pages]

            freed = 0
            for page in target_pages:
                if 0 <= page < self.total_pages and self.page_owner[page] == pid:
                    self.memory_bitmap[page] = 0
                    self.page_owner[page] = None
                    freed += 1

            if pid in self.allocations:
                if pages is None:
                    self.allocations.pop(pid, None)
                else:
                    remain = [page for page in self.allocations[pid] if page not in target_pages]
                    if remain:
                        self.allocations[pid] = remain
                    else:
                        self.allocations.pop(pid, None)

            return freed

    def can_allocate(self, pages_needed: int, contiguous: bool = False) -> bool:
        """仅做可分配性检查，不修改状态。"""
        with self.lock:
            if pages_needed <= 0:
                return True

            free_pages = sum(1 for used in self.memory_bitmap if used == 0)
            if free_pages < pages_needed:
                return False

            if not contiguous:
                return True

            segments = self._find_free_segments()
            return any(length >= pages_needed for _, length in segments)

    def get_status(self) -> dict:
        """返回当前内存分配快照，供 shell 输出。"""
        with self.lock:
            used_pages = sum(self.memory_bitmap)
            free_pages = self.total_pages - used_pages
            usage_rate = (used_pages / self.total_pages) * 100 if self.total_pages else 0
            free_segments = self._find_free_segments()
            largest_free_block = max((length for _, length in free_segments), default=0)
            external_fragmentation = 0.0
            if free_pages > 0:
                external_fragmentation = (1 - largest_free_block / free_pages) * 100

            return {
                "used_pages": used_pages,
                "free_pages": free_pages,
                "total_pages": self.total_pages,
                "usage_rate": usage_rate,
                "bitmap": "".join(str(x) for x in self.memory_bitmap),
                "page_owner": self.page_owner[:],
                "free_segments": free_segments,
                "largest_free_block": largest_free_block,
                "external_fragmentation": external_fragmentation,
                "allocations": {pid: pages[:] for pid, pages in self.allocations.items()},
                "allocation_policy": self.allocation_policy,
            }

    def compact(self) -> dict:
        """执行内存紧凑，将已分配页向低地址聚拢，降低外部碎片。"""
        with self.lock:
            old_allocations = {pid: pages[:] for pid, pages in self.allocations.items()}

            # 按页号顺序重排，尽量保持每个进程页内相对顺序稳定。
            ordered = sorted(
                ((pid, sorted(pages)) for pid, pages in self.allocations.items()),
                key=lambda item: item[1][0] if item[1] else self.total_pages,
            )

            cursor = 0
            new_allocations = {}
            for pid, pages in ordered:
                count = len(pages)
                if count == 0:
                    continue
                new_pages = list(range(cursor, cursor + count))
                new_allocations[pid] = new_pages
                cursor += count

            self.memory_bitmap = [0] * self.total_pages
            self.page_owner = [None] * self.total_pages
            for pid, pages in new_allocations.items():
                for page in pages:
                    self.memory_bitmap[page] = 1
                    self.page_owner[page] = pid

            self.allocations = new_allocations
            return {
                "before": old_allocations,
                "after": {pid: pages[:] for pid, pages in self.allocations.items()},
            }

    def _tracker_thread(self):
        """用于跟踪内存分配情况，并且打印内存信息的线程 [cite: 67]"""
        while True:
            time.sleep(self.monitor_interval) # 每 monitor_interval 秒打印一次
            report_lines = None
            with self.lock:
                used_pages = sum(self.memory_bitmap)
                free_pages = self.total_pages - used_pages
                usage_rate = (used_pages / self.total_pages) * 100 if self.total_pages else 0
                bitmap_str = "".join(str(x) for x in self.memory_bitmap)
                segments = self._find_free_segments()
                largest_free_block = max((length for _, length in segments), default=0)
                external_fragmentation = 0.0
                if free_pages > 0:
                    external_fragmentation = (1 - largest_free_block / free_pages) * 100

                report_key = (bitmap_str, tuple(sorted((pid, tuple(pages)) for pid, pages in self.allocations.items())))
                if self.print_on_change_only and report_key == self._last_report_key:
                    continue
                self._last_report_key = report_key
                allocations_snapshot = {pid: pages[:] for pid, pages in self.allocations.items()}
                report_lines = [
                    "\n[Memory Tracker]",
                    f"使用率: {usage_rate:.2f}% ({used_pages}/{self.total_pages} 页)",
                    f"空闲页: {free_pages}",
                    f"位图: {bitmap_str}",
                    f"最大连续空闲块: {largest_free_block} 页",
                    f"外部碎片率: {external_fragmentation:.2f}%",
                    f"分配表: {allocations_snapshot if allocations_snapshot else '<empty>'}",
                ]

            if report_lines:
                for line in report_lines:
                    print(line)