这是一份为你量身定制的 `README.md` 文件。它不仅总结了你们目前完成的所有架构和模块，还详细列出了 Shell 中所有支持的指令及其使用案例。

你可以直接将以下内容复制并保存为项目根目录下的 `README.md` 文件：

```markdown
# 💻 操作系统模拟器 (OS Simulator)

这是一个基于 Python 开发的小型操作系统模拟原型。系统采用**事件驱动与全局时钟机制**，模拟了真实操作系统的核心行为，包含完整的进程调度、内存分配追踪以及树状文件系统管理。

本系统旨在深入理解操作系统的内部机制，通过命令行（Shell）与内核直接交互，并实现了对系统资源的实时可视化监控。

## ⚙️ 核心模块特性

* [cite_start]**进程管理 (Process Manager)**：支持进程的创建、撤销、阻塞与唤醒 [cite: 40][cite_start]。内置动态时间片轮转与优先级调度算法。进程会在就绪队列、运行队列和阻塞队列之间自动流转 [cite: 45]。
* [cite_start]**内存管理 (Memory Manager)**：模拟物理内存分页管理（默认页面大小 1K，总容量 32 页） [cite: 73, 74]。提供内存分配与回收接口，并拥有独立的后台线程实时打印内存位图（Bitmap）、使用率及外部碎片状态。
* [cite_start]**文件系统 (File Manager)**：基于内存构建的树状虚拟文件系统。支持多级目录管理、文件读写、属性查看以及将整个虚拟磁盘状态持久化（Save/Load）到本地 [cite: 80, 81]。

---

## 🚀 如何运行

系统要求：Python 3.7+

在终端或命令行中进入项目根目录，运行主程序即可启动虚拟操作系统的 Shell 交互界面：

```bash
python main.py
```

*注意：启动后，后台将自动开启一个硬件时钟线程（Tick Thread），以 1 秒为单位推动进程运行和时间片消耗。*

---

## 📖 指令速查手册 (Shell Commands)

在 `root@os-sim#` 提示符下，你可以输入以下指令来控制操作系统。

### 1. 进程管理指令

| 指令 | 语法与参数 | 功能描述 |
| :--- | :--- | :--- |
| **create_process** | `create_process <name> <pri> <time> [pages]` | [cite_start]创建新进程 [cite: 40]。参数分别为：进程名、优先级(越大越高)、需要运行的总时间(秒)、申请的内存页数(可选，默认1)。 |
| **ps** | `ps` | [cite_start]打印当前系统的进程队列状态 [cite: 51][cite_start]，包含正在运行、就绪和阻塞的进程详细属性 [cite: 41]。 |
| **kill** | `kill <pid>` | [cite_start]强制结束指定 PID 的进程，并回收其占用的内存资源 [cite: 40]。 |
| **block** | `block <pid>` | [cite_start]将指定进程挂起（移入阻塞队列） [cite: 45]。 |
| **unblock** | `unblock <pid>` | [cite_start]将阻塞的进程唤醒（移回就绪队列） [cite: 45]。 |

**💡 使用案例：**
```bash
# 创建一个名为 p1 的进程，优先级为 10，需要运行 50 秒，申请 3 页内存
root@os-sim# create_process p1 10 50 3
# 查看当前进程在各个队列中的状态
root@os-sim# ps
# 挂起 PID 为 1 的进程
root@os-sim# block 1
```

### 2. 内存管理指令

| 指令 | 语法与参数 | 功能描述 |
| :--- | :--- | :--- |
| **mem** | `mem` | 主动打印当前内存的详细状态，包括位图、空闲/占用页数及分配表。 |

*注：内存追踪器会在后台自动定时打印状态变化，当你创建或销毁进程导致内存改变时即可观察到。*

### 3. 文件系统指令

| 指令 | 语法与参数 | 功能描述 |
| :--- | :--- | :--- |
| **mkdir** | `mkdir <path>` | [cite_start]创建新目录 [cite: 80]。 |
| **rmdir** | `rmdir <path>` | [cite_start]删除空目录 [cite: 80]。 |
| **ls** | `ls [path]` | [cite_start]列出目标目录下的文件和子目录（默认当前目录） [cite: 81]。 |
| **cd** | `cd <path>` | [cite_start]切换当前工作目录 [cite: 81]。 |
| **pwd** | `pwd` | [cite_start]显示当前所在的工作路径 [cite: 81]。 |
| **touch** | `touch <path>` | [cite_start]创建一个空文件，若文件存在则更新修改时间 [cite: 80]。 |
| **cat** | `cat <path>` | 在终端打印文件的内容。 |
| **write** | `write <path> <content>` | 向指定文件写入内容（会覆盖原有内容）。 |
| **append** | `append <path> <content>`| 向指定文件追加内容。 |
| **rm** | `rm <path>` | [cite_start]删除指定文件 [cite: 80]。 |
| **info** | `info <path>` | [cite_start]查看文件或目录的详细属性信息（大小、创建/修改时间等） [cite: 81]。 |
| **save** | `save` | 将当前整个虚拟文件系统的状态序列化保存到本地硬盘。 |
| **load** | `load` | 从本地硬盘读取并恢复之前保存的虚拟文件系统状态。 |

**💡 使用案例：**
```bash
# 创建一个工作目录并进入
root@os-sim# mkdir /home
root@os-sim# cd /home

# 创建一个文本文件并写入内容
root@os-sim# touch readme.txt
root@os-sim# write readme.txt Hello, this is OS Simulator!
root@os-sim# append readme.txt Welcome to use it.

# 查看文件内容和属性
root@os-sim# cat readme.txt
root@os-sim# info readme.txt

# 保存整个文件系统树以备下次启动时恢复
root@os-sim# save
```

### 4. 系统指令

| 指令 | 语法与参数 | 功能描述 |
| :--- | :--- | :--- |
| **help** | `help` | 打印所有可用指令的快速速查表。 |
| **exit** | `exit` | 安全关闭系统时钟和所有线程，退出模拟器。 |

---

## 👥 开发团队 (Team Members)

* **进程管理模块**：[填写组员姓名]
* **内存管理模块**：[填写组员姓名]
* **文件系统模块**：[填写组员姓名]
* **交互终端与系统集成 (Shell)**：[填写你的姓名]
* **[未定/其他模块]**：[填写组员姓名]

**本项目为操作系统课程设计最终交付物。**