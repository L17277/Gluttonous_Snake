import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import os
import json
import threading
from datetime import datetime

SCORE_FILE = "scores.txt"
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

class Launcher:
    def __init__(self, root):
        self.root = root
        self.root.title("贪吃蛇启动器 - 完全控制版")
        self.root.geometry("750x780")
        self.root.resizable(False, False)

        # ----- 基本参数 -----
        self.speed_var = tk.IntVar(value=10)
        self.grid_var = tk.IntVar(value=20)
        self.wrap_var = tk.BooleanVar(value=False)

        # ----- 黄点参数 -----
        self.yellow_enabled = tk.BooleanVar(value=True)
        self.yellow_trigger = tk.IntVar(value=6)
        self.yellow_duration = tk.IntVar(value=6)
        self.yellow_base = tk.IntVar(value=3)

        # ----- 蓝点参数 -----
        self.blue_enabled = tk.BooleanVar(value=True)
        self.blue_trigger = tk.IntVar(value=10)
        self.blue_duration = tk.IntVar(value=5)
        self.blue_shrink_mult = tk.IntVar(value=2)

        # ----- 奖励参数（AI 训练）-----
        self.reward_red = tk.DoubleVar(value=10.0)
        self.reward_step = tk.DoubleVar(value=-0.1)
        self.reward_death = tk.DoubleVar(value=-10.0)

        # ----- 运行模式 -----
        self.ai_mode = tk.BooleanVar(value=False)
        self.record_var = tk.BooleanVar(value=False)

        # ----- 历史得分 -----
        self.scores = []
        self.load_scores()

        # ----- 构建界面 -----
        self.build_ui()

        # ----- 子进程管理 -----
        self.game_process = None

    def build_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # === 基础设置 ===
        base_frame = ttk.LabelFrame(main_frame, text="基础设置", padding="5")
        base_frame.pack(fill=tk.X, pady=5)

        ttk.Label(base_frame, text="速度 (帧率):").grid(row=0, column=0, padx=5, sticky='w')
        speed_scale = ttk.Scale(base_frame, from_=5, to=30, orient=tk.HORIZONTAL,
                                variable=self.speed_var, length=120)
        speed_scale.grid(row=0, column=1, padx=5)
        ttk.Label(base_frame, textvariable=self.speed_var, width=4).grid(row=0, column=2, padx=5)

        ttk.Label(base_frame, text="地图大小:").grid(row=0, column=3, padx=15, sticky='w')
        ttk.Spinbox(base_frame, from_=10, to=40, increment=2,
                    textvariable=self.grid_var, width=5).grid(row=0, column=4, padx=5)

        ttk.Label(base_frame, text="边界模式:").grid(row=0, column=5, padx=15, sticky='w')
        ttk.Radiobutton(base_frame, text="死亡", variable=self.wrap_var, value=False).grid(row=0, column=6, padx=2)
        ttk.Radiobutton(base_frame, text="穿墙", variable=self.wrap_var, value=True).grid(row=0, column=7, padx=2)

        # === 黄点设置 ===
        yellow_frame = ttk.LabelFrame(main_frame, text="黄点 (得分倍数触发)", padding="5")
        yellow_frame.pack(fill=tk.X, pady=5)

        ttk.Checkbutton(yellow_frame, text="启用", variable=self.yellow_enabled).grid(row=0, column=0, padx=5)

        ttk.Label(yellow_frame, text="触发倍数:").grid(row=0, column=1, padx=5)
        ttk.Spinbox(yellow_frame, from_=2, to=20, increment=1,
                    textvariable=self.yellow_trigger, width=4).grid(row=0, column=2, padx=5)

        ttk.Label(yellow_frame, text="持续时间(秒):").grid(row=0, column=3, padx=5)
        ttk.Spinbox(yellow_frame, from_=1, to=15, increment=1,
                    textvariable=self.yellow_duration, width=4).grid(row=0, column=4, padx=5)

        ttk.Label(yellow_frame, text="基础分:").grid(row=0, column=5, padx=5)
        ttk.Spinbox(yellow_frame, from_=1, to=10, increment=1,
                    textvariable=self.yellow_base, width=4).grid(row=0, column=6, padx=5)
        ttk.Label(yellow_frame, text="(乘数×基础分)").grid(row=0, column=7, padx=5)

        # === 蓝点设置 ===
        blue_frame = ttk.LabelFrame(main_frame, text="蓝点 (得分倍数触发)", padding="5")
        blue_frame.pack(fill=tk.X, pady=5)

        ttk.Checkbutton(blue_frame, text="启用", variable=self.blue_enabled).grid(row=0, column=0, padx=5)

        ttk.Label(blue_frame, text="触发倍数:").grid(row=0, column=1, padx=5)
        ttk.Spinbox(blue_frame, from_=2, to=20, increment=1,
                    textvariable=self.blue_trigger, width=4).grid(row=0, column=2, padx=5)

        ttk.Label(blue_frame, text="持续时间(秒):").grid(row=0, column=3, padx=5)
        ttk.Spinbox(blue_frame, from_=1, to=15, increment=1,
                    textvariable=self.blue_duration, width=4).grid(row=0, column=4, padx=5)

        ttk.Label(blue_frame, text="减长倍数:").grid(row=0, column=5, padx=5)
        ttk.Spinbox(blue_frame, from_=1, to=5, increment=1,
                    textvariable=self.blue_shrink_mult, width=4).grid(row=0, column=6, padx=5)
        ttk.Label(blue_frame, text="(乘数×倍数)").grid(row=0, column=7, padx=5)

        # === 奖励设计 (AI) ===
        reward_frame = ttk.LabelFrame(main_frame, text="奖励设计 (AI训练用)", padding="5")
        reward_frame.pack(fill=tk.X, pady=5)

        ttk.Label(reward_frame, text="红点奖励:").grid(row=0, column=0, padx=5)
        ttk.Spinbox(reward_frame, from_=-20, to=50, increment=0.5,
                    textvariable=self.reward_red, width=6).grid(row=0, column=1, padx=5)

        ttk.Label(reward_frame, text="每步惩罚:").grid(row=0, column=2, padx=15)
        ttk.Spinbox(reward_frame, from_=-5.0, to=0.0, increment=0.05,
                    textvariable=self.reward_step, width=6).grid(row=0, column=3, padx=5)

        ttk.Label(reward_frame, text="死亡惩罚:").grid(row=0, column=4, padx=15)
        ttk.Spinbox(reward_frame, from_=-50.0, to=0.0, increment=0.5,
                    textvariable=self.reward_death, width=6).grid(row=0, column=5, padx=5)

        # === 运行模式 ===
        mode_frame = ttk.LabelFrame(main_frame, text="运行模式", padding="5")
        mode_frame.pack(fill=tk.X, pady=5)

        ttk.Radiobutton(mode_frame, text="手动游戏", variable=self.ai_mode,
                        value=False).pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(mode_frame, text="AI 训练 (可视化)", variable=self.ai_mode,
                        value=True).pack(side=tk.LEFT, padx=10)
        ttk.Checkbutton(mode_frame, text="记录日志 (仅手动)", variable=self.record_var).pack(side=tk.LEFT, padx=20)

        # === 操作按钮 ===
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)

        self.start_btn = ttk.Button(btn_frame, text="启动", command=self.start)
        self.start_btn.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        self.replay_btn = ttk.Button(btn_frame, text="回放日志", command=self.replay_log)
        self.replay_btn.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        self.stop_btn = ttk.Button(btn_frame, text="停止进程", command=self.stop_process)
        self.stop_btn.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        # === 得分历史 ===
        score_frame = ttk.LabelFrame(main_frame, text="历史得分 (最近20条)", padding="5")
        score_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.score_listbox = tk.Listbox(score_frame, height=6)
        self.score_listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        scrollbar = ttk.Scrollbar(score_frame, orient=tk.VERTICAL, command=self.score_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.score_listbox.config(yscrollcommand=scrollbar.set)

        self.update_score_display()

    def load_scores(self):
        if os.path.exists(SCORE_FILE):
            with open(SCORE_FILE, 'r') as f:
                self.scores = [line.strip() for line in f.readlines() if line.strip()]
        else:
            self.scores = []

    def save_score(self, score_str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"{timestamp}  Score: {score_str}"
        self.scores.append(entry)
        if len(self.scores) > 20:
            self.scores = self.scores[-20:]
        with open(SCORE_FILE, 'w') as f:
            f.write("\n".join(self.scores) + "\n")
        self.update_score_display()

    def update_score_display(self):
        self.score_listbox.delete(0, tk.END)
        for s in self.scores:
            self.score_listbox.insert(tk.END, s)

    def build_command(self):
        """根据当前UI参数构建命令行列表"""
        if self.ai_mode.get():
            # AI 训练模式 → 调用 ai.py
            cmd = ["python", "ai.py", "--ai"]
        else:
            # 手动游戏模式 → 调用 snake_game.py
            cmd = ["python", "snake_game.py"]
            if self.record_var.get():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                log_file = os.path.join(LOG_DIR, f"snake_{timestamp}.log")
                cmd.extend(["--log", log_file])

        # 公共参数（所有模式均需要）
        cmd.extend([
            "--speed", str(self.speed_var.get()),
            "--grid-size", str(self.grid_var.get())
        ])
        if self.wrap_var.get():
            cmd.append("--wrap")

        # 黄点参数
        cmd.extend([
            "--yellow-enabled", str(1 if self.yellow_enabled.get() else 0),
            "--yellow-trigger", str(self.yellow_trigger.get()),
            "--yellow-duration", str(self.yellow_duration.get()),
            "--yellow-base", str(self.yellow_base.get())
        ])

        # 蓝点参数
        cmd.extend([
            "--blue-enabled", str(1 if self.blue_enabled.get() else 0),
            "--blue-trigger", str(self.blue_trigger.get()),
            "--blue-duration", str(self.blue_duration.get()),
            "--blue-shrink-mult", str(self.blue_shrink_mult.get())
        ])

        # 奖励参数（AI 和手动模式都传，手动模式会忽略但无妨）
        cmd.extend([
            "--reward-red", str(self.reward_red.get()),
            "--reward-step", str(self.reward_step.get()),
            "--reward-death", str(self.reward_death.get())
        ])

        return cmd

    def start(self):
        if self.game_process and self.game_process.poll() is None:
            messagebox.showinfo("提示", "已有进程正在运行，请先停止")
            return

        cmd = self.build_command()
        try:
            self.game_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8'
            )
            self.start_btn.config(state=tk.DISABLED)
            self.replay_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)

            # 启动后台线程监控进程结束
            threading.Thread(target=self.game_watcher, daemon=True).start()

            msg = "启动 " + ("AI训练" if self.ai_mode.get() else "手动游戏")
            if not self.ai_mode.get() and self.record_var.get():
                # 日志文件名在 build_command 中生成，我们无法直接获取，但可以提示
                msg += "，日志将保存在 logs/ 目录"
            messagebox.showinfo("启动成功", msg)

        except Exception as e:
            messagebox.showerror("启动失败", f"错误信息：{e}")

    def game_watcher(self):
        if not self.game_process:
            return
        stdout, stderr = self.game_process.communicate()
        # 解析得分（仅手动模式输出 SCORE: 行）
        for line in stdout.splitlines():
            if line.startswith("SCORE:"):
                score_val = line.split(":")[1].strip()
                self.root.after(0, self.on_game_end, score_val)
                break
        # 无论是否捕获到得分，都恢复按钮
        self.root.after(0, self.enable_buttons)

    def on_game_end(self, score):
        self.save_score(score)
        messagebox.showinfo("游戏结束", f"得分：{score}")

    def enable_buttons(self):
        self.start_btn.config(state=tk.NORMAL)
        self.replay_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.game_process = None

    def stop_process(self):
        if self.game_process and self.game_process.poll() is None:
            self.game_process.terminate()
            messagebox.showinfo("已停止", "进程已终止")
            self.enable_buttons()
        else:
            messagebox.showinfo("提示", "没有正在运行的进程")

    def replay_log(self):
        if self.game_process and self.game_process.poll() is None:
            messagebox.showinfo("提示", "请先停止当前游戏进程")
            return

        log_file = filedialog.askopenfilename(
            title="选择日志文件",
            initialdir=LOG_DIR,
            filetypes=[("JSON log", "*.log"), ("All files", "*.*")]
        )
        if not log_file:
            return

        # 回放时使用当前速度，其他参数从日志读取
        cmd = [
            "python", "snake_game.py",
            "--replay", log_file,
            "--speed", str(self.speed_var.get())
        ]
        try:
            subprocess.Popen(cmd)
            messagebox.showinfo("回放启动", f"正在回放：{os.path.basename(log_file)}")
        except Exception as e:
            messagebox.showerror("启动回放失败", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = Launcher(root)
    root.mainloop()
