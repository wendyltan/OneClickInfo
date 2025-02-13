import sys
import os
import tkinter as tk
from tkinter import messagebox
import psutil
import socket
import platform
import subprocess
import pyperclip
import ctypes

def is_admin():
    """检查是否以管理员权限运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """以管理员权限重新运行脚本"""
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit()

def run_command_silently(command):
    """运行命令并禁止显示 cmd 窗口"""
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return subprocess.check_output(command, startupinfo=startupinfo, shell=True)

def get_network_info():
    """获取有线网卡的 MAC 地址、IPv4 地址、网关、DNS 和子网掩码信息"""
    network_info = {}

    # 获取 MAC 地址和 IPv4 地址
    for interface, addrs in psutil.net_if_addrs().items():
        # 排除环回接口
        if interface.lower() == "loopback" or interface.lower().startswith("lo"):
            continue

        for addr in addrs:
            if addr.family == psutil.AF_LINK:  # MAC 地址
                network_info['MAC 地址'] = addr.address
            elif addr.family == socket.AF_INET:  # IPv4 地址
                # 排除环回地址
                if not addr.address.startswith("127."):
                    network_info['IPv4 地址'] = addr.address
                    network_info['子网掩码'] = addr.netmask
                    break  # 优先获取第一个非环回地址
        if 'IPv4 地址' in network_info:
            break  # 找到非环回接口后退出

    # 获取网关和 DNS
    try:
        ipconfig_output = run_command_silently("chcp 65001 && ipconfig /all").decode('utf-8', errors='ignore')
        lines = ipconfig_output.splitlines()
        for i, line in enumerate(lines):
            if "默认网关" in line or "Default Gateway" in line:  # 网关
                gateway = line.split(":")[1].strip()
                if gateway:
                    network_info['网关'] = gateway
            elif "DNS Servers" in line:  # DNS
                if 'DNS' not in network_info:
                    network_info['DNS'] = []
                dns = line.split(":")[1].strip()
                if dns and dns not in network_info['DNS']:  # 避免重复
                    network_info['DNS'].append(dns)
    except Exception as e:
        print(f"获取网关或 DNS 时出错: {e}")

    # 格式化 DNS 信息
    if 'DNS' in network_info and isinstance(network_info['DNS'], list):
        network_info['DNS'] = ", ".join(network_info['DNS'])

    return network_info


def get_system_info():
    """获取系统信息"""
    return {
        '计算机名称': socket.gethostname(),
        '系统版本': platform.platform()
    }

def get_disk_info():
    """获取分区数量、分区大小和使用情况"""
    disk_info = []
    for partition in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            disk_info.append({
                '分区名称': partition.device,
                '挂载点': partition.mountpoint,
                '总大小': f"{usage.total / (1024 ** 3):.2f} GB",
                '已用大小': f"{usage.used / (1024 ** 3):.2f} GB",
                '使用率': f"{usage.percent}%"
            })
        except Exception:
            # 静默跳过无法访问的分区
            continue

    return disk_info

def get_memory_info():
    """获取内存信息"""
    virtual_memory = psutil.virtual_memory()
    swap_memory = psutil.swap_memory()
    memory_info = {
        '总内存': f"{virtual_memory.total / (1024 ** 3):.2f} GB",
        '可用内存': f"{virtual_memory.available / (1024 ** 3):.2f} GB",
        '内存使用率': f"{virtual_memory.percent}%",
        '总交换内存': f"{swap_memory.total / (1024 ** 3):.2f} GB",
        '交换内存使用率': f"{swap_memory.percent}%"
    }

    try:
        memory_slots = run_command_silently(["wmic", "memorychip", "get", "Capacity,Manufacturer,PartNumber"]).decode('utf-8', errors='ignore')
        memory_slots = memory_slots.strip().splitlines()
        memory_info['内存条信息'] = [
            f"{int(slot.split()[0]) / (1024 ** 3):.2f} GB ({slot.split()[1]} - {slot.split()[2]})"
            for slot in memory_slots[1:] if len(slot.split()) >= 3
        ]
    except Exception as e:
        memory_info['内存条信息'] = ["无法获取内存条信息（可能需要管理员权限）"]

    return memory_info

def query_and_display():
    """查询信息并显示在 GUI 中"""
    try:
        info = {
            "网络信息": get_network_info(),
            "系统信息": get_system_info(),
            "内存信息": get_memory_info(),
            "硬盘分区信息": get_disk_info()
        }

        text_box.config(state=tk.NORMAL)
        text_box.delete(1.0, tk.END)

        for section, data in info.items():
            text_box.insert(tk.END, f"{section}:\n")
            if isinstance(data, dict):
                for key, value in data.items():
                    if key == '内存条信息' and isinstance(value, list):
                        text_box.insert(tk.END, f"{key}:\n")
                        for i, slot in enumerate(value):
                            text_box.insert(tk.END, f"内存条 {i + 1}: {slot}\n")
                    else:
                        text_box.insert(tk.END, f"{key}: {value}\n")
            elif isinstance(data, list):
                for item in data:
                    for key, value in item.items():
                        text_box.insert(tk.END, f"{key}: {value}\n")
                    text_box.insert(tk.END, "\n")
            text_box.insert(tk.END, "=" * 60 + "\n")

        # 检查是否需要管理员权限
        if not is_admin() and ("无法获取内存条信息" in str(info["内存信息"])):
            admin_button.grid()  # 显示管理员权限按钮
            messagebox.showwarning("提示", "部分信息需要管理员权限才能获取，请点击按钮以获取权限。")
        else:
            admin_button.grid_remove()  # 隐藏管理员权限按钮

        text_box.config(state=tk.DISABLED)
    except Exception as e:
        messagebox.showerror("错误", f"获取信息时出错: {e}")

def copy_to_clipboard():
    """将文本框中的内容复制到剪贴板"""
    pyperclip.copy(text_box.get(1.0, tk.END))
    messagebox.showinfo("成功", "信息已复制到剪贴板")

def show_about():
    """显示关于信息"""
    about_message = (
        "Oneclickinfo v1.0\n\n"
        "理论上可运行于 Win7-Win11 64位或32位版本的 Windows 上。\n"
        "如遇使用问题，请联系qq:915889513@qq.com"
    )
    messagebox.showinfo("关于", about_message)

def load_icon():
    """加载图标文件"""
    try:
        # 如果是打包后的程序，使用 sys._MEIPASS 获取资源路径
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(base_path, 'app.ico')
        root.iconbitmap(icon_path)
    except Exception as e:
        print(f"无法加载图标: {e}")

# 创建 GUI 窗口
root = tk.Tk()
root.title("电脑信息一键查询工具")
root.geometry("1000x900")

# 加载图标
load_icon()

# 创建菜单栏
menu_bar = tk.Menu(root)
root.config(menu=menu_bar)

# 添加“关于”菜单
about_menu = tk.Menu(menu_bar, tearoff=0)
about_menu.add_command(label="关于", command=show_about)
menu_bar.add_cascade(label="帮助", menu=about_menu)

# 创建查询按钮
query_button = tk.Button(root, text="一键查询电脑信息", command=query_and_display)
query_button.grid(row=0, column=0, pady=10, sticky="ew")  # 第一行

# 创建文本框用于显示信息
text_box = tk.Text(root, height=30, width=100)
text_box.grid(row=1, column=0, pady=10, sticky="nsew")  # 第二行

# 创建滚动条
scrollbar = tk.Scrollbar(root)
scrollbar.grid(row=1, column=1, sticky="ns")  # 放置在文本框右侧

# 关联滚动条和文本框
text_box.config(yscrollcommand=scrollbar.set)
scrollbar.config(command=text_box.yview)

# 创建复制按钮
copy_button = tk.Button(root, text="一键复制信息", command=copy_to_clipboard)
copy_button.grid(row=2, column=0, pady=10, sticky="ew")  # 第三行

# 创建管理员权限按钮（初始状态为隐藏）
admin_button = tk.Button(root, text="一键获取管理员权限", command=run_as_admin)
admin_button.grid(row=3, column=0, pady=10, sticky="ew")  # 第四行
admin_button.grid_remove()  # 初始状态隐藏

# 配置行和列的权重，使文本框可以随窗口大小调整
root.grid_rowconfigure(1, weight=1)  # 第二行（文本框）可以扩展
root.grid_columnconfigure(0, weight=1)  # 第一列可以扩展

# 运行主循环
root.mainloop()
