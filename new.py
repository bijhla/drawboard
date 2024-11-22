from PIL import Image
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import os
import sys
import aiohttp
import asyncio

# 配置
image_path = 'L:\\practice\\python\\drawboard\\1.png'  # 图片路径
api_url = 'https://api.paintboard.ayakacraft.com:11451/api/paintboard/paint'  # API URL
tokens = [  # 你的token列表
    '45d57d3a-2294-49e5-9d4d-a7b687ada555'
]
uids = [  # 你的uid列表
    708102
]
delay_between_requests = 0.001  # 请求之间的延迟时间（秒）
num_iterations = 100  # 发送整张图片的次数
max_workers = 70  # 并发线程数
start_x, start_y = 734, 251  # 图片左上角的初始坐标
max_retries = 3  # 每个像素点的最大重试次数
consecutive_restart_threshold = 10  # 连续重启次数阈值
max_failed_attempts_per_pixel = 3  # 每个像素点最大失败尝试次数

# 读取图片并转换为RGB模式
img = Image.open(image_path).convert('RGB')
pixels = img.load()
width, height = img.size

# 创建线程锁
output_lock = threading.Lock()

# 将RGB颜色转换为十进制


def rgb_to_decimal(r, g, b):
    return (r << 16) + (g << 8) + b

# 全局变量，用于跟踪连续达到最大重试次数的次数和已发送图片的次数


consecutive_restarts = 0
iterations_completed = 0

# 存储每个像素点的失败尝试次数
failed_attempts = {}


async def send_request_async(session, x, y, r, g, b, account_index):
    global consecutive_restarts  # 声明使用全局变量

    decimal_color = rgb_to_decimal(r, g, b)

    # 使用account_index获取对应的uid和token
    current_token = tokens[account_index]
    current_uid = uids[account_index]

    payload = {
        "x": x + start_x,
        "y": y + start_y,
        "color": decimal_color,
        "uid": current_uid,
        "token": current_token
    }

    retries = max_retries  # 使用全局变量 max_retries

    pixel_key = (x, y)  # 使用元组作为键

    for i in range(retries):
        try:
            async with session.post(api_url, json=payload, timeout=30) as response:
                # 使用线程锁同步输出
                with output_lock:
                    # 检查响应头中的 Via 字段
                    if response.headers.get('Via') and '502' in response.headers.get('Via'):
                        print(
                            f"发送像素点 ({x + start_x}, {y + start_y}) 失败，颜色为 (R: {r}, G: {g}, B: {b}): 502 网关错误 (Via 头) 使用账户编号: {account_index}")
                        failed_attempts[pixel_key] = failed_attempts.get(
                            pixel_key, 0) + 1
                        return (x, y, r, g, b, account_index) if failed_attempts[pixel_key] < max_failed_attempts_per_pixel else None  # 超过最大失败次数，返回 None
                    elif response.status == 200:
                        try:
                            response_data = await response.json()
                            if 'errorType' in response_data:
                                print(
                                    f"发送像素点 ({x + start_x}, {y + start_y}) 失败，颜色为 (R: {r}, G: {g}, B: {b}): {response_data['errorType']} 使用账户编号: {account_index}")
                                failed_attempts[pixel_key] = failed_attempts.get(
                                    pixel_key, 0) + 1
                                return (x, y, r, g, b, account_index) if failed_attempts[pixel_key] < max_failed_attempts_per_pixel else None  # 超过最大失败次数，返回 None
                            else:
                                print(
                                    f"已发送像素点 ({x + start_x}, {y + start_y})，颜色为 (R: {r}, G: {g}, B: {b}) 使用账户编号: {account_index}")
                                return None  # 返回 None 表示成功
                        except ValueError:
                            print(
                                f"发送像素点 ({x + start_x}, {y + start_y}) 失败，颜色为 (R: {r}, G: {g}, B: {b}): 响应不是JSON格式 使用账户编号: {account_index}")
                            failed_attempts[pixel_key] = failed_attempts.get(
                                pixel_key, 0) + 1
                            return (x, y, r, g, b, account_index) if failed_attempts[pixel_key] < max_failed_attempts_per_pixel else None  # 超过最大失败次数，返回 None
                    else:
                        print(
                            f"发送像素点 ({x + start_x}, {y + start_y}) 失败，颜色为 (R: {r}, G: {g}, B: {b}): HTTP {response.status} 使用账户编号: {account_index}")
                        failed_attempts[pixel_key] = failed_attempts.get(
                            pixel_key, 0) + 1
                        return (x, y, r, g, b, account_index) if failed_attempts[pixel_key] < max_failed_attempts_per_pixel else None  # 超过最大失败次数，返回 None
                # 不再等待
            break  # 如果请求成功，跳出循环
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:  # 添加 asyncio.TimeoutError
            if i < retries - 1:
                print(
                    f"发送像素点 ({x + start_x}, {y + start_y}) 出错: {e}, 立即重试...")
                # 不再等待
            else:  # 如果是最后一次尝试，打印错误信息并根据连续重启次数决定是否重启程序
                print(
                    f"发送像素点 ({x + start_x}, {y + start_y}) 出错: {e}, 放弃.")
                consecutive_restarts += 1
                if consecutive_restarts >= consecutive_restart_threshold:
                    print(
                        f"达到连续重启阈值 ({consecutive_restart_threshold}). 正在重启程序...")
                    # 使用 sys.executable 和 sys.argv 重启程序
                    os.execl(sys.executable, sys.executable,
                             *sys.argv)  # 修改为 os.execl
                else:
                    print(
                        f"连续重启次数: {consecutive_restarts}/{consecutive_restart_threshold}")
                    failed_attempts[pixel_key] = failed_attempts.get(
                        pixel_key, 0) + 1
                    return (x, y, r, g, b, account_index) if failed_attempts[pixel_key] < max_failed_attempts_per_pixel else None  # 超过最大失败次数，返回 None


# 遍历每个像素点
async def process_image_async():
    global failed_attempts  # 声明使用全局变量
    failed_attempts = {}  # 在每次 process_image 开始时重置 failed_attempts
    failed_pixels = []
    num_accounts = len(tokens)  # 获取账户数量
    account_index = 0  # 初始化账户索引

    async with aiohttp.ClientSession() as session:
        tasks = []
        for y in range(height):
            for x in range(width):
                r, g, b = pixels[x, y]
                task = asyncio.ensure_future(send_request_async(
                    session, x, y, r, g, b, account_index))
                tasks.append(task)
                account_index = (account_index + 1) % num_accounts  # 循环使用账户

        results = await asyncio.gather(*tasks)

        for result in results:
            if result:
                failed_pixels.append(result)

    return failed_pixels


# 重置连续重启次数
def reset_consecutive_restarts():
    global consecutive_restarts
    consecutive_restarts = 0


# 主循环
async def main():
    global iterations_completed
    for iteration in range(num_iterations):
        print(f"开始第 {iteration + 1}/{num_iterations} 次迭代")
        failed_pixels = await process_image_async()
        iterations_completed += 1  # 增加已完成迭代次数

        # 重新绘制失败的像素
        while failed_pixels:
            print(f"正在重试 {len(failed_pixels)} 个失败的像素点...")
            new_failed_pixels = []

            async with aiohttp.ClientSession() as session:
                tasks = []
                for x, y, r, g, b, account_index in failed_pixels:  # 获取账户索引
                    task = asyncio.ensure_future(send_request_async(
                        session, x, y, r, g, b, account_index))
                    tasks.append(task)

                results = await asyncio.gather(*tasks)

                for result in results:
                    if result:
                        new_failed_pixels.append(result)
                    else:
                        reset_consecutive_restarts()  # 在成功发送像素后重置计数器

            failed_pixels = new_failed_pixels

        print(f"完成第 {iteration + 1}/{num_iterations} 次迭代")

        # 检查是否达到发送整张图片的次数
        if iterations_completed >= num_iterations:
            print(f"达到最大迭代次数 ({num_iterations}). 正在重启程序...")
            os.execl(sys.executable, sys.executable, *sys.argv)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
