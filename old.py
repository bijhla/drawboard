from PIL import Image
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 配置
image_path = 'L:\\practice\\python\\drawboard\\1.png'  # 图片路径
api_url = 'https://api.paintboard.ayakacraft.com:11451/api/paintboard/paint'  # API URL
token = '45d57d3a-2294-49e5-9d4d-a7b687ada555'  # 你的token
uid = 708102  # 你的uid
delay_between_requests = 0.001  # 请求之间的延迟时间（秒）
num_iterations = 100  # 发送整张图片的次数
max_workers = 70  # 并发线程数
start_x, start_y = 734, 251  # 图片左上角的初始坐标

# 读取图片并转换为RGB模式
img = Image.open(image_path).convert('RGB')
pixels = img.load()
width, height = img.size

# 创建线程锁
output_lock = threading.Lock()

# 创建一个新的 Session 对象
session = requests.Session()

# 将RGB颜色转换为十进制
def rgb_to_decimal(r, g, b):
    return (r << 16) + (g << 8) + b

# 发送请求的函数
def send_request(x, y, r, g, b):
    decimal_color = rgb_to_decimal(r, g, b)
    payload = {
        "x": x + start_x,
        "y": y + start_y,
        "color": decimal_color,
        "uid": uid,
        "token": token
    }
    response = session.post(api_url, json=payload, timeout=30)

    # 使用线程锁同步输出
    with output_lock:
        # 检查响应头中的 Via 字段
        if 'Via' in response.headers and '502' in response.headers['Via']:
            print(f"Failed to send pixel ({x + start_x}, {y + start_y}) with color (R: {r}, G: {g}, B: {b}) (decimal: {decimal_color}): 502 Bad Gateway (Via header)")
        elif response.status_code == 200:
            try:
                response_data = response.json()
                if 'errorType' in response_data:
                    print(f"Failed to send pixel ({x + start_x}, {y + start_y}) with color (R: {r}, G: {g}, B: {b}) (decimal: {decimal_color}): {response_data['errorType']}")
                else:
                    print(f"Sent pixel ({x + start_x}, {y + start_y}) with color (R: {r}, G: {g}, B: {b}) (decimal: {decimal_color})")
            except ValueError:
                print(f"Failed to send pixel ({x + start_x}, {y + start_y}) with color (R: {r}, G: {g}, B: {b}) (decimal: {decimal_color}): Response is not JSON")
        else:
            print(f"Failed to send pixel ({x + start_x}, {y + start_y}) with color (R: {r}, G: {g}, B: {b}) (decimal: {decimal_color}): HTTP {response.status_code}")

# 遍历每个像素点
def process_image():
    futures = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for y in range(height):
            for x in range(width):
                r, g, b = pixels[x, y]
                future = executor.submit(send_request, x, y, r, g, b)
                futures.append(future)
                time.sleep(delay_between_requests)  # 延迟

    # 等待所有任务完成
    for future in as_completed(futures):
        future.result()

# 主循环
for iteration in range(num_iterations):
    print(f"Starting iteration {iteration + 1}/{num_iterations}")
    process_image()
    print(f"Finished iteration {iteration + 1}/{num_iterations}")
