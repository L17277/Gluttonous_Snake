import random
import numpy as np
from collections import deque
import torch
import torch.nn as nn
import torch.optim as optim
import argparse
import sys
import os
from snake_game import GameEnv  # 确保 snake_game.py 在同一目录

# ---------------------------- 超参数 ----------------------------
DEFAULT_EPISODES = 500
DEFAULT_BATCH_SIZE = 64
DEFAULT_GAMMA = 0.9
DEFAULT_EPSILON_START = 1.0
DEFAULT_EPSILON_DECAY = 0.995
DEFAULT_EPSILON_MIN = 0.01
DEFAULT_LEARNING_RATE = 0.001
DEFAULT_MEMORY_SIZE = 10000
DEFAULT_TARGET_UPDATE = 10
EMBED_DIM = 64
NHEAD = 4
NUM_LAYERS = 2

# ---------------------------- Transformer 模型 ----------------------------
class SnakeTransformer(nn.Module):
    def __init__(self, embed_dim=EMBED_DIM, nhead=NHEAD, num_layers=NUM_LAYERS, output_dim=4):
        super().__init__()
        self.embed_dim = embed_dim
        self.type_embed = nn.Embedding(4, embed_dim)
        self.pos_embed = nn.Linear(2, embed_dim)
        self.dist_embed = nn.Linear(1, embed_dim)
        self.remain_embed = nn.Linear(1, embed_dim)
        encoder_layer = nn.TransformerEncoderLayer(d_model=embed_dim, nhead=nhead, batch_first=True)
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.fc = nn.Linear(embed_dim, output_dim)

    def forward(self, grid_lists):
        """
        grid_lists: list of list of dict, 每个 dict 含 'type','pos','dist_from_head','remaining'
        返回 Q 值张量 (batch_size, output_dim)
        """
        batch_size = len(grid_lists)
        if batch_size == 0:
            return torch.empty(0, self.fc.out_features)

        # 提取特征
        batch_features = []
        batch_lengths = []
        for grid_list in grid_lists:
            if not grid_list:
                # 空状态（理论上不会发生），用零向量占位
                features = [torch.zeros(self.embed_dim)]
                batch_lengths.append(1)
            else:
                features = []
                for g in grid_list:
                    type_idx = {'snake':0, 'food':1, 'yellow':2, 'blue':3}[g['type']]
                    type_t = torch.LongTensor([type_idx])
                    pos_t = torch.FloatTensor(g['pos'])
                    dist_t = torch.FloatTensor([g['dist_from_head']])
                    remain_t = torch.FloatTensor([g['remaining']])
                    emb = (self.type_embed(type_t) + self.pos_embed(pos_t) +
                           self.dist_embed(dist_t) + self.remain_embed(remain_t))
                    features.append(emb.squeeze(0))
                batch_features.append(features)
                batch_lengths.append(len(features))

        # 填充序列
        max_len = max(batch_lengths)
        padded = torch.zeros(batch_size, max_len, self.embed_dim)
        mask = torch.ones(batch_size, max_len, dtype=torch.bool)  # True 表示填充
        for i, feat in enumerate(batch_features):
            length = len(feat)
            padded[i, :length] = torch.stack(feat)
            mask[i, :length] = False

        # Transformer 编码
        x = self.transformer(padded, src_key_padding_mask=mask)  # (batch, max_len, embed_dim)
        # 对有效位置求平均（忽略填充）
        lengths_t = torch.tensor(batch_lengths, device=x.device).float().unsqueeze(1)
        x = x.sum(dim=1) / lengths_t  # (batch, embed_dim)
        return self.fc(x)


# ---------------------------- DQN Agent ----------------------------
class DQNAgent:
    def __init__(self, gamma=DEFAULT_GAMMA, lr=DEFAULT_LEARNING_RATE,
                 memory_size=DEFAULT_MEMORY_SIZE, batch_size=DEFAULT_BATCH_SIZE,
                 epsilon_start=DEFAULT_EPSILON_START, epsilon_decay=DEFAULT_EPSILON_DECAY,
                 epsilon_min=DEFAULT_EPSILON_MIN):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.policy_net = SnakeTransformer().to(self.device)
        self.target_net = SnakeTransformer().to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=lr)
        self.memory = deque(maxlen=memory_size)
        self.batch_size = batch_size
        self.gamma = gamma
        self.epsilon = epsilon_start
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_decay
        self.steps_done = 0

    def act(self, state):
        """state 为列表（格子信息）"""
        if random.random() < self.epsilon:
            return random.randint(0, 3)
        state_t = [state]  # 包装成 batch
        with torch.no_grad():
            q_values = self.policy_net(state_t)  # (1,4)
        return q_values.argmax().item()

    def remember(self, state, action, reward, next_state, done):
        self.memory.append((state, action, reward, next_state, done))

    def learn(self):
        if len(self.memory) < self.batch_size:
            return
        batch = random.sample(self.memory, self.batch_size)
        states, actions, rewards, next_states, dones = zip(*batch)
        # states 和 next_states 是 list of list of dict

        q_values = self.policy_net(states).gather(1, torch.LongTensor(actions).unsqueeze(1).to(self.device))
        with torch.no_grad():
            max_next_q = self.target_net(next_states).max(1, keepdim=True)[0]
        targets = torch.FloatTensor(rewards).unsqueeze(1).to(self.device) + \
                  self.gamma * max_next_q * (~torch.BoolTensor(dones).unsqueeze(1).to(self.device))

        loss = nn.MSELoss()(q_values, targets)
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

    def update_target_net(self):
        self.target_net.load_state_dict(self.policy_net.state_dict())

    def save_model(self, episode):
        torch.save(self.policy_net.state_dict(), f"dqn_snake_ep{episode}.pth")
        print(f"Model saved at episode {episode}")


# ---------------------------- 训练主函数 ----------------------------
def train(args):
    env = GameEnv(
        grid_size=args.grid_size,
        wrap_mode=args.wrap,
        yellow_enabled=bool(args.yellow_enabled),
        yellow_trigger=args.yellow_trigger,
        yellow_duration=args.yellow_duration,
        yellow_base_score=args.yellow_base,
        blue_enabled=bool(args.blue_enabled),
        blue_trigger=args.blue_trigger,
        blue_duration=args.blue_duration,
        blue_shrink_multiple=args.blue_shrink_mult,
        reward_red=args.reward_red,
        reward_step=args.reward_step,
        reward_death=args.reward_death,
        render=True
    )

    agent = DQNAgent(
        gamma=args.gamma,
        lr=args.lr,
        memory_size=args.memory_size,
        batch_size=args.batch_size,
        epsilon_start=args.epsilon_start,
        epsilon_decay=args.epsilon_decay,
        epsilon_min=args.epsilon_min
    )

    scores = []
    for episode in range(1, args.episodes + 1):
        state = env.reset()
        done = False
        total_reward = 0
        step = 0
        while not done:
            action = agent.act(state)
            next_state, reward, done, info = env.step(action)
            agent.remember(state, action, reward, next_state, done)
            agent.learn()
            state = next_state
            total_reward += reward
            step += 1
            if done:
                score = info.get('score', 0)
                scores.append(score)
                avg = np.mean(scores[-20:]) if len(scores) >= 20 else np.mean(scores)
                print(f"Ep {episode}/{args.episodes} | Score: {score} | Avg(20): {avg:.2f} | Steps: {step} | Eps: {agent.epsilon:.3f}")
                break

        agent.epsilon = max(agent.epsilon_min, agent.epsilon * agent.epsilon_decay)
        if (episode + 1) % args.target_update == 0:
            agent.update_target_net()
            print("Target net updated.")

        # 每10局和第一局保存模型
        if episode == 1 or episode % 10 == 0:
            agent.save_model(episode)

    env.close()
    # 最终保存
    agent.save_model("final")
    print("Training finished.")


# ---------------------------- 命令行入口 ----------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DQN 贪吃蛇训练 (Transformer)")
    # 环境参数（与 snake_game.py 保持一致）
    parser.add_argument("--grid-size", type=int, default=20)
    parser.add_argument("--wrap", action="store_true")
    parser.add_argument("--yellow-enabled", type=int, default=1)
    parser.add_argument("--yellow-trigger", type=int, default=6)
    parser.add_argument("--yellow-duration", type=int, default=6)
    parser.add_argument("--yellow-base", type=int, default=3)
    parser.add_argument("--blue-enabled", type=int, default=1)
    parser.add_argument("--blue-trigger", type=int, default=10)
    parser.add_argument("--blue-duration", type=int, default=5)
    parser.add_argument("--blue-shrink-mult", type=int, default=2)
    parser.add_argument("--reward-red", type=float, default=10)
    parser.add_argument("--reward-step", type=float, default=-0.1)
    parser.add_argument("--reward-death", type=float, default=-10)

    # AI 超参数
    parser.add_argument("--episodes", type=int, default=DEFAULT_EPISODES)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--gamma", type=float, default=DEFAULT_GAMMA)
    parser.add_argument("--lr", type=float, default=DEFAULT_LEARNING_RATE)
    parser.add_argument("--epsilon-start", type=float, default=DEFAULT_EPSILON_START)
    parser.add_argument("--epsilon-decay", type=float, default=DEFAULT_EPSILON_DECAY)
    parser.add_argument("--epsilon-min", type=float, default=DEFAULT_EPSILON_MIN)
    parser.add_argument("--memory-size", type=int, default=DEFAULT_MEMORY_SIZE)
    parser.add_argument("--target-update", type=int, default=DEFAULT_TARGET_UPDATE)

    # AI 模式标记（由启动器传入）
    parser.add_argument("--ai", action="store_true", help="标识 AI 模式")

    args = parser.parse_args()
    train(args)
