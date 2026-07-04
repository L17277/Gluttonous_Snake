import pygame
import random
import sys
import json
import argparse
import math
import os

# ----- 常量配置 -----
DEFAULT_SPEED = 10
DEFAULT_GRID_SIZE = 20
WINDOW_SIZE = 600

# 颜色
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
DARK_GREEN = (0, 150, 0)
YELLOW = (255, 255, 0)
BLUE = (0, 0, 255)

# 方向
UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)


# ============================================================
#  蛇类
# ============================================================
class Snake:
    def __init__(self, grid_width, grid_height):
        self.grid_width = grid_width
        self.grid_height = grid_height
        self.body = [(grid_width // 2, grid_height // 2),
                     (grid_width // 2 - 1, grid_height // 2),
                     (grid_width // 2 - 2, grid_height // 2)]
        self.direction = RIGHT
        self.grow_flag = False

    def move(self):
        head = self.body[0]
        new_head = (head[0] + self.direction[0], head[1] + self.direction[1])
        self.body.insert(0, new_head)
        if not self.grow_flag:
            self.body.pop()
        else:
            self.grow_flag = False

    def change_direction(self, new_dir):
        if (new_dir[0] * -1, new_dir[1] * -1) != self.direction:
            self.direction = new_dir

    def grow(self):
        self.grow_flag = True

    def check_self_collision(self):
        head = self.body[0]
        return head in self.body[1:]

    def get_head(self):
        return self.body[0]

    def wrap_head(self):
        head = self.body[0]
        new_x = head[0] % self.grid_width
        new_y = head[1] % self.grid_height
        if (new_x, new_y) != head:
            self.body[0] = (new_x, new_y)

    def shrink(self, units):
        if units <= 0:
            return
        min_len = 3
        target_len = max(min_len, len(self.body) - units)
        while len(self.body) > target_len:
            self.body.pop()


# ============================================================
#  特殊食物（黄/蓝点）
# ============================================================
class SpecialFood:
    def __init__(self, pos, food_type, duration, spawn_time_offset=0):
        self.pos = pos
        self.type = food_type  # 'yellow' or 'blue'
        self.duration = duration
        self.spawn_time = pygame.time.get_ticks() / 1000.0 + spawn_time_offset

    def elapsed(self):
        return pygame.time.get_ticks() / 1000.0 - self.spawn_time

    def remaining(self):
        rem = self.duration - self.elapsed()
        return max(0, rem)

    def is_expired(self):
        return self.remaining() <= 0

    def get_score_multiplier(self):
        if self.type != 'yellow':
            return 0
        elapsed = self.elapsed()
        if elapsed < 1:
            return 6
        elif elapsed < 2:
            return 5
        elif elapsed < 3:
            return 4
        elif elapsed < 4:
            return 3
        elif elapsed < 5:
            return 2
        elif elapsed < 6:
            return 1
        else:
            return 0

    def get_shrink_units(self):
        if self.type != 'blue':
            return 0
        elapsed = self.elapsed()
        if elapsed < 1:
            return 3
        elif elapsed < 2:
            return 2
        elif elapsed < 3:
            return 1
        else:
            return 0


# ============================================================
#  红点（普通食物）
# ============================================================
class Food:
    def __init__(self, snake_body, grid_width, grid_height, occupied_positions=None):
        self.grid_width = grid_width
        self.grid_height = grid_height
        self.position = self.random_position(snake_body, occupied_positions or [])

    def random_position(self, snake_body, occupied):
        while True:
            pos = (random.randint(0, self.grid_width - 1),
                   random.randint(0, self.grid_height - 1))
            if pos not in snake_body and pos not in occupied:
                return pos

    def respawn(self, snake_body, occupied=None):
        self.position = self.random_position(snake_body, occupied or [])


# ============================================================
#  辅助函数
# ============================================================
def random_free_position(snake_body, grid_w, grid_h, occupied):
    attempts = 0
    while attempts < 1000:
        pos = (random.randint(0, grid_w - 1), random.randint(0, grid_h - 1))
        if pos not in snake_body and pos not in occupied:
            return pos
        attempts += 1
    return None


# ============================================================
#  绘图函数
# ============================================================
def draw_snake(surface, snake, cell_size):
    for i, (x, y) in enumerate(snake.body):
        rect = pygame.Rect(x * cell_size, y * cell_size, cell_size, cell_size)
        color = (0, 200, 0) if i == 0 else DARK_GREEN
        pygame.draw.rect(surface, color, rect)
        pygame.draw.rect(surface, BLACK, rect, 1)


def draw_food(surface, food, cell_size):
    rect = pygame.Rect(food.position[0] * cell_size, food.position[1] * cell_size,
                       cell_size, cell_size)
    pygame.draw.rect(surface, RED, rect)
    pygame.draw.rect(surface, BLACK, rect, 1)


def draw_special_foods(surface, special_foods, cell_size):
    for f in special_foods:
        color = YELLOW if f.type == 'yellow' else BLUE
        rect = pygame.Rect(f.pos[0] * cell_size, f.pos[1] * cell_size, cell_size, cell_size)
        pygame.draw.rect(surface, color, rect)
        pygame.draw.rect(surface, BLACK, rect, 1)


def draw_score(surface, score):
    font = pygame.font.Font(None, 36)
    text = font.render(f"Score: {score}", True, WHITE)
    surface.blit(text, (10, 10))


def draw_timers(surface, special_foods):
    font = pygame.font.Font(None, 30)
    y = 10
    for f in special_foods:
        label = "黄" if f.type == 'yellow' else "蓝"
        color = YELLOW if f.type == 'yellow' else BLUE
        remaining = f.remaining()
        if remaining > 0:
            seconds = math.ceil(remaining)
            text = font.render(f"{label} {seconds}s", True, color)
            surface.blit(text, (WINDOW_SIZE - text.get_width() - 10, y))
            y += text.get_height() + 2


# ============================================================
#  游戏状态快照（用于日志）
# ============================================================
class GameState:
    def __init__(self, snake_body, food_pos, score, direction,
                 yellow_pos=None, yellow_remaining=0,
                 blue_pos=None, blue_remaining=0):
        self.snake_body = snake_body[:]
        self.food_pos = food_pos
        self.score = score
        self.direction = direction
        self.yellow_pos = yellow_pos
        self.yellow_remaining = yellow_remaining
        self.blue_pos = blue_pos
        self.blue_remaining = blue_remaining

    def to_dict(self):
        data = {
            'snake': self.snake_body,
            'food': self.food_pos,
            'score': self.score,
            'direction': self.direction
        }
        if self.yellow_pos is not None:
            data['yellow_pos'] = self.yellow_pos
            data['yellow_remaining'] = self.yellow_remaining
        if self.blue_pos is not None:
            data['blue_pos'] = self.blue_pos
            data['blue_remaining'] = self.blue_remaining
        return data

    @classmethod
    def from_dict(cls, data):
        return cls(
            data['snake'],
            data['food'],
            data['score'],
            tuple(data['direction']),
            data.get('yellow_pos'),
            data.get('yellow_remaining', 0),
            data.get('blue_pos'),
            data.get('blue_remaining', 0)
        )


# ============================================================
#  AI 环境接口
# ============================================================
class GameEnv:
    def __init__(self, grid_size=20, wrap_mode=False,
                 yellow_enabled=True, yellow_trigger=6, yellow_duration=6, yellow_base_score=3,
                 blue_enabled=True, blue_trigger=10, blue_duration=5, blue_shrink_multiple=2,
                 reward_red=10, reward_step=-0.1, reward_death=-10,
                 render=True):
        self.grid_size = grid_size
        self.wrap_mode = wrap_mode
        self.yellow_enabled = yellow_enabled
        self.yellow_trigger = yellow_trigger
        self.yellow_duration = yellow_duration
        self.yellow_base_score = yellow_base_score
        self.blue_enabled = blue_enabled
        self.blue_trigger = blue_trigger
        self.blue_duration = blue_duration
        self.blue_shrink_multiple = blue_shrink_multiple
        self.reward_red = reward_red
        self.reward_step = reward_step
        self.reward_death = reward_death
        self.render = render

        self.cell_size = WINDOW_SIZE // grid_size
        if render:
            pygame.init()
            self.screen = pygame.display.set_mode((WINDOW_SIZE, WINDOW_SIZE))
            pygame.display.set_caption("AI 贪吃蛇训练")
            self.clock = pygame.time.Clock()
        else:
            pygame.init()
            self.screen = None
            self.clock = None
        self.reset()

    def reset(self):
        self.snake = Snake(self.grid_size, self.grid_size)
        self.food = Food(self.snake.body, self.grid_size, self.grid_size)
        self.special_foods = []
        self.score = 0
        self.done = False
        self.last_yellow_score = -1
        self.last_blue_score = -1
        self.total_reward = 0
        self.steps = 0
        return self._get_state()

    def _get_state(self):
        state = []
        head = self.snake.get_head()
        for i, seg in enumerate(self.snake.body):
            state.append({
                'type': 'snake',
                'pos': seg,
                'dist_from_head': i,
                'remaining': 0.0
            })
        state.append({
            'type': 'food',
            'pos': self.food.position,
            'dist_from_head': 0,
            'remaining': 0.0
        })
        for f in self.special_foods:
            state.append({
                'type': f.type,
                'pos': f.pos,
                'dist_from_head': 0,
                'remaining': f.remaining()
            })
        return state

    def step(self, action):
        if self.done:
            return self._get_state(), 0, True, {}

        self.steps += 1
        action_map = [UP, DOWN, LEFT, RIGHT]
        new_dir = action_map[action]
        self.snake.change_direction(new_dir)
        self.snake.move()
        head = self.snake.get_head()
        reward = self.reward_step
        done = False
        info = {}

        # 边界碰撞
        if not self.wrap_mode:
            if (head[0] < 0 or head[0] >= self.grid_size or
                head[1] < 0 or head[1] >= self.grid_size):
                reward = self.reward_death
                done = True
        else:
            self.snake.wrap_head()
            head = self.snake.get_head()

        # 自碰
        if self.snake.check_self_collision():
            reward = self.reward_death
            done = True

        # ---- 特殊食物（修正：无论是否有效都移除） ----
        ate_yellow = False
        ate_blue = False
        yellow_food = next((f for f in self.special_foods if f.type == 'yellow'), None)
        blue_food = next((f for f in self.special_foods if f.type == 'blue'), None)

        if yellow_food and head == yellow_food.pos:
            mult = yellow_food.get_score_multiplier()
            if mult > 0:
                points = mult * self.yellow_base_score
                self.score += points
                reward += points
                self.last_yellow_score = self.score
            self.special_foods.remove(yellow_food)
            ate_yellow = True

        if blue_food and head == blue_food.pos:
            units = blue_food.get_shrink_units()
            if units > 0:
                shrink_amount = units * self.blue_shrink_multiple
                self.snake.shrink(shrink_amount)
            self.special_foods.remove(blue_food)
            ate_blue = True

        # ---- 红点 ----
        if not ate_yellow and not ate_blue and not done and head == self.food.position:
            self.snake.grow()
            self.score += 1
            reward += self.reward_red
            occupied = [f.pos for f in self.special_foods]
            self.food.respawn(self.snake.body, occupied)

        # ---- 生成特殊食物 ----
        if not done:
            if self.yellow_enabled:
                if (not any(f.type == 'yellow' for f in self.special_foods) and
                    self.score > 0 and self.score % self.yellow_trigger == 0 and
                    self.score != self.last_yellow_score):
                    occupied = [self.food.position] + [f.pos for f in self.special_foods]
                    pos = random_free_position(self.snake.body, self.grid_size, self.grid_size, occupied)
                    if pos:
                        self.special_foods.append(SpecialFood(pos, 'yellow', self.yellow_duration))
                        self.last_yellow_score = self.score

            if self.blue_enabled:
                if (not any(f.type == 'blue' for f in self.special_foods) and
                    self.score > 0 and self.score % self.blue_trigger == 0 and
                    self.score != self.last_blue_score):
                    occupied = [self.food.position] + [f.pos for f in self.special_foods]
                    pos = random_free_position(self.snake.body, self.grid_size, self.grid_size, occupied)
                    if pos:
                        self.special_foods.append(SpecialFood(pos, 'blue', self.blue_duration))
                        self.last_blue_score = self.score

            self.special_foods = [f for f in self.special_foods if not f.is_expired()]

        if self.render and self.screen:
            self.render_frame()

        if done:
            info['score'] = self.score
            info['steps'] = self.steps
            self.done = True

        self.total_reward += reward
        return self._get_state(), reward, done, info

    def render_frame(self):
        self.screen.fill(BLACK)
        draw_snake(self.screen, self.snake, self.cell_size)
        draw_food(self.screen, self.food, self.cell_size)
        draw_special_foods(self.screen, self.special_foods, self.cell_size)
        draw_score(self.screen, self.score)
        draw_timers(self.screen, self.special_foods)
        pygame.display.flip()
        if self.clock:
            self.clock.tick(30)

    def close(self):
        pygame.quit()


# ============================================================
#  手动游戏主函数（支持记录、回放及所有参数）
# ============================================================
def run_game(speed, grid_size, log_file=None, replay_file=None,
             wrap_mode=False,
             yellow_enabled=True, yellow_trigger=6, yellow_duration=6, yellow_base_score=3,
             blue_enabled=True, blue_trigger=10, blue_duration=5, blue_shrink_multiple=2,
             reward_red=10, reward_step=-0.1, reward_death=-10):
    """手动游戏入口（也用于回放）"""
    if replay_file:
        with open(replay_file, 'r') as f:
            log_data = json.load(f)
        if isinstance(log_data, dict) and 'meta' in log_data and 'grid_size' in log_data['meta']:
            grid_size = log_data['meta']['grid_size']
            frames = log_data['frames']
        else:
            frames = log_data
        if not frames:
            print("日志为空")
            return
    else:
        frames = None

    pygame.init()
    cell_size = WINDOW_SIZE // grid_size
    screen = pygame.display.set_mode((WINDOW_SIZE, WINDOW_SIZE))
    if replay_file:
        pygame.display.set_caption(f"回放 - {os.path.basename(replay_file)}")
    else:
        pygame.display.set_caption("贪吃蛇 - 手动模式")
    clock = pygame.time.Clock()

    # ----- 回放 -----
    if replay_file:
        initial = frames[0]
        snake = Snake(grid_size, grid_size)
        snake.body = [tuple(p) for p in initial['snake']]
        food = Food(snake.body, grid_size, grid_size)
        food.position = tuple(initial['food'])
        score = initial['score']
        snake.direction = tuple(initial['direction'])
        special_foods = []
        if 'yellow_pos' in initial and initial['yellow_pos']:
            y_rem = initial['yellow_remaining']
            if y_rem > 0:
                y = SpecialFood(tuple(initial['yellow_pos']), 'yellow', 6,
                                spawn_time_offset=-(6 - y_rem))
                special_foods.append(y)
        if 'blue_pos' in initial and initial['blue_pos']:
            b_rem = initial['blue_remaining']
            if b_rem > 0:
                b = SpecialFood(tuple(initial['blue_pos']), 'blue', 5,
                                spawn_time_offset=-(5 - b_rem))
                special_foods.append(b)

        replay_index = 1
        replay_total = len(frames)
        running = True
        while running and replay_index < replay_total:
            clock.tick(speed)
            state = frames[replay_index]
            snake.body = [tuple(p) for p in state['snake']]
            food.position = tuple(state['food'])
            score = state['score']
            snake.direction = tuple(state['direction'])

            special_foods.clear()
            if 'yellow_pos' in state and state['yellow_pos']:
                y_rem = state['yellow_remaining']
                if y_rem > 0:
                    y = SpecialFood(tuple(state['yellow_pos']), 'yellow', 6,
                                    spawn_time_offset=-(6 - y_rem))
                    special_foods.append(y)
            if 'blue_pos' in state and state['blue_pos']:
                b_rem = state['blue_remaining']
                if b_rem > 0:
                    b = SpecialFood(tuple(state['blue_pos']), 'blue', 5,
                                    spawn_time_offset=-(5 - b_rem))
                    special_foods.append(b)

            replay_index += 1

            screen.fill(BLACK)
            draw_snake(screen, snake, cell_size)
            draw_food(screen, food, cell_size)
            draw_special_foods(screen, special_foods, cell_size)
            draw_score(screen, score)
            draw_timers(screen, special_foods)
            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

        if replay_index >= replay_total:
            font = pygame.font.Font(None, 40)
            text = font.render("Replay Finished", True, WHITE)
            screen.blit(text, (WINDOW_SIZE//2 - text.get_width()//2, WINDOW_SIZE//2 - 20))
            pygame.display.flip()
            pygame.time.wait(2000)
        pygame.quit()
        return

    # ----- 手动游戏 -----
    snake = Snake(grid_size, grid_size)
    food = Food(snake.body, grid_size, grid_size)
    score = 0
    special_foods = []
    last_yellow_score = -1
    last_blue_score = -1

    log_frames = []
    if log_file:
        log_frames.append(GameState(snake.body, food.position, score, snake.direction).to_dict())

    running = True
    while running:
        clock.tick(speed)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # 键盘轮询（修复同时按键）
        keys = pygame.key.get_pressed()
        new_dir = None
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            new_dir = UP
        elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
            new_dir = DOWN
        elif keys[pygame.K_LEFT] or keys[pygame.K_a]:
            new_dir = LEFT
        elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            new_dir = RIGHT
        if new_dir is not None:
            snake.change_direction(new_dir)

        snake.move()
        head = snake.get_head()

        if not wrap_mode:
            if (head[0] < 0 or head[0] >= grid_size or
                head[1] < 0 or head[1] >= grid_size):
                running = False
                break
        else:
            snake.wrap_head()
            head = snake.get_head()

        if snake.check_self_collision():
            running = False
            break

        # ---- 特殊食物（修正：无论是否有效都移除） ----
        ate_yellow = False
        ate_blue = False
        yellow_food = next((f for f in special_foods if f.type == 'yellow'), None)
        blue_food = next((f for f in special_foods if f.type == 'blue'), None)

        if yellow_food and head == yellow_food.pos:
            mult = yellow_food.get_score_multiplier()
            if mult > 0:
                points = mult * yellow_base_score
                score += points
                last_yellow_score = score
            special_foods.remove(yellow_food)
            ate_yellow = True

        if blue_food and head == blue_food.pos:
            units = blue_food.get_shrink_units()
            if units > 0:
                snake.shrink(units * blue_shrink_multiple)
            special_foods.remove(blue_food)
            ate_blue = True

        # ---- 红点 ----
        if not ate_yellow and not ate_blue and head == food.position:
            snake.grow()
            score += 1
            occupied = [f.pos for f in special_foods]
            food.respawn(snake.body, occupied)

        # ---- 生成特殊食物 ----
        if yellow_enabled:
            if (not any(f.type == 'yellow' for f in special_foods) and
                score > 0 and score % yellow_trigger == 0 and score != last_yellow_score):
                occupied = [food.position] + [f.pos for f in special_foods]
                pos = random_free_position(snake.body, grid_size, grid_size, occupied)
                if pos:
                    special_foods.append(SpecialFood(pos, 'yellow', yellow_duration))
                    last_yellow_score = score

        if blue_enabled:
            if (not any(f.type == 'blue' for f in special_foods) and
                score > 0 and score % blue_trigger == 0 and score != last_blue_score):
                occupied = [food.position] + [f.pos for f in special_foods]
                pos = random_free_position(snake.body, grid_size, grid_size, occupied)
                if pos:
                    special_foods.append(SpecialFood(pos, 'blue', blue_duration))
                    last_blue_score = score

        special_foods = [f for f in special_foods if not f.is_expired()]

        # ---- 记录 ----
        if log_file:
            yellow = next((f for f in special_foods if f.type == 'yellow'), None)
            blue = next((f for f in special_foods if f.type == 'blue'), None)
            state = GameState(
                snake.body, food.position, score, snake.direction,
                yellow.pos if yellow else None,
                yellow.remaining() if yellow else 0,
                blue.pos if blue else None,
                blue.remaining() if blue else 0
            )
            log_frames.append(state.to_dict())

        # ---- 绘制 ----
        screen.fill(BLACK)
        draw_snake(screen, snake, cell_size)
        draw_food(screen, food, cell_size)
        draw_special_foods(screen, special_foods, cell_size)
        draw_score(screen, score)
        draw_timers(screen, special_foods)
        pygame.display.flip()

    if log_file and log_frames:
        log_data = {'meta': {'grid_size': grid_size}, 'frames': log_frames}
        with open(log_file, 'w') as f:
            json.dump(log_data, f, indent=2)

    pygame.quit()
    print(f"SCORE:{score}")
    sys.exit(0)


# ============================================================
#  命令行入口
# ============================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="贪吃蛇游戏")
    parser.add_argument("--speed", type=int, default=DEFAULT_SPEED)
    parser.add_argument("--grid-size", type=int, default=DEFAULT_GRID_SIZE)
    parser.add_argument("--wrap", action="store_true")
    parser.add_argument("--log", type=str)
    parser.add_argument("--replay", type=str)

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

    parser.add_argument("--ai", action="store_true")

    args = parser.parse_args()

    if args.grid_size < 5:
        args.grid_size = 5
    if args.grid_size > 50:
        args.grid_size = 50

    run_game(
        speed=args.speed,
        grid_size=args.grid_size,
        log_file=args.log,
        replay_file=args.replay,
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
        reward_death=args.reward_death
    )
